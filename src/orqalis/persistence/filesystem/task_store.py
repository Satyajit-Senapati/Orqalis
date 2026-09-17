"""Project-local Task Capsule persistence adapters.

The existing orchestration layer speaks through small repository protocols.  This
module implements the task-related subset of those protocols over one repo-local
capsule aggregate, preserving the Run UUID used by the application while assigning
each user request a human-readable ``ORQ-YYYYMMDD-NNNN`` directory.

Mutable capsule files are committed under a short-lived state lock.  A durable
transaction marker contains the complete replacement documents and the event tail;
readers roll an interrupted transaction forward before observing the capsule.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from opentelemetry import trace
from pydantic import ValidationError

from orqalis.core.state_machine import TERMINAL
from orqalis.domain.acceptance import AcceptanceCriterion, GoalContract
from orqalis.domain.agent import ActorSession
from orqalis.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionKind,
    ApprovalRequest,
    ApprovalStatus,
    ControlPolicy,
)
from orqalis.domain.artifact import Artifact, Evidence, Finding
from orqalis.domain.base import Entity
from orqalis.domain.delivery import ChangeReport, FinalValidation, GitDelivery
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.domain.events import Event, EventDraft
from orqalis.domain.execution import ReviewRecord
from orqalis.domain.plan import TaskPlan
from orqalis.domain.project import Project
from orqalis.domain.run import Run
from orqalis.domain.task import Task, TaskExecution
from orqalis.domain.timing import PhaseExecution
from orqalis.git.service import validate_relative_path
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    append_jsonl_atomic,
    atomic_write_bytes,
    atomic_write_json,
    ensure_no_filesystem_links,
    read_json_object,
    read_jsonl,
    repair_jsonl_prefix,
)
from orqalis.persistence.filesystem.layout import (
    ProjectLayout,
    bootstrap_project_store,
    ensure_current_schema,
    load_manifest,
)
from orqalis.persistence.filesystem.locking import FileLock, LockTimeoutError
from orqalis.security.redaction import is_credential_field, safe_diagnostic

if TYPE_CHECKING:
    from orqalis.context.models import ProjectContextPack

TASK_SCHEMA_VERSION = 1
_CAPSULE_ID = re.compile(r"ORQ-(?P<date>[0-9]{8})-(?P<sequence>[0-9]{4})\Z")
_EXTENSION_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_CONTROLLER_GUARD = threading.Lock()
_CONTROLLER_OWNERS: dict[str, object] = {}
_PROJECTION_SOURCE = "execution/state.yaml"
_PROJECTION_NOTE = (
    "> Derived from `execution/state.yaml`; this file is a human-readable projection, "
    "not authoritative state."
)
_PHASE_FILES = {
    "CONTEXT": "context.yaml",
    "GOAL": "goal.yaml",
    "PLAN": "planning.yaml",
    "IMPLEMENT": "implementation.yaml",
    "TEST": "testing.yaml",
    "REVIEW": "review.yaml",
    "REPAIR": "repair.yaml",
    "DOCS": "documentation.yaml",
    "DELIVER": "delivery.yaml",
}


def _json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConflictError("Task capsule contains data that cannot be serialized") from exc


def _ensure_secret_safe(value: object) -> None:
    encoded = _json_bytes(value).decode("utf-8")
    if safe_diagnostic(encoded) != encoded:
        raise PolicyDeniedError("Task Capsule state cannot contain credentials or private data")


def _safe_projection_value(value: object) -> object:
    if isinstance(value, str):
        return safe_diagnostic(value)
    if isinstance(value, dict):
        projected: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            projected[key] = (
                "[REDACTED]" if is_credential_field(key) else _safe_projection_value(item)
            )
        return projected
    if isinstance(value, (list, tuple)):
        return [_safe_projection_value(item) for item in value]
    return value


def _projection_payload(generation: int, value: dict[str, object]) -> object:
    return _safe_projection_value(
        {
            "schema_version": TASK_SCHEMA_VERSION,
            "_projection": {
                "authoritative": False,
                "source": _PROJECTION_SOURCE,
                "generation": generation,
            },
            **value,
        }
    )


def _projection_bytes(generation: int, value: dict[str, object]) -> bytes:
    return _json_bytes(_projection_payload(generation, value))


def _projection_jsonl(generation: int, values: list[dict[str, object]]) -> bytes:
    records = [
        _safe_projection_value(
            {
                "schema_version": TASK_SCHEMA_VERSION,
                "_projection_source": _PROJECTION_SOURCE,
                "_projection_generation": generation,
                **value,
            }
        )
        for value in values
    ]
    try:
        return b"".join(
            (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode(
                "utf-8"
            )
            for value in records
        )
    except (TypeError, ValueError) as exc:
        raise ConflictError("Task capsule projection cannot be serialized") from exc


def _projection_markdown(value: str) -> bytes:
    content = f"{_PROJECTION_NOTE}\n\n{value.rstrip()}\n"
    return safe_diagnostic(content).encode("utf-8")


def _safe_extension(namespace: str) -> str:
    if _EXTENSION_NAME.fullmatch(namespace) is None:
        raise ValueError("Extension namespace must be a lowercase filesystem-safe name")
    return namespace


def _title(request: str) -> str:
    line = next((line.strip() for line in request.splitlines() if line.strip()), "Task")
    return line[:120]


def _sort_entities(values: dict[UUID, Any]) -> list[Any]:
    return sorted(values.values(), key=lambda item: (item.created_at, str(item.id)))


def _document(content: bytes) -> dict[str, str]:
    return {
        "content": base64.b64encode(content).decode("ascii"),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _decode_document(value: object) -> bytes:
    if not isinstance(value, dict):
        raise ConflictError("Task transaction contains an invalid document")
    encoded, expected = value.get("content"), value.get("sha256")
    if not isinstance(encoded, str) or not isinstance(expected, str):
        raise ConflictError("Task transaction contains an invalid document")
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ConflictError("Task transaction contains invalid encoded content") from exc
    if hashlib.sha256(content).hexdigest() != expected:
        raise ConflictError("Task transaction document checksum does not match")
    return content


def _relative_target(capsule: Path, relative: str) -> Path:
    try:
        validate_relative_path(relative)
    except PolicyDeniedError as exc:
        raise ConflictError("Task transaction contains an unsafe target") from exc
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts:
        raise ConflictError("Task transaction contains an unsafe target")
    capsule_root = ensure_no_filesystem_links(capsule).resolve(strict=True)
    target = ensure_no_filesystem_links(capsule_root.joinpath(*path.parts))
    resolved = target.resolve(strict=False)
    if not resolved.is_relative_to(capsule_root):
        raise ConflictError("Task transaction target escapes its capsule")
    return target


def _event_record(event: Event) -> dict[str, object]:
    return {"schema_version": TASK_SCHEMA_VERSION, **event.model_dump(mode="json")}


def _parse_event(value: dict[str, object]) -> Event:
    version = value.get("schema_version")
    if version != TASK_SCHEMA_VERSION:
        raise ConflictError("Unsupported Task Capsule event schema")
    try:
        return Event.model_validate({k: v for k, v in value.items() if k != "schema_version"})
    except ValidationError as exc:
        raise ConflictError("Task Capsule contains an invalid event") from exc


@dataclass(slots=True)
class TaskCapsuleAggregate:
    """In-memory authoritative state shared by repository adapters in one UoW."""

    capsule_id: str
    generation: int
    run: Run
    goals: dict[UUID, GoalContract] = field(default_factory=dict)
    evidence: dict[UUID, Evidence] = field(default_factory=dict)
    plans: dict[int, TaskPlan] = field(default_factory=dict)
    tasks: dict[UUID, Task] = field(default_factory=dict)
    actors: dict[UUID, ActorSession] = field(default_factory=dict)
    executions: dict[UUID, TaskExecution] = field(default_factory=dict)
    phases: dict[UUID, PhaseExecution] = field(default_factory=dict)
    control_policy: ControlPolicy | None = None
    approval_requests: dict[UUID, ApprovalRequest] = field(default_factory=dict)
    approval_decisions: dict[UUID, ApprovalDecision] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    extensions: dict[str, object] = field(default_factory=dict)
    dirty: bool = False
    is_new: bool = False
    persisted_event_count: int = 0

    def mark_dirty(self) -> None:
        self.dirty = True


def _projection_extension(aggregate: TaskCapsuleAggregate, namespace: str) -> dict[str, object]:
    raw = aggregate.extensions.get(namespace)
    if not isinstance(raw, dict) or raw.get("schema_version") != TASK_SCHEMA_VERSION:
        return {}
    if any(not isinstance(key, str) for key in raw):
        raise ConflictError(f"Task Capsule {namespace} projection source is invalid")
    return cast(dict[str, object], raw)


def _projection_entities[EntityT: Entity](
    document: dict[str, object],
    key: str,
    model: type[EntityT],
    run_id: UUID,
) -> tuple[EntityT, ...]:
    raw = document.get(key, [])
    if not isinstance(raw, list):
        raise ConflictError(f"Task Capsule {key} projection source is invalid")
    try:
        values = tuple(model.model_validate(value) for value in raw)
    except ValidationError as exc:
        raise ConflictError(f"Task Capsule {key} projection source is invalid") from exc
    if any(value.__dict__.get("run_id") != run_id for value in values):
        raise ConflictError(f"Task Capsule {key} projection source belongs to another run")
    return tuple(sorted(values, key=lambda item: (item.created_at, str(item.id))))


def _context_extension(aggregate: TaskCapsuleAggregate) -> ProjectContextPack | None:
    # Localized to avoid context -> graph -> filesystem package import cycles.
    from orqalis.context.models import ProjectContextPack

    raw = aggregate.extensions.get("context")
    if raw is None:
        return None
    try:
        pack = ProjectContextPack.model_validate(raw)
    except ValidationError as exc:
        raise ConflictError("Task Capsule context projection source is invalid") from exc
    if pack.schema_version != TASK_SCHEMA_VERSION or pack.project_id != str(
        aggregate.run.project_id
    ):
        raise ConflictError("Task Capsule context projection source belongs to another project")
    return pack


class TaskCapsuleStore:
    """Root-scoped factory and discovery surface for Task Capsule UoWs."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout

    @classmethod
    def from_root(cls, root: Path) -> TaskCapsuleStore:
        layout = ProjectLayout(root)
        # SDK/API/CLI composition opens the project through this factory. Migrate
        # supported old manifests here so callers cannot accidentally construct a
        # store that fails later with an otherwise recoverable schema.
        if layout.manifest.is_file():
            ensure_current_schema(layout)
        return cls(layout)

    @property
    def root(self) -> Path:
        return self.layout.root

    def unit_of_work(self) -> TaskCapsuleUnitOfWork:
        return TaskCapsuleUnitOfWork(self)

    def _capsule_directories(self) -> tuple[Path, ...]:
        if not self.layout.tasks.is_dir():
            return ()
        return tuple(
            sorted(
                (
                    path
                    for path in self.layout.tasks.iterdir()
                    if path.is_dir() and _CAPSULE_ID.fullmatch(path.name)
                ),
                key=lambda path: path.name,
            )
        )

    def _task_document(self, capsule: Path) -> dict[str, object] | None:
        path = capsule / "task.yaml"
        if not path.is_file():
            return None
        try:
            document = read_json_object(path)
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Task Capsule metadata is invalid") from exc
        if document.get("schema_version") != TASK_SCHEMA_VERSION:
            raise ConflictError("Unsupported Task Capsule schema")
        if document.get("id") != capsule.name or not isinstance(document.get("run_id"), str):
            raise ConflictError("Task Capsule identity is inconsistent")
        return document

    def _index_entries(self) -> tuple[dict[str, object], ...]:
        capsule_names = {path.name for path in self._capsule_directories()}
        path = self.layout.tasks / "index.json"
        if path.is_file():
            try:
                document = read_json_object(path)
                values = document.get("tasks")
                if document.get("schema_version") == TASK_SCHEMA_VERSION and isinstance(
                    values, list
                ):
                    cached_entries = tuple(value for value in values if isinstance(value, dict))
                    indexed_names = {
                        value.get("id")
                        for value in cached_entries
                        if isinstance(value.get("id"), str)
                    }
                    if len(cached_entries) == len(values) and indexed_names == capsule_names:
                        return cached_entries
            except (OSError, FilesystemFormatError):
                pass
        entries: list[dict[str, object]] = []
        for capsule in self._capsule_directories():
            task_document = self._task_document(capsule)
            if task_document is not None:
                entries.append(self._index_entry(task_document))
        return tuple(entries)

    @staticmethod
    def _index_entry(document: dict[str, object]) -> dict[str, object]:
        project_value = document.get("project")
        project = cast(dict[str, object], project_value) if isinstance(project_value, dict) else {}
        return {
            "id": document.get("id"),
            "run_id": document.get("run_id"),
            "title": document.get("title"),
            "status": document.get("status"),
            "created_at": document.get("created_at"),
            "completed_at": document.get("completed_at"),
            "branch": project.get("branch"),
            "starting_commit": project.get("starting_commit"),
        }

    def capsule_id(self, run_id: UUID) -> str | None:
        expected = str(run_id)
        for entry in self._index_entries():
            capsule_id = entry.get("id")
            if entry.get("run_id") == expected and isinstance(capsule_id, str):
                candidate = self.layout.task(capsule_id)
                document = self._task_document(candidate)
                if document is not None and document.get("run_id") == expected:
                    return capsule_id
        # An index is derived and may be stale or deleted; scan canonical task files.
        for capsule in self._capsule_directories():
            document = self._task_document(capsule)
            if document is not None and document.get("run_id") == expected:
                return capsule.name
        return None

    def capsule_path(self, run_id: UUID) -> Path | None:
        capsule_id = self.capsule_id(run_id)
        return self.layout.task(capsule_id) if capsule_id else None

    def reserve_capsule(self) -> tuple[str, Path]:
        day = datetime.now(UTC).strftime("%Y%m%d")
        self.layout.tasks.mkdir(parents=True, exist_ok=True)
        with FileLock(self.layout.lock("tasks-index")):
            sequences = [
                int(match.group("sequence"))
                for path in self._capsule_directories()
                if (match := _CAPSULE_ID.fullmatch(path.name)) and match.group("date") == day
            ]
            sequence = max(sequences, default=0) + 1
            if sequence > 9999:
                raise ConflictError("Daily Task Capsule sequence is exhausted")
            capsule_id = f"ORQ-{day}-{sequence:04d}"
            path = self.layout.task(capsule_id)
            try:
                path.mkdir(parents=False, exist_ok=False)
            except FileExistsError as exc:
                raise ConflictError("Task Capsule identity was allocated concurrently") from exc
            return capsule_id, path

    def rebuild_index(self) -> int:
        self.layout.tasks.mkdir(parents=True, exist_ok=True)
        with FileLock(self.layout.lock("tasks-index")):
            entries: list[dict[str, object]] = []
            for capsule in self._capsule_directories():
                document = self._task_document(capsule)
                if document is not None:
                    entries.append(self._index_entry(document))
            entries.sort(key=lambda value: str(value.get("id")))
            atomic_write_json(
                self.layout.tasks / "index.json",
                {"schema_version": TASK_SCHEMA_VERSION, "tasks": entries},
            )
            return len(entries)


