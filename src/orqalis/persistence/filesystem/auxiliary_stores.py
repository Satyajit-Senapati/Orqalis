"""Filesystem adapters for run-scoped execution, provider, and delivery state."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import UUID

from pydantic import ValidationError

from orqalis.domain.artifact import Artifact, Finding
from orqalis.domain.base import Entity
from orqalis.domain.delivery import ChangeReport, FinalValidation, GitDelivery
from orqalis.domain.errors import ConflictError
from orqalis.domain.execution import ReviewRecord, RunWorkspace, ToolInvocation
from orqalis.domain.provider import ProviderExecution
from orqalis.persistence.filesystem.task_store import TaskCapsuleSession

AUXILIARY_SCHEMA_VERSION = 1
_EXECUTION_NAMESPACE = "execution"
_PROVIDER_NAMESPACE = "providers"
_DELIVERY_NAMESPACE = "delivery"


def _document(session: TaskCapsuleSession, run_id: UUID, namespace: str) -> dict[str, object]:
    raw = session.extension(run_id, namespace)
    if raw is None:
        return {"schema_version": AUXILIARY_SCHEMA_VERSION}
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ConflictError(f"Task Capsule {namespace} extension is invalid")
    document = cast(dict[str, object], raw)
    if document.get("schema_version") != AUXILIARY_SCHEMA_VERSION:
        raise ConflictError(f"Unsupported Task Capsule {namespace} extension schema")
    return document


def _entity_run_id(value: Entity) -> UUID:
    run_id = value.__dict__.get("run_id")
    if not isinstance(run_id, UUID):
        raise ConflictError(f"{type(value).__name__} has no valid run identity")
    return run_id


def _models[EntityT: Entity](
    document: dict[str, object],
    key: str,
    model: type[EntityT],
    *,
    run_id: UUID,
) -> list[EntityT]:
    raw = document.get(key, [])
    if not isinstance(raw, list):
        raise ConflictError(f"Task Capsule {key} state is invalid")
    try:
        values = [model.model_validate(value) for value in raw]
    except ValidationError as exc:
        raise ConflictError(f"Task Capsule {key} state is invalid") from exc
    seen: set[UUID] = set()
    for value in values:
        if cast(object, getattr(value, "run_id", None)) != run_id or value.id in seen:
            raise ConflictError(f"Task Capsule {key} state is inconsistent")
        seen.add(value.id)
    return values


def _save_models(
    session: TaskCapsuleSession,
    run_id: UUID,
    namespace: str,
    document: dict[str, object],
    key: str,
    values: Sequence[Entity],
) -> None:
    document[key] = [value.model_dump(mode="json") for value in values]
    session.save_extension(run_id, namespace, document)


def _replace[EntityT: Entity](values: list[EntityT], value: EntityT) -> None:
    for index, existing in enumerate(values):
        if existing.id == value.id:
            values[index] = value
            return
    values.append(value)


def _find[EntityT: Entity](
    session: TaskCapsuleSession,
    namespace: str,
    key: str,
    model: type[EntityT],
    identifier: UUID,
) -> tuple[UUID, EntityT] | None:
    found: tuple[UUID, EntityT] | None = None
    for aggregate in session.iter_capsules():
        document = _document(session, aggregate.run.id, namespace)
        for value in _models(document, key, model, run_id=aggregate.run.id):
            if value.id != identifier:
                continue
            if found is not None:
                raise ConflictError(f"Task Capsule {key} identity is duplicated")
            found = (aggregate.run.id, value)
    return found


def _ensure_upsert_owner[EntityT: Entity](
    session: TaskCapsuleSession,
    namespace: str,
    key: str,
    model: type[EntityT],
    value: EntityT,
) -> None:
    existing = _find(session, namespace, key, model, value.id)
    if existing is not None and existing[0] != _entity_run_id(value):
        raise ConflictError(f"{model.__name__} identity belongs to another run")


def _canonical_workspace_path(path: Path, root: Path) -> Path:
    expanded = path.expanduser()
    candidate = expanded if expanded.is_absolute() else root / expanded
    return candidate.resolve(strict=False)


def _dump_workspace(workspace: RunWorkspace, root: Path) -> dict[str, object]:
    path = _canonical_workspace_path(workspace.path, root)
    canonical_root = root.resolve(strict=False)
    if path == canonical_root or path.is_relative_to(canonical_root):
        relative = path.relative_to(canonical_root)
        stored_path = {
            "scope": "project",
            "value": relative.as_posix() if relative.parts else ".",
        }
    else:
        stored_path = {"scope": "absolute", "value": str(path)}
    return {**workspace.model_dump(mode="json", exclude={"path"}), "path": stored_path}


def _load_workspace(value: object, root: Path, run_id: UUID) -> RunWorkspace:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ConflictError("Task Capsule workspace state is invalid")
    raw = cast(dict[str, object], value)
    path_value = raw.get("path")
    if not isinstance(path_value, dict):
        raise ConflictError("Task Capsule workspace path is invalid")
    scope, stored = path_value.get("scope"), path_value.get("value")
    if not isinstance(stored, str):
        raise ConflictError("Task Capsule workspace path is invalid")
    canonical_root = root.resolve(strict=False)
    if scope == "project":
        relative = PurePosixPath(stored)
        if stored != "." and (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ConflictError("Task Capsule workspace path is unsafe")
        parts = () if stored == "." else relative.parts
        path = canonical_root.joinpath(*parts).resolve(strict=False)
        if path != canonical_root and not path.is_relative_to(canonical_root):
            raise ConflictError("Task Capsule workspace path escapes the project")
    elif scope == "absolute":
        candidate = Path(stored).expanduser()
        if not candidate.is_absolute():
            raise ConflictError("Task Capsule external workspace path is invalid")
        path = candidate.resolve(strict=False)
    else:
        raise ConflictError("Task Capsule workspace path scope is invalid")
    try:
        workspace = RunWorkspace.model_validate(
            {**{key: item for key, item in raw.items() if key != "path"}, "path": path}
        )
    except ValidationError as exc:
        raise ConflictError("Task Capsule workspace state is invalid") from exc
    if workspace.run_id != run_id:
        raise ConflictError("Task Capsule workspace belongs to another run")
    return workspace


class FilesystemExecutionRepository:
    """Execution state stored transactionally in the owning Task Capsule."""

    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def try_run_lock(self, run_id: UUID) -> bool:
        return self.session.try_run_lock(run_id)

    def workspace(self, run_id: UUID) -> RunWorkspace | None:
        value = _document(self.session, run_id, _EXECUTION_NAMESPACE).get("workspace")
        return None if value is None else _load_workspace(value, self.session.layout.root, run_id)

    def save_workspace(self, workspace: RunWorkspace) -> None:
        document = _document(self.session, workspace.run_id, _EXECUTION_NAMESPACE)
        document["workspace"] = _dump_workspace(workspace, self.session.layout.root)
        self.session.save_extension(workspace.run_id, _EXECUTION_NAMESPACE, document)

    def tool(self, invocation_id: UUID) -> ToolInvocation | None:
        found = _find(
            self.session,
            _EXECUTION_NAMESPACE,
            "tools",
            ToolInvocation,
            invocation_id,
        )
        return found[1] if found else None

    def save_tool(self, invocation: ToolInvocation) -> None:
        _ensure_upsert_owner(
            self.session, _EXECUTION_NAMESPACE, "tools", ToolInvocation, invocation
        )
        document = _document(self.session, invocation.run_id, _EXECUTION_NAMESPACE)
        values = _models(document, "tools", ToolInvocation, run_id=invocation.run_id)
        if any(
            item.id != invocation.id
            and item.provider_invocation_id == invocation.provider_invocation_id
            and item.call_id == invocation.call_id
            for item in values
        ):
            raise ConflictError("Provider tool call identity already exists")
        _replace(values, invocation)
        _save_models(
            self.session,
            invocation.run_id,
            _EXECUTION_NAMESPACE,
            document,
            "tools",
            values,
        )

    def tools(self, run_id: UUID) -> tuple[ToolInvocation, ...]:
        values = _models(
            _document(self.session, run_id, _EXECUTION_NAMESPACE),
            "tools",
            ToolInvocation,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: (item.started_at, str(item.id))))

    def save_review(self, review: ReviewRecord) -> None:
        if (
            _find(self.session, _EXECUTION_NAMESPACE, "reviews", ReviewRecord, review.id)
            is not None
        ):
            raise ConflictError("Review identity already exists")
        document = _document(self.session, review.run_id, _EXECUTION_NAMESPACE)
        values = _models(document, "reviews", ReviewRecord, run_id=review.run_id)
        values.append(review)
        _save_models(
            self.session,
            review.run_id,
            _EXECUTION_NAMESPACE,
            document,
            "reviews",
            values,
        )

    def reviews(self, run_id: UUID) -> tuple[ReviewRecord, ...]:
        values = _models(
            _document(self.session, run_id, _EXECUTION_NAMESPACE),
            "reviews",
            ReviewRecord,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: (item.created_at, str(item.id))))


class FilesystemProviderRepository:
    """Provider invocation history stored with the run that initiated it."""

    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def get(self, invocation_id: UUID) -> ProviderExecution | None:
        found = _find(
            self.session,
            _PROVIDER_NAMESPACE,
            "invocations",
            ProviderExecution,
            invocation_id,
        )
        return found[1] if found else None

    def save(self, invocation: ProviderExecution) -> None:
        _ensure_upsert_owner(
            self.session,
            _PROVIDER_NAMESPACE,
            "invocations",
            ProviderExecution,
            invocation,
        )
        document = _document(self.session, invocation.run_id, _PROVIDER_NAMESPACE)
        values = _models(document, "invocations", ProviderExecution, run_id=invocation.run_id)
        if any(
            item.id != invocation.id and item.idempotency_key == invocation.idempotency_key
            for item in values
        ):
            raise ConflictError("Provider idempotency key already exists")
        _replace(values, invocation)
        _save_models(
            self.session,
            invocation.run_id,
            _PROVIDER_NAMESPACE,
            document,
            "invocations",
            values,
        )

    def list(self, run_id: UUID) -> tuple[ProviderExecution, ...]:
        values = _models(
            _document(self.session, run_id, _PROVIDER_NAMESPACE),
            "invocations",
            ProviderExecution,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: (item.started_at, str(item.id))))


class FilesystemDeliveryRepository:
    """Change review, validation, artifacts, findings, and Git delivery state."""

    def __init__(self, session: TaskCapsuleSession) -> None:
        self.session = session

    def guardians(self, run_id: UUID) -> tuple[ChangeReport, ...]:
        values = _models(
            _document(self.session, run_id, _DELIVERY_NAMESPACE),
            "guardians",
            ChangeReport,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: (item.created_at, str(item.id))))

    def save_guardian(self, report: ChangeReport) -> None:
        if (
            _find(self.session, _DELIVERY_NAMESPACE, "guardians", ChangeReport, report.id)
            is not None
        ):
            raise ConflictError("Change report identity already exists")
        document = _document(self.session, report.run_id, _DELIVERY_NAMESPACE)
        reports = _models(document, "guardians", ChangeReport, run_id=report.run_id)
        findings = _models(document, "findings", Finding, run_id=report.run_id)
        for finding in report.findings:
            _ensure_upsert_owner(self.session, _DELIVERY_NAMESPACE, "findings", Finding, finding)
            _replace(findings, finding)
        reports.append(report)
        document["guardians"] = [item.model_dump(mode="json") for item in reports]
        document["findings"] = [item.model_dump(mode="json") for item in findings]
        self.session.save_extension(report.run_id, _DELIVERY_NAMESPACE, document)

    def validations(self, run_id: UUID) -> tuple[FinalValidation, ...]:
        values = _models(
            _document(self.session, run_id, _DELIVERY_NAMESPACE),
            "validations",
            FinalValidation,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: (item.created_at, str(item.id))))

    def save_validation(self, validation: FinalValidation) -> None:
        if (
            _find(
                self.session,
                _DELIVERY_NAMESPACE,
                "validations",
                FinalValidation,
                validation.id,
            )
            is not None
        ):
            raise ConflictError("Final validation identity already exists")
        document = _document(self.session, validation.run_id, _DELIVERY_NAMESPACE)
        values = _models(document, "validations", FinalValidation, run_id=validation.run_id)
        values.append(validation)
        _save_models(
            self.session,
            validation.run_id,
            _DELIVERY_NAMESPACE,
            document,
            "validations",
            values,
        )

    def get(self, run_id: UUID) -> GitDelivery | None:
        document = _document(self.session, run_id, _DELIVERY_NAMESPACE)
        value = document.get("git_delivery")
        if value is None:
            return None
        try:
            delivery = GitDelivery.model_validate(value)
        except ValidationError as exc:
            raise ConflictError("Task Capsule Git delivery state is invalid") from exc
        if delivery.run_id != run_id:
            raise ConflictError("Task Capsule Git delivery belongs to another run")
        return delivery

    def save(self, delivery: GitDelivery) -> None:
        document = _document(self.session, delivery.run_id, _DELIVERY_NAMESPACE)
        existing = self.get(delivery.run_id)
        if existing is not None and existing.id != delivery.id:
            raise ConflictError("Run already has a Git delivery identity")
        document["git_delivery"] = delivery.model_dump(mode="json")
        self.session.save_extension(delivery.run_id, _DELIVERY_NAMESPACE, document)

    def artifacts(self, run_id: UUID) -> tuple[Artifact, ...]:
        values = _models(
            _document(self.session, run_id, _DELIVERY_NAMESPACE),
            "artifacts",
            Artifact,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: item.created_at))

    def save_artifact(self, artifact: Artifact) -> None:
        _ensure_upsert_owner(self.session, _DELIVERY_NAMESPACE, "artifacts", Artifact, artifact)
        document = _document(self.session, artifact.run_id, _DELIVERY_NAMESPACE)
        values = _models(document, "artifacts", Artifact, run_id=artifact.run_id)
        _replace(values, artifact)
        _save_models(
            self.session,
            artifact.run_id,
            _DELIVERY_NAMESPACE,
            document,
            "artifacts",
            values,
        )

    def findings(self, run_id: UUID) -> tuple[Finding, ...]:
        values = _models(
            _document(self.session, run_id, _DELIVERY_NAMESPACE),
            "findings",
            Finding,
            run_id=run_id,
        )
        return tuple(sorted(values, key=lambda item: item.created_at))

    def save_finding(self, finding: Finding) -> None:
        _ensure_upsert_owner(self.session, _DELIVERY_NAMESPACE, "findings", Finding, finding)
        document = _document(self.session, finding.run_id, _DELIVERY_NAMESPACE)
        values = _models(document, "findings", Finding, run_id=finding.run_id)
        _replace(values, finding)
        _save_models(
            self.session,
            finding.run_id,
            _DELIVERY_NAMESPACE,
            document,
            "findings",
            values,
        )


__all__ = [
    "AUXILIARY_SCHEMA_VERSION",
    "FilesystemDeliveryRepository",
    "FilesystemExecutionRepository",
    "FilesystemProviderRepository",
]
