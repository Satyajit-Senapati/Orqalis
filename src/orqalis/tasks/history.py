"""Validated, root-scoped historical access to Task Capsules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast
from uuid import UUID

from pydantic import Field, JsonValue, ValidationError

from orqalis.context.models import ProjectContextPack
from orqalis.domain.base import Contract
from orqalis.domain.errors import ConflictError, InputError, NotFoundError
from orqalis.persistence.filesystem.io import (
    ensure_no_filesystem_links,
    read_json_object,
    read_jsonl,
)
from orqalis.persistence.filesystem.layout import load_manifest, resolve_project_root
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore

_TASK_ID = re.compile(r"ORQ-[0-9]{8}-[0-9]{4}\Z")
_TERMS = re.compile(r"[a-z0-9_]{2,}")


class TaskHistoryEntry(Contract):
    id: str
    run_id: UUID
    title: str
    status: str
    created_at: str
    completed_at: str | None = None
    branch: str | None = None
    starting_commit: str | None = None
    final_commit: str | None = None
    acceptance_result: str | None = None
    agents: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class TaskCapsuleView(Contract):
    task: TaskHistoryEntry
    request: str
    event_count: int = Field(ge=0)
    context: ProjectContextPack | None = None
    documents: dict[str, dict[str, JsonValue]]
    summary: str | None = None
    files: tuple[str, ...] = ()


class TaskHistoryService:
    """High-level historical reads without exposing arbitrary filesystem access."""

    def __init__(self, root: Path) -> None:
        self.root = resolve_project_root(root)
        self.store = TaskCapsuleStore.from_root(self.root)
        self.layout = self.store.layout
        load_manifest(self.layout)

    def list(self, limit: int = 100) -> tuple[TaskHistoryEntry, ...]:
        if not 1 <= limit <= 10_000:
            raise InputError("Task history limit must be between 1 and 10000")
        self.store.rebuild_index()
        document = read_json_object(self.layout.tasks / "index.json")
        raw = document.get("tasks")
        if not isinstance(raw, list):
            raise ConflictError("Task history index is invalid")
        entries = [self._entry_from_index(value) for value in raw]
        entries.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return tuple(entries[:limit])

    def get(self, task_id: str) -> TaskCapsuleView:
        capsule = self._capsule(task_id)
        metadata = read_json_object(capsule / "task.yaml")
        entry = self._entry(metadata, capsule)
        request_path = capsule / "request.md"
        if not request_path.is_file():
            raise ConflictError("Task Capsule request is missing")
        try:
            request = (
                ensure_no_filesystem_links(request_path).read_text(encoding="utf-8").rstrip("\n")
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise ConflictError("Task Capsule request is unreadable") from exc
        state = read_json_object(capsule / "execution" / "state.yaml")
        project = metadata.get("project")
        project_id = self._required(
            project.get("id") if isinstance(project, dict) else None,
            "project ID",
        )
        context = self._context(state, project_id)
        documents: dict[str, dict[str, JsonValue]] = {}
        for relative in (
            "goal/acceptance.yaml",
            "plan/dag.json",
            "execution/state.yaml",
            "review/acceptance-results.yaml",
            "changes/files.json",
            "delivery/commit.yaml",
            "delivery/push.yaml",
            "final/result.yaml",
        ):
            path = capsule.joinpath(*relative.split("/"))
            if path.is_file():
                value = read_json_object(path)
                documents[relative] = cast(dict[str, JsonValue], value)
        summary_path = capsule / "final" / "summary.md"
        try:
            summary = (
                ensure_no_filesystem_links(summary_path).read_text(encoding="utf-8")
                if summary_path.is_file()
                else None
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise ConflictError("Task Capsule final summary is unreadable") from exc
        events_path = capsule / "execution" / "events.jsonl"
        files = tuple(
            sorted(
                path.relative_to(capsule).as_posix()
                for path in capsule.rglob("*")
                if path.is_file() and not path.name.startswith(".")
            )
        )
        return TaskCapsuleView(
            task=entry,
            request=request,
            event_count=len(read_jsonl(events_path)),
            context=context,
            documents=documents,
            summary=summary,
            files=files,
        )

    def get_by_run(self, run_id: UUID) -> TaskCapsuleView:
        task_id = self.store.capsule_id(run_id)
        if task_id is None:
            raise NotFoundError("Task Capsule not found")
        return self.get(task_id)

    def related(self, query: str, limit: int = 5) -> tuple[TaskHistoryEntry, ...]:
        if not query.strip() or len(query) > 10_000:
            raise InputError("Task history query must contain 1..10000 characters")
        if not 1 <= limit <= 100:
            raise InputError("Related task limit must be between 1 and 100")
        terms = tuple(dict.fromkeys(_TERMS.findall(query.casefold())))
        ranked: list[tuple[int, TaskHistoryEntry]] = []
        for entry in self.list(limit=10_000):
            capsule = self.layout.task(entry.id)
            summary_path = capsule / "final" / "summary.md"
            summary = ""
            if summary_path.is_file():
                try:
                    summary = ensure_no_filesystem_links(summary_path).read_text(encoding="utf-8")[
                        :16_000
                    ]
                except (OSError, UnicodeDecodeError):
                    summary = ""
            text = f"{entry.title} {' '.join(entry.tags)} {summary}".casefold()
            score = sum(term in text for term in terms)
            if score:
                ranked.append((score, entry))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        return tuple(entry for _, entry in ranked[:limit])

    def _capsule(self, task_id: str) -> Path:
        if _TASK_ID.fullmatch(task_id) is None:
            raise InputError("Invalid Task Capsule ID")
        capsule = self.layout.task(task_id)
        if not capsule.is_dir():
            raise NotFoundError("Task Capsule not found")
        return capsule

    def _entry_from_index(self, value: object) -> TaskHistoryEntry:
        if not isinstance(value, dict):
            raise ConflictError("Task history index contains an invalid entry")
        task_id = value.get("id")
        if not isinstance(task_id, str):
            raise ConflictError("Task history index contains an invalid identity")
        return self._entry(value, self._capsule(task_id))

    def _entry(self, value: dict[str, object], capsule: Path) -> TaskHistoryEntry:
        project = value.get("project")
        project_data = project if isinstance(project, dict) else {}
        task_id = self._required(value.get("id"), "Task Capsule ID")
        if task_id != capsule.name:
            raise ConflictError("Task Capsule identity is inconsistent")
        try:
            run_id = UUID(self._required(value.get("run_id"), "run ID"))
        except ValueError as exc:
            raise ConflictError("Task Capsule run ID is invalid") from exc
        agents = self._agents(capsule)
        final_commit = self._nested_text(capsule / "delivery" / "commit.yaml", "commit_sha")
        acceptance = self._acceptance(capsule)
        tags_value = value.get("tags", [])
        tags = (
            tuple(item for item in tags_value if isinstance(item, str))
            if isinstance(tags_value, list)
            else ()
        )
        return TaskHistoryEntry(
            id=task_id,
            run_id=run_id,
            title=self._required(value.get("title"), "task title"),
            status=self._required(value.get("status"), "task status"),
            created_at=self._required(value.get("created_at"), "creation timestamp"),
            completed_at=self._optional(value.get("completed_at")),
            branch=self._optional(project_data.get("branch", value.get("branch"))),
            starting_commit=self._optional(
                project_data.get("starting_commit", value.get("starting_commit"))
            ),
            final_commit=final_commit,
            acceptance_result=acceptance,
            agents=agents,
            tags=tags,
        )

    @staticmethod
    def _context(state: dict[str, object], project_id: str) -> ProjectContextPack | None:
        extensions = state.get("extensions")
        value = extensions.get("context") if isinstance(extensions, dict) else None
        if value is None:
            return None
        try:
            pack = ProjectContextPack.model_validate(value)
        except ValidationError as exc:
            raise ConflictError("Task Capsule context stage is invalid") from exc
        if pack.project_id != project_id:
            raise ConflictError("Task Capsule context belongs to another project")
        return pack

    @staticmethod
    def _agents(capsule: Path) -> tuple[str, ...]:
        root = capsule / "execution" / "agents"
        if not root.is_dir():
            return ()
        values: set[str] = set()
        for path in root.glob("*/session.yaml"):
            document = read_json_object(path)
            role = document.get("role")
            provider = document.get("provider")
            if isinstance(role, str) and role:
                values.add(role)
            elif isinstance(provider, str) and provider:
                values.add(provider)
        return tuple(sorted(values))

    @staticmethod
    def _nested_text(path: Path, key: str) -> str | None:
        if not path.is_file():
            return None
        value = read_json_object(path).get(key)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _acceptance(capsule: Path) -> str | None:
        path = capsule / "review" / "acceptance-results.yaml"
        if not path.is_file():
            return None
        document = read_json_object(path)
        criteria = document.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            return None
        statuses = {
            item.get("status")
            for item in criteria
            if isinstance(item, dict) and isinstance(item.get("status"), str)
        }
        if "FAIL" in statuses:
            return "FAIL"
        if statuses == {"PASS"} and len(statuses) == 1:
            return "PASS"
        return "PENDING"

    @staticmethod
    def _required(value: object, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise ConflictError(f"Task Capsule {label} is invalid")
        return value

    @staticmethod
    def _optional(value: object) -> str | None:
        return value if isinstance(value, str) and value else None


__all__ = ["TaskCapsuleView", "TaskHistoryEntry", "TaskHistoryService"]