class TaskCapsuleSession:
    """One transaction shared by all capsule repository adapters."""

    def __init__(self, store: TaskCapsuleStore) -> None:
        self.store = store
        self.layout = store.layout
        self._capsules: dict[UUID, TaskCapsuleAggregate] = {}
        self._state_locks: dict[UUID, FileLock] = {}
        self._controller_locks: dict[UUID, FileLock] = {}
        self._controller_keys: dict[UUID, str] = {}
        self._lease_token = object()
        self._reserved: dict[UUID, Path] = {}
        self._pending_project: Project | None = None
        self._project_extensions: dict[str, object] | None = None
        self._project_generation = 0
        self._project_extensions_dirty = False
        self._closed = False

    def _state_lock(self, run_id: UUID, capsule_id: str) -> None:
        if run_id in self._state_locks:
            return
        lock = FileLock(self.layout.lock(f"{capsule_id}.state"))
        lock.acquire()
        self._state_locks[run_id] = lock

    def try_run_lock(self, run_id: UUID) -> bool:
        """Acquire the long controller lease until this UoW exits."""

        if run_id in self._controller_locks:
            return True
        capsule_id = self.store.capsule_id(run_id)
        if capsule_id is None and run_id in self._capsules:
            capsule_id = self._capsules[run_id].capsule_id
        if capsule_id is None:
            raise NotFoundError("Run not found")
        lock_path = self.layout.lock(f"{capsule_id}.controller")
        key = os.path.normcase(str(lock_path.absolute()))
        with _CONTROLLER_GUARD:
            owner = _CONTROLLER_OWNERS.get(key)
            if owner is not None and owner is not self._lease_token:
                return False
            _CONTROLLER_OWNERS[key] = self._lease_token
        lock = FileLock(lock_path, timeout=0)
        try:
            lock.acquire()
        except LockTimeoutError:
            with _CONTROLLER_GUARD:
                if _CONTROLLER_OWNERS.get(key) is self._lease_token:
                    _CONTROLLER_OWNERS.pop(key, None)
            return False
        self._controller_locks[run_id] = lock
        self._controller_keys[run_id] = key
        return True

    def _recover(self, capsule: Path) -> None:
        marker = capsule / "execution" / ".transaction.json"
        if not marker.is_file():
            return
        try:
            transaction = read_json_object(marker)
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Task Capsule transaction marker is invalid") from exc
        if transaction.get("schema_version") != TASK_SCHEMA_VERSION:
            raise ConflictError("Unsupported Task Capsule transaction schema")
        documents = transaction.get("documents")
        if not isinstance(documents, dict):
            raise ConflictError("Task Capsule transaction has no documents")
        # State is the commit snapshot and is replaced last.
        names = sorted(documents, key=lambda value: (value == "execution/state.yaml", value))
        for relative in names:
            if not isinstance(relative, str):
                raise ConflictError("Task transaction contains an invalid target")
            atomic_write_bytes(
                _relative_target(capsule, relative), _decode_document(documents[relative])
            )
        base = transaction.get("event_base_sequence")
        tail = transaction.get("events")
        if (
            isinstance(base, bool)
            or not isinstance(base, int)
            or base < 0
            or not isinstance(tail, list)
        ):
            raise ConflictError("Task Capsule transaction has an invalid event tail")
        events_path = capsule / "execution" / "events.jsonl"
        if not events_path.exists():
            atomic_write_bytes(events_path, b"")
        try:
            existing = list(read_jsonl(events_path))
        except FilesystemFormatError:
            try:
                existing = list(repair_jsonl_prefix(events_path, base))
            except (OSError, FilesystemFormatError) as exc:
                raise ConflictError("Task Capsule event log is invalid") from exc
        except OSError as exc:
            raise ConflictError("Task Capsule event log is invalid") from exc
        if len(existing) < base:
            raise ConflictError("Task Capsule event log is missing committed history")
        for offset, value in enumerate(tail, start=1):
            if not isinstance(value, dict):
                raise ConflictError("Task Capsule transaction contains an invalid event")
            position = base + offset
            if position <= len(existing):
                if existing[position - 1] != value:
                    raise ConflictError("Task Capsule event history diverged during recovery")
                continue
            if len(existing) != position - 1:
                raise ConflictError("Task Capsule event sequence is not contiguous")
            append_jsonl_atomic(events_path, value)
            existing.append(value)
        with suppress(FileNotFoundError):
            marker.unlink()

    def _load_path(self, capsule: Path) -> TaskCapsuleAggregate:
        state_path = capsule / "execution" / "state.yaml"
        try:
            state = read_json_object(state_path)
            event_values = read_jsonl(capsule / "execution" / "events.jsonl")
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Task Capsule state is invalid") from exc
        if state.get("schema_version") != TASK_SCHEMA_VERSION:
            raise ConflictError("Unsupported Task Capsule state schema")
        generation = state.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ConflictError("Task Capsule generation is invalid")
        try:
            run = Run.model_validate(state.get("run"))
            goals = {
                contract.goal.id: contract
                for value in _list(state, "goals")
                for contract in (GoalContract.model_validate(value),)
            }
            evidence = {
                item.id: item
                for value in _list(state, "evidence")
                for item in (Evidence.model_validate(value),)
            }
            plans = {
                item.version: item
                for value in _list(state, "plans")
                for item in (TaskPlan.model_validate(value),)
            }
            tasks = {
                item.id: item
                for value in _list(state, "tasks")
                for item in (Task.model_validate(value),)
            }
            actors = {
                item.id: item
                for value in _list(state, "actors")
                for item in (ActorSession.model_validate(value),)
            }
            executions = {
                item.id: item
                for value in _list(state, "executions")
                for item in (TaskExecution.model_validate(value),)
            }
            phases = {
                item.id: item
                for value in _list(state, "phases")
                for item in (PhaseExecution.model_validate(value),)
            }
            policy_value = state.get("control_policy")
            policy = (
                ControlPolicy.model_validate(policy_value) if policy_value is not None else None
            )
            requests = {
                item.id: item
                for value in _list(state, "approval_requests")
                for item in (ApprovalRequest.model_validate(value),)
            }
            decisions = {
                item.request_id: item
                for value in _list(state, "approval_decisions")
                for item in (ApprovalDecision.model_validate(value),)
            }
            events = [_parse_event(value) for value in event_values]
        except ValidationError as exc:
            raise ConflictError("Task Capsule contains invalid domain state") from exc
        if any(event.run_id != run.id for event in events) or [
            event.sequence for event in events
        ] != list(range(1, len(events) + 1)):
            raise ConflictError("Task Capsule event sequence is invalid")
        if run.last_event_sequence != len(events):
            raise ConflictError("Task Capsule state and event cursor disagree")
        extensions = state.get("extensions", {})
        if not isinstance(extensions, dict):
            raise ConflictError("Task Capsule extensions are invalid")
        return TaskCapsuleAggregate(
            capsule_id=capsule.name,
            generation=generation,
            run=run,
            goals=goals,
            evidence=evidence,
            plans=plans,
            tasks=tasks,
            actors=actors,
            executions=executions,
            phases=phases,
            control_policy=policy,
            approval_requests=requests,
            approval_decisions=decisions,
            events=events,
            extensions=deepcopy(extensions),
            persisted_event_count=len(events),
        )

    def load_capsule(self, run_id: UUID, *, for_update: bool = False) -> TaskCapsuleAggregate:
        cached = self._capsules.get(run_id)
        if cached is not None:
            if for_update and not cached.is_new:
                self._state_lock(run_id, cached.capsule_id)
                current = self._disk_generation(self.layout.task(cached.capsule_id))
                if current != cached.generation:
                    raise ConflictError("Task Capsule changed concurrently; retry")
            return cached
        capsule_id = self.store.capsule_id(run_id)
        if capsule_id is None:
            raise NotFoundError("Run not found")
        capsule = self.layout.task(capsule_id)
        self._state_lock(run_id, capsule_id)
        self._recover(capsule)
        aggregate = self._load_path(capsule)
        if aggregate.run.id != run_id:
            raise ConflictError("Task Capsule run identity is inconsistent")
        self._capsules[run_id] = aggregate
        if not for_update:
            self._release_state_lock(run_id)
        return aggregate

    def create_capsule(self, run: Run) -> TaskCapsuleAggregate:
        if run.id in self._capsules or self.store.capsule_id(run.id) is not None:
            raise ConflictError("Run identity already exists")
        if safe_diagnostic(run.request) != run.request:
            raise PolicyDeniedError("Run requests cannot contain credentials")
        capsule_id, path = self.store.reserve_capsule()
        aggregate = TaskCapsuleAggregate(
            capsule_id=capsule_id,
            generation=0,
            run=run,
            dirty=True,
            is_new=True,
        )
        self._capsules[run.id] = aggregate
        self._reserved[run.id] = path
        self._state_lock(run.id, capsule_id)
        return aggregate

    def iter_capsules(self) -> tuple[TaskCapsuleAggregate, ...]:
        values: list[TaskCapsuleAggregate] = []
        seen = set(self._capsules)
        values.extend(self._capsules.values())
        for entry in self.store._index_entries():
            raw = entry.get("run_id")
            try:
                run_id = UUID(raw) if isinstance(raw, str) else None
            except ValueError:
                continue
            if run_id is not None and run_id not in seen:
                try:
                    values.append(self.load_capsule(run_id))
                except NotFoundError:
                    continue
                seen.add(run_id)
        return tuple(values)

    def extension(self, run_id: UUID, namespace: str) -> object | None:
        aggregate = self.load_capsule(run_id)
        return deepcopy(aggregate.extensions.get(_safe_extension(namespace)))

    def save_extension(self, run_id: UUID, namespace: str, value: object) -> None:
        aggregate = self.load_capsule(run_id, for_update=True)
        aggregate.extensions[_safe_extension(namespace)] = deepcopy(value)
        _json_bytes(aggregate.extensions)
        aggregate.mark_dirty()

    def _load_project_extensions(self) -> None:
        if self._project_extensions is not None:
            return
        path = self.layout.project / "state.yaml"
        if not path.is_file():
            self._project_extensions, self._project_generation = {}, 0
            return
        try:
            document = read_json_object(path)
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Project filesystem state is invalid") from exc
        generation, extensions = document.get("generation"), document.get("extensions")
        if (
            document.get("schema_version") != TASK_SCHEMA_VERSION
            or isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
            or not isinstance(extensions, dict)
        ):
            raise ConflictError("Project filesystem state is invalid")
        self._project_generation = generation
        self._project_extensions = deepcopy(extensions)

    def project_extension(self, namespace: str) -> object | None:
        self._load_project_extensions()
        assert self._project_extensions is not None
        return deepcopy(self._project_extensions.get(_safe_extension(namespace)))

    def save_project_extension(self, namespace: str, value: object) -> None:
        self._load_project_extensions()
        assert self._project_extensions is not None
        self._project_extensions[_safe_extension(namespace)] = deepcopy(value)
        _json_bytes(self._project_extensions)
        self._project_extensions_dirty = True

    def _disk_generation(self, capsule: Path) -> int:
        self._recover(capsule)
        try:
            value = read_json_object(capsule / "execution" / "state.yaml").get("generation")
        except (OSError, FilesystemFormatError) as exc:
            raise ConflictError("Task Capsule state is invalid") from exc
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConflictError("Task Capsule generation is invalid")
        return value

    def _state_document(
        self, aggregate: TaskCapsuleAggregate, generation: int
    ) -> dict[str, object]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "generation": generation,
            "capsule_id": aggregate.capsule_id,
            "run": aggregate.run.model_dump(mode="json"),
            "goals": [
                value.model_dump(mode="json")
                for value in sorted(aggregate.goals.values(), key=lambda item: item.goal.version)
            ],
            "evidence": [
                item.model_dump(mode="json") for item in _sort_entities(aggregate.evidence)
            ],
            "plans": [
                value.model_dump(mode="json")
                for value in sorted(aggregate.plans.values(), key=lambda item: item.version)
            ],
            "tasks": [item.model_dump(mode="json") for item in _sort_entities(aggregate.tasks)],
            "actors": [item.model_dump(mode="json") for item in _sort_entities(aggregate.actors)],
            "executions": [
                item.model_dump(mode="json") for item in _sort_entities(aggregate.executions)
            ],
            "phases": [item.model_dump(mode="json") for item in _sort_entities(aggregate.phases)],
            "control_policy": aggregate.control_policy.model_dump(mode="json")
            if aggregate.control_policy
            else None,
            "approval_requests": [
                item.model_dump(mode="json") for item in _sort_entities(aggregate.approval_requests)
            ],
            "approval_decisions": [
                item.model_dump(mode="json")
                for item in sorted(
                    aggregate.approval_decisions.values(),
                    key=lambda value: (value.created_at, str(value.id)),
                )
            ],
            "extensions": deepcopy(aggregate.extensions),
        }

    def _task_document(self, aggregate: TaskCapsuleAggregate) -> dict[str, object]:
        run = aggregate.run
        updated = aggregate.events[-1].occurred_at if aggregate.events else run.created_at
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "id": aggregate.capsule_id,
            "run_id": str(run.id),
            "title": _title(run.request),
            "status": run.state.value,
            "created_at": run.created_at.isoformat(),
            "updated_at": updated.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "project": {
                "id": str(run.project_id),
                "branch": run.target_branch,
                "starting_commit": run.base_commit,
            },
            "request": {"source": "application"},
            "current_phase": run.ui_phase.value,
            "iteration": run.repair_iteration,
            "max_iterations": run.max_repair_iterations,
        }

    def _stage_documents(
        self, aggregate: TaskCapsuleAggregate, generation: int
    ) -> dict[str, bytes]:
        documents: dict[str, bytes] = {}
        context = _context_extension(aggregate)
        if context is not None:
            context_lines = [
                "# Context pack",
                "",
                f"Task: {context.task}",
                f"Project: {context.project_name}",
                f"Branch: {context.branch or '(detached)'}",
                f"Commit: `{context.head_commit}`",
                f"Budget: {context.size_chars}/{context.max_chars} characters",
                f"Truncated: {'yes' if context.truncated else 'no'}",
            ]
            if context.relevant_files:
                context_lines.extend(("", "## Relevant files", ""))
                context_lines.extend(f"- `{path}`" for path in context.relevant_files)
            if context.memory:
                context_lines.extend(("", "## Memory", ""))
                context_lines.extend(
                    f"- {item.record.title} ({item.freshness.value}, score {item.score:g})"
                    for item in context.memory
                )
            if context.graph:
                context_lines.extend(("", "## Graph results", ""))
                context_lines.extend(
                    f"- {item.node.name} ({item.node.kind})" for item in context.graph
                )
            if context.related_tasks:
                context_lines.extend(("", "## Related tasks", ""))
                context_lines.extend(f"- {item.id}: {item.title}" for item in context.related_tasks)
            documents["context/context-pack.md"] = _projection_markdown("\n".join(context_lines))
            documents["context/memory-used.yaml"] = _projection_bytes(
                generation,
                {
                    "memory": [
                        {
                            "id": item.record.id,
                            "title": item.record.title,
                            "category": item.record.category.value,
                            "freshness": item.freshness.value,
                            "score": item.score,
                            "source": item.record.source.model_dump(mode="json"),
                            "verified_commit": item.record.verified_commit,
                            "introduced_by_task": item.record.introduced_by_task,
                            "confidence": item.record.confidence,
                            "last_verified_at": item.record.last_verified_at.isoformat(),
                        }
                        for item in context.memory
                    ]
                },
            )
            documents["context/files-used.json"] = _projection_bytes(
                generation,
                {
                    "relevant_files": list(context.relevant_files),
                    "dirty_paths": list(context.dirty_paths),
                },
            )
            documents["context/graph-query.json"] = _projection_bytes(
                generation,
                {
                    "query": context.task,
                    "branch": context.branch,
                    "head_commit": context.head_commit,
                    "results": [
                        {
                            "node": item.node.model_dump(mode="json"),
                            "score": item.score,
                            "distance": item.distance,
                            "neighbors": list(item.neighbors),
                        }
                        for item in context.graph
                    ],
                },
            )

        phase_groups: dict[str, list[PhaseExecution]] = {}
        for phase in sorted(
            aggregate.phases.values(),
            key=lambda item: (item.phase.value, item.iteration, item.started_at, str(item.id)),
        ):
            phase_groups.setdefault(phase.phase.value, []).append(phase)
        for phase_name, phases in phase_groups.items():
            filename = _PHASE_FILES[phase_name]
            documents[f"execution/phases/{filename}"] = _projection_bytes(
                generation,
                {
                    "phase": phase_name,
                    "executions": [item.model_dump(mode="json") for item in phases],
                },
            )

        for actor in _sort_entities(aggregate.actors):
            documents[f"execution/agents/{actor.id}/session.yaml"] = _projection_bytes(
                generation,
                {"session": actor.model_dump(mode="json")},
            )

        executions_by_task: dict[UUID, list[TaskExecution]] = {}
        for execution in _sort_entities(aggregate.executions):
            executions_by_task.setdefault(execution.task_id, []).append(execution)
        task_ids = set(aggregate.tasks) | set(executions_by_task)
        for task_id in sorted(task_ids, key=str):
            task = aggregate.tasks.get(task_id)
            documents[f"execution/subtasks/{task_id}.yaml"] = _projection_bytes(
                generation,
                {
                    "task": task.model_dump(mode="json") if task is not None else None,
                    "executions": [
                        item.model_dump(mode="json") for item in executions_by_task.get(task_id, [])
                    ],
                },
            )

        execution_extension = _projection_extension(aggregate, "execution")
        delivery_extension = _projection_extension(aggregate, "delivery")
        reviews = _projection_entities(
            execution_extension, "reviews", ReviewRecord, aggregate.run.id
        )
        guardians = _projection_entities(
            delivery_extension, "guardians", ChangeReport, aggregate.run.id
        )
        validations = _projection_entities(
            delivery_extension, "validations", FinalValidation, aggregate.run.id
        )
        artifacts = _projection_entities(
            delivery_extension, "artifacts", Artifact, aggregate.run.id
        )
        findings = _projection_entities(delivery_extension, "findings", Finding, aggregate.run.id)
        delivery: GitDelivery | None = None
        raw_delivery = delivery_extension.get("git_delivery")
        if raw_delivery is not None:
            try:
                delivery = GitDelivery.model_validate(raw_delivery)
            except ValidationError as exc:
                raise ConflictError(
                    "Task Capsule Git delivery projection source is invalid"
                ) from exc
            if delivery.run_id != aggregate.run.id:
                raise ConflictError("Task Capsule Git delivery belongs to another run")

        for review in reviews:
            documents[f"review/reviews/{review.id}.yaml"] = _projection_bytes(
                generation,
                {"review": review.model_dump(mode="json")},
            )
        if findings:
            documents["review/findings.jsonl"] = _projection_jsonl(
                generation,
                [item.model_dump(mode="json") for item in findings],
            )
        if guardians:
            documents["review/change-guardian.yaml"] = _projection_bytes(
                generation,
                {
                    "latest": guardians[-1].model_dump(mode="json"),
                    "reports": [item.model_dump(mode="json") for item in guardians],
                },
            )

        current_goal_id = aggregate.run.current_goal_version_id
        current_goal = aggregate.goals.get(current_goal_id) if current_goal_id is not None else None
        has_acceptance_state = bool(
            aggregate.evidence
            or reviews
            or validations
            or (
                current_goal is not None
                and any(item.status.value != "PENDING" for item in current_goal.criteria)
            )
        )
        if has_acceptance_state:
            documents["review/acceptance-results.yaml"] = _projection_bytes(
                generation,
                {
                    "goal_version_id": str(current_goal.goal.id) if current_goal else None,
                    "criteria": [
                        item.model_dump(mode="json")
                        for item in (current_goal.criteria if current_goal else ())
                    ],
                    "evidence": [
                        item.model_dump(mode="json") for item in _sort_entities(aggregate.evidence)
                    ],
                    "reviews": [item.model_dump(mode="json") for item in reviews],
                    "validations": [item.model_dump(mode="json") for item in validations],
                },
            )

        if artifacts:
            documents["artifacts/index.yaml"] = _projection_bytes(
                generation,
                {"artifacts": [item.model_dump(mode="json") for item in artifacts]},
            )

        if guardians:
            report = guardians[-1]
            documents["changes/files.json"] = _projection_bytes(
                generation,
                {
                    "report_id": str(report.id),
                    "checkpoint": report.checkpoint,
                    "base_commit": report.base_commit,
                    "tree_hash": report.tree_hash,
                    "passed": report.passed,
                    "files": [item.model_dump(mode="json") for item in report.changes],
                },
            )
            diff_lines = [
                "# Diff summary",
                "",
                f"Checkpoint: {report.checkpoint}",
                f"Passed: {'yes' if report.passed else 'no'}",
                f"Files changed: {len(report.changes)}",
            ]
            if report.changes:
                diff_lines.extend(("", "## Files", ""))
                diff_lines.extend(
                    f"- `{item.path}` ? {item.status}; +{item.added_lines} "
                    f"-{item.deleted_lines}{' (binary)' if item.binary else ''}"
                    for item in report.changes
                )
            documents["changes/diff-summary.md"] = _projection_markdown("\n".join(diff_lines))

        if delivery is not None:
            documents["delivery/commit.yaml"] = _projection_bytes(
                generation,
                {
                    "id": str(delivery.id),
                    "run_id": str(delivery.run_id),
                    "base_commit": delivery.base_commit,
                    "branch": delivery.branch,
                    "tree_hash": delivery.tree_hash,
                    "git_tree_sha": delivery.git_tree_sha,
                    "commit_message": delivery.commit_message,
                    "commit_attached": delivery.commit_attached,
                    "commit_sha": delivery.commit_sha,
                    "policy": delivery.policy.model_dump(mode="json"),
                },
            )
            documents["delivery/push.yaml"] = _projection_bytes(
                generation,
                {
                    "delivery_id": str(delivery.id),
                    "push_status": delivery.push_status,
                    "remote": delivery.remote,
                    "requested": delivery.policy.push,
                },
            )

        if aggregate.run.state in TERMINAL:
            criteria = current_goal.criteria if current_goal is not None else ()
            acceptance_counts = {
                status: sum(item.status.value == status for item in criteria)
                for status in ("PENDING", "TESTING", "PASS", "FAIL")
            }
            task_counts = {
                status: sum(item.status.value == status for item in aggregate.tasks.values())
                for status in (
                    "PENDING",
                    "READY",
                    "RUNNING",
                    "WAITING",
                    "BLOCKED",
                    "SUCCEEDED",
                    "FAILED",
                    "CANCELLED",
                    "SKIPPED",
                )
            }
            result: dict[str, object] = {
                "capsule_id": aggregate.capsule_id,
                "run_id": str(aggregate.run.id),
                "project_id": str(aggregate.run.project_id),
                "state": aggregate.run.state.value,
                "phase": aggregate.run.ui_phase.value,
                "branch": aggregate.run.target_branch,
                "base_commit": aggregate.run.base_commit,
                "started_at": aggregate.run.started_at.isoformat()
                if aggregate.run.started_at
                else None,
                "completed_at": aggregate.run.completed_at.isoformat()
                if aggregate.run.completed_at
                else None,
                "repair_iterations": aggregate.run.repair_iteration,
                "goal_version_id": str(current_goal.goal.id) if current_goal else None,
                "acceptance": acceptance_counts,
                "tasks": task_counts,
                "execution_attempts": len(aggregate.executions),
                "actors": len(aggregate.actors),
                "evidence": len(aggregate.evidence),
                "reviews": len(reviews),
                "findings": len(findings),
                "artifacts": len(artifacts),
                "changed_files": len(guardians[-1].changes) if guardians else 0,
                "latest_review": reviews[-1].model_dump(mode="json") if reviews else None,
                "latest_guardian": guardians[-1].model_dump(mode="json") if guardians else None,
                "latest_validation": validations[-1].model_dump(mode="json")
                if validations
                else None,
                "delivery": delivery.model_dump(mode="json") if delivery else None,
            }
            documents["final/result.yaml"] = _projection_bytes(generation, result)
            summary_lines = [
                "# Final result",
                "",
                f"State: **{aggregate.run.state.value}**",
                f"Branch: `{aggregate.run.target_branch}`",
                f"Base commit: `{aggregate.run.base_commit}`",
                f"Repair iterations: {aggregate.run.repair_iteration}",
                f"Acceptance: {acceptance_counts['PASS']} passed, "
                f"{acceptance_counts['FAIL']} failed, "
                f"{acceptance_counts['PENDING']} pending",
                f"Tasks: {task_counts['SUCCEEDED']} succeeded, "
                f"{task_counts['FAILED']} failed, {task_counts['CANCELLED']} cancelled",
                f"Evidence: {len(aggregate.evidence)}",
                f"Findings: {len(findings)}",
                f"Changed files: {len(guardians[-1].changes) if guardians else 0}",
                f"Commit: `{delivery.commit_sha}`"
                if delivery and delivery.commit_sha
                else "Commit: not attached",
                f"Push: {delivery.push_status}" if delivery else "Push: unavailable",
            ]
            documents["final/summary.md"] = _projection_markdown("\n".join(summary_lines))

        return documents

    def _documents(self, aggregate: TaskCapsuleAggregate, generation: int) -> dict[str, bytes]:
        state = self._state_document(aggregate, generation)
        _ensure_secret_safe(state)
        documents: dict[str, bytes] = {
            "task.yaml": _json_bytes(self._task_document(aggregate)),
            "request.md": (aggregate.run.request.rstrip() + "\n").encode("utf-8"),
            "execution/state.yaml": _json_bytes(state),
        }
        current_goal_id = aggregate.run.current_goal_version_id
        current = aggregate.goals.get(current_goal_id) if current_goal_id is not None else None
        if current is not None:
            lines = ["# Goal", "", current.goal.goal, "", "## Scope", ""]
            lines.extend(f"- {item}" for item in current.goal.scope)
            lines.extend(("", "## Definition of done", ""))
            lines.extend(f"- {item}" for item in current.goal.definition_of_done)
            documents["goal/goal.md"] = _projection_markdown("\n".join(lines))
            documents["goal/acceptance.yaml"] = _projection_bytes(
                generation,
                {
                    "goal_version_id": str(current.goal.id),
                    "criteria": [item.model_dump(mode="json") for item in current.criteria],
                },
            )
        for contract in aggregate.goals.values():
            documents[f"goal/versions/{contract.goal.version:04d}.json"] = _projection_bytes(
                generation,
                contract.model_dump(mode="json"),
            )
        if aggregate.plans:
            plan = aggregate.plans[max(aggregate.plans)]
            plan = plan.model_copy(
                update={"tasks": tuple(aggregate.tasks[item.id] for item in plan.tasks)}
            )
            documents["plan/dag.json"] = _projection_bytes(
                generation,
                plan.model_dump(mode="json"),
            )
            documents["plan/subtasks.yaml"] = _projection_bytes(
                generation,
                {
                    "tasks": [item.model_dump(mode="json") for item in plan.tasks],
                },
            )
            documents["plan/plan.md"] = _projection_markdown(
                "# Plan\n\n" + "\n".join(f"- {item.description}" for item in plan.tasks) + "\n"
            )
        if aggregate.control_policy or aggregate.approval_requests:
            documents["execution/approvals.yaml"] = _projection_bytes(
                generation,
                {
                    "policy": aggregate.control_policy.model_dump(mode="json")
                    if aggregate.control_policy
                    else None,
                    "requests": [
                        _approval_view(item, aggregate.approval_decisions).model_dump(mode="json")
                        for item in _sort_entities(aggregate.approval_requests)
                    ],
                },
            )
        for item in aggregate.evidence.values():
            documents[f"evidence/{item.id}.json"] = _projection_bytes(
                generation,
                item.model_dump(mode="json"),
            )
        documents.update(self._stage_documents(aggregate, generation))
        return documents

    def _commit_capsule(self, aggregate: TaskCapsuleAggregate) -> None:
        if not aggregate.dirty:
            return
        capsule = self.layout.task(aggregate.capsule_id)
        self._state_lock(aggregate.run.id, aggregate.capsule_id)
        if not aggregate.is_new:
            current = self._disk_generation(capsule)
            if current != aggregate.generation:
                raise ConflictError("Task Capsule changed concurrently; retry")
        generation = aggregate.generation + 1
        documents = self._documents(aggregate, generation)
        tail = aggregate.events[aggregate.persisted_event_count :]
        marker = capsule / "execution" / ".transaction.json"
        atomic_write_json(
            marker,
            {
                "schema_version": TASK_SCHEMA_VERSION,
                "generation": generation,
                "documents": {name: _document(content) for name, content in documents.items()},
                "event_base_sequence": aggregate.persisted_event_count,
                "events": [_event_record(event) for event in tail],
            },
        )
        self._recover(capsule)
        aggregate.generation = generation
        aggregate.persisted_event_count = len(aggregate.events)
        aggregate.dirty = False
        aggregate.is_new = False
        self._reserved.pop(aggregate.run.id, None)

    def _commit_project(self) -> None:
        if self._pending_project is not None:
            project = self._pending_project
            with FileLock(self.layout.lock("project-identity")):
                existing = _load_project(self.layout)
                if existing is not None and existing.id != project.id:
                    raise ConflictError("Project identity already exists")
                if existing is None:
                    identity = project.model_dump(mode="json", exclude={"repo_root"})
                    identity["repo_root"] = "."
                    atomic_write_json(
                        self.layout.project / "identity.yaml",
                        {"schema_version": TASK_SCHEMA_VERSION, **identity},
                    )
                    bootstrap_project_store(
                        self.layout.root,
                        project_id=project.id,
                        project_name=project.name,
                        initialized_at=project.created_at,
                    )
            self._pending_project = None
        if self._project_extensions_dirty:
            assert self._project_extensions is not None
            with FileLock(self.layout.lock("project-state")):
                path = self.layout.project / "state.yaml"
                disk_generation = 0
                if path.is_file():
                    document = read_json_object(path)
                    value = document.get("generation")
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise ConflictError("Project filesystem state is invalid")
                    disk_generation = value
                if disk_generation != self._project_generation:
                    raise ConflictError("Project filesystem state changed concurrently; retry")
                self._project_generation += 1
                atomic_write_json(
                    path,
                    {
                        "schema_version": TASK_SCHEMA_VERSION,
                        "generation": self._project_generation,
                        "extensions": self._project_extensions,
                    },
                )
            self._project_extensions_dirty = False

    def commit(self) -> None:
        self._ensure_open()
        self._commit_project()
        for run_id in sorted(self._capsules, key=str):
            self._commit_capsule(self._capsules[run_id])
        if self._capsules:
            self.store.rebuild_index()

    def pending_events(self) -> tuple[Event, ...]:
        """Return uncommitted event tails without scanning unrelated capsules."""

        self._ensure_open()
        return tuple(
            event
            for aggregate in self._capsules.values()
            for event in aggregate.events[aggregate.persisted_event_count :]
        )

    def rollback(self) -> None:
        for run_id, path in tuple(self._reserved.items()):
            with suppress(OSError):
                path.rmdir()
            self._reserved.pop(run_id, None)
        self._capsules.clear()
        self._pending_project = None
        self._project_extensions = None
        self._project_extensions_dirty = False
        self._release_locks()

    def close(self) -> None:
        if self._closed:
            return
        if self._reserved or any(item.dirty for item in self._capsules.values()):
            self.rollback()
        self._release_locks()
        self._closed = True

    def _release_state_lock(self, run_id: UUID) -> None:
        lock = self._state_locks.pop(run_id, None)
        if lock is not None:
            lock.release()

    def _release_locks(self) -> None:
        for lock in reversed(tuple(self._state_locks.values())):
            lock.release()
        self._state_locks.clear()
        for run_id, lock in reversed(tuple(self._controller_locks.items())):
            key = self._controller_keys.pop(run_id)
            try:
                lock.release()
            finally:
                with _CONTROLLER_GUARD:
                    if _CONTROLLER_OWNERS.get(key) is self._lease_token:
                        _CONTROLLER_OWNERS.pop(key, None)
                self._controller_locks.pop(run_id, None)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Task Capsule session is closed")


class FilesystemProjectRepository:
    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    @property
    def root(self) -> Path:
        return self.session.layout.root

    def get(self, project_id: UUID) -> Project | None:
        pending = self.session._pending_project
        if pending is not None and pending.id == project_id:
            return pending
        project = _load_project(self.session.layout)
        return project if project and project.id == project_id else None

    def get_by_root(self, root: Path) -> Project | None:
        try:
            matches = root.expanduser().resolve(strict=True) == self.root.resolve(strict=True)
        except OSError:
            return None
        if not matches:
            return None
        return self.session._pending_project or _load_project(self.session.layout)

    def list(self) -> tuple[Project, ...]:
        project = self.session._pending_project or _load_project(self.session.layout)
        return (project,) if project else ()

    def add(self, project: Project) -> Project:
        if project.repo_root.resolve(strict=True) != self.root.resolve(strict=True):
            raise PolicyDeniedError("Project repository root does not match this local store")
        existing = _load_project(self.session.layout)
        if existing is not None:
            raise ConflictError("Project identity already exists")
        self.session._pending_project = project
        return project


class FilesystemRunRepository:
    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def add(self, run: Run) -> None:
        self.session.create_capsule(run)

    def get(self, run_id: UUID, for_update: bool = False) -> Run | None:
        try:
            return self.session.load_capsule(run_id, for_update=for_update).run
        except NotFoundError:
            return None

    def list(self, project_id: UUID | None = None, limit: int = 100) -> tuple[Run, ...]:
        values = [
            aggregate.run
            for aggregate in self.session.iter_capsules()
            if project_id is None or aggregate.run.project_id == project_id
        ]
        values.sort(key=lambda item: (item.created_at, str(item.id)), reverse=True)
        return tuple(values[:limit])

    def save(self, run: Run) -> None:
        aggregate = self.session.load_capsule(run.id, for_update=True)
        if run.project_id != aggregate.run.project_id or run.created_at != aggregate.run.created_at:
            raise ConflictError("Run identity cannot be changed")
        aggregate.run = run.model_copy(
            update={"last_event_sequence": aggregate.run.last_event_sequence}
        )
        aggregate.mark_dirty()

    def save_goal(self, contract: GoalContract) -> None:
        aggregate = self.session.load_capsule(contract.goal.run_id, for_update=True)
        existing = aggregate.goals.get(contract.goal.id)
        if existing is not None and existing != contract:
            raise ConflictError("Goal identity already exists")
        if any(
            item.goal.version == contract.goal.version and item.goal.id != contract.goal.id
            for item in aggregate.goals.values()
        ):
            raise ConflictError("Goal version already exists")
        aggregate.goals[contract.goal.id] = contract
        aggregate.mark_dirty()

    def set_current_goal(self, run_id: UUID, goal_id: UUID) -> None:
        aggregate = self.session.load_capsule(run_id, for_update=True)
        if goal_id not in aggregate.goals:
            raise NotFoundError("Goal not found")
        aggregate.run = aggregate.run.model_copy(update={"current_goal_version_id": goal_id})
        aggregate.mark_dirty()

    def get_goal(self, goal_id: UUID) -> GoalContract | None:
        for aggregate in self.session.iter_capsules():
            if value := aggregate.goals.get(goal_id):
                return value
        return None

    def get_evidence(self, evidence_id: UUID) -> Evidence | None:
        for aggregate in self.session.iter_capsules():
            if value := aggregate.evidence.get(evidence_id):
                return value
        return None

    def save_criterion(self, criterion: AcceptanceCriterion) -> None:
        for aggregate in self.session.iter_capsules():
            contract = aggregate.goals.get(criterion.goal_version_id)
            if contract is None:
                continue
            aggregate = self.session.load_capsule(aggregate.run.id, for_update=True)
            contract = aggregate.goals[criterion.goal_version_id]
            if not any(item.id == criterion.id for item in contract.criteria):
                return
            aggregate.goals[criterion.goal_version_id] = contract.model_copy(
                update={
                    "criteria": tuple(
                        criterion if item.id == criterion.id else item for item in contract.criteria
                    )
                }
            )
            aggregate.mark_dirty()
            return

    def save_evaluation(self, criterion: AcceptanceCriterion, evidence: Evidence) -> None:
        aggregate = next(
            (
                item
                for item in self.session.iter_capsules()
                if criterion.goal_version_id in item.goals
            ),
            None,
        )
        if aggregate is None:
            raise NotFoundError("Goal not found")
        aggregate = self.session.load_capsule(aggregate.run.id, for_update=True)
        aggregate.evidence[evidence.id] = evidence
        self.save_criterion(criterion)
        aggregate.mark_dirty()


class FilesystemEventRepository:
    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def append(self, run_id: UUID, draft: EventDraft) -> Event:
        aggregate = self.session.load_capsule(run_id, for_update=True)
        existing = next(
            (item for item in aggregate.events if item.idempotency_key == draft.idempotency_key),
            None,
        )
        if existing is not None:
            if (
                existing.event_type != draft.event_type
                or existing.payload != draft.payload
                or existing.task_id != draft.task_id
                or existing.actor_session_id != draft.actor_session_id
                or existing.task_execution_id != draft.task_execution_id
                or existing.phase != draft.phase
            ):
                raise ConflictError("Idempotency key reused for a different event")
            return existing
        payload = draft.payload.model_dump_json()
        if safe_diagnostic(payload) != payload:
            raise ConflictError("Unsafe event payload rejected")
        timestamp = (
            max(aggregate.events[-1].occurred_at, draft.occurred_at)
            if aggregate.events
            else draft.occurred_at
        )
        span = trace.get_current_span().get_span_context()
        event = Event(
            project_id=aggregate.run.project_id,
            run_id=run_id,
            sequence=aggregate.run.last_event_sequence + 1,
            **draft.model_dump(exclude={"occurred_at"}),
            occurred_at=timestamp,
            status=draft.payload.status,
            trace_id=format(span.trace_id, "032x") if span.is_valid else None,
        )
        aggregate.events.append(event)
        aggregate.run = aggregate.run.model_copy(update={"last_event_sequence": event.sequence})
        aggregate.mark_dirty()
        return event

    def list(self, run_id: UUID, after: int = 0, limit: int | None = None) -> tuple[Event, ...]:
        events = [
            item for item in self.session.load_capsule(run_id).events if item.sequence > after
        ]
        return tuple(events if limit is None else events[:limit])

    def by_key(self, run_id: UUID, key: str) -> Event | None:
        return next(
            (
                item
                for item in self.session.load_capsule(run_id).events
                if item.idempotency_key == key
            ),
            None,
        )


class FilesystemRuntimeRepository:
    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def add_task(self, task: Task) -> None:
        aggregate = self.session.load_capsule(task.run_id, for_update=True)
        if task.id in aggregate.tasks:
            raise ConflictError("Task identity already exists")
        aggregate.tasks[task.id] = task
        aggregate.mark_dirty()

    def tasks(self, run_id: UUID) -> tuple[Task, ...]:
        return tuple(_sort_entities(self.session.load_capsule(run_id).tasks))

    def save_plan(self, plan: TaskPlan) -> None:
        aggregate = self.session.load_capsule(plan.run_id, for_update=True)
        existing_plan = aggregate.plans.get(plan.version)
        if existing_plan is not None and existing_plan != plan:
            raise ConflictError("Plan version already exists")
        for task in plan.tasks:
            existing = aggregate.tasks.get(task.id)
            if existing is not None and existing != task:
                raise ConflictError("Plan revisions cannot rewrite existing task records")
            aggregate.tasks.setdefault(task.id, task)
        aggregate.plans[plan.version] = plan
        aggregate.mark_dirty()

    def get_plan(self, run_id: UUID, version: int) -> TaskPlan | None:
        aggregate = self.session.load_capsule(run_id)
        plan = aggregate.plans.get(version)
        if plan is None:
            return None
        return plan.model_copy(
            update={"tasks": tuple(aggregate.tasks[item.id] for item in plan.tasks)}
        )

    def save_task(self, task: Task) -> None:
        aggregate = self.session.load_capsule(task.run_id, for_update=True)
        if task.id in aggregate.tasks:
            aggregate.tasks[task.id] = task
            aggregate.mark_dirty()

    def actors(self, run_id: UUID) -> tuple[ActorSession, ...]:
        return tuple(_sort_entities(self.session.load_capsule(run_id).actors))

    def save_actor(self, actor: ActorSession) -> None:
        aggregate = self.session.load_capsule(actor.run_id, for_update=True)
        aggregate.actors[actor.id] = actor
        aggregate.mark_dirty()

    def executions(self, run_id: UUID) -> tuple[TaskExecution, ...]:
        return tuple(_sort_entities(self.session.load_capsule(run_id).executions))

    def save_execution(self, execution: TaskExecution) -> None:
        aggregate = self.session.load_capsule(execution.run_id, for_update=True)
        aggregate.executions[execution.id] = execution
        aggregate.mark_dirty()

    def phases(self, run_id: UUID) -> tuple[PhaseExecution, ...]:
        return tuple(_sort_entities(self.session.load_capsule(run_id).phases))

    def save_phase(self, phase: PhaseExecution) -> None:
        aggregate = self.session.load_capsule(phase.run_id, for_update=True)
        if any(
            item.id != phase.id and item.phase == phase.phase and item.iteration == phase.iteration
            for item in aggregate.phases.values()
        ):
            raise ConflictError("Phase iteration already exists")
        aggregate.phases[phase.id] = phase
        aggregate.mark_dirty()


class FilesystemApprovalRepository:
    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def policy(self, run_id: UUID) -> ControlPolicy | None:
        return self.session.load_capsule(run_id).control_policy

    def save_policy(self, policy: ControlPolicy) -> None:
        aggregate = self.session.load_capsule(policy.run_id, for_update=True)
        aggregate.control_policy = policy
        aggregate.mark_dirty()

    def get(self, request_id: UUID) -> ApprovalRequest | None:
        for aggregate in self.session.iter_capsules():
            request = aggregate.approval_requests.get(request_id)
            if request is not None:
                return _approval_view(request, aggregate.approval_decisions)
        return None

    def list(self, run_id: UUID) -> tuple[ApprovalRequest, ...]:
        aggregate = self.session.load_capsule(run_id)
        return tuple(
            _approval_view(item, aggregate.approval_decisions)
            for item in _sort_entities(aggregate.approval_requests)
        )

    def add_request(self, request: ApprovalRequest) -> None:
        aggregate = self.session.load_capsule(request.run_id, for_update=True)
        if request.id in aggregate.approval_requests or any(
            item.stage == request.stage
            and item.subject_version == request.subject_version
            and item.subject_digest == request.subject_digest
            for item in aggregate.approval_requests.values()
        ):
            raise ConflictError("Approval request already exists")
        aggregate.approval_requests[request.id] = request.model_copy(
            update={"status": ApprovalStatus.PENDING, "decision": None}
        )
        aggregate.mark_dirty()

    def add_decision(self, decision: ApprovalDecision) -> None:
        target = next(
            (
                aggregate
                for aggregate in self.session.iter_capsules()
                if decision.request_id in aggregate.approval_requests
            ),
            None,
        )
        if target is None:
            raise NotFoundError("Approval request not found")
        target = self.session.load_capsule(target.run.id, for_update=True)
        existing = target.approval_decisions.get(decision.request_id)
        if existing is not None and existing != decision:
            raise ConflictError("Approval request already has a decision")
        target.approval_decisions[decision.request_id] = decision
        target.mark_dirty()


class TaskCapsuleUnitOfWork:
    """Task-related filesystem UoW; later adapters may share ``session`` extensions."""

    def __init__(self, store: TaskCapsuleStore) -> None:
        self.store = store
        self.session = TaskCapsuleSession(store)
        self.projects = FilesystemProjectRepository(self.session)
        self.runs = FilesystemRunRepository(self.session)
        self.events = FilesystemEventRepository(self.session)
        self.runtime = FilesystemRuntimeRepository(self.session)
        self.approvals = FilesystemApprovalRepository(self.session)

    def __enter__(self) -> TaskCapsuleUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.session.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


def _list(document: dict[str, object], key: str) -> list[object]:
    value = document.get(key, [])
    if not isinstance(value, list):
        raise ConflictError(f"Task Capsule {key} state is invalid")
    return value


def _approval_view(
    request: ApprovalRequest, decisions: dict[UUID, ApprovalDecision]
) -> ApprovalRequest:
    decision = decisions.get(request.id)
    if decision is None:
        return request.model_copy(update={"status": ApprovalStatus.PENDING, "decision": None})
    status = (
        ApprovalStatus.APPROVED
        if decision.decision == ApprovalDecisionKind.APPROVE
        else ApprovalStatus.REJECTED
    )
    return request.model_copy(update={"status": status, "decision": decision})


def _load_project(layout: ProjectLayout) -> Project | None:
    path = layout.project / "identity.yaml"
    if not path.is_file():
        return None
    try:
        document = read_json_object(path)
        if document.pop("schema_version", None) != TASK_SCHEMA_VERSION:
            raise ConflictError("Unsupported project identity schema")
        relative_root = document.pop("repo_root", None)
        if relative_root != ".":
            raise ConflictError("Project identity contains a machine-specific root")
        project = Project.model_validate({**document, "repo_root": layout.root})
        if not layout.manifest.is_file():
            bootstrap_project_store(
                layout.root,
                project_id=project.id,
                project_name=project.name,
                initialized_at=project.created_at,
            )
        manifest = load_manifest(layout)
        manifest_project = manifest.get("project")
        if not isinstance(manifest_project, dict) or manifest_project.get("id") != str(project.id):
            raise ConflictError("Project identity does not match the manifest")
        return project
    except (OSError, FilesystemFormatError, ValidationError) as exc:
        raise ConflictError("Project identity is invalid") from exc


__all__ = [
    "FilesystemApprovalRepository",
    "FilesystemEventRepository",
    "FilesystemProjectRepository",
    "FilesystemRunRepository",
    "FilesystemRuntimeRepository",
    "TASK_SCHEMA_VERSION",
    "TaskCapsuleAggregate",
    "TaskCapsuleSession",
    "TaskCapsuleStore",
    "TaskCapsuleUnitOfWork",
]
