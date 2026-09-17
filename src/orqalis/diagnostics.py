"""Diagnostics and supported schema migration for one local project store."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, ValidationError

from orqalis.domain.base import Contract
from orqalis.graph.models import GraphManifest, ProjectGraph
from orqalis.memory.curated import CuratedMemoryStore
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    read_json_object,
    read_jsonl,
)
from orqalis.persistence.filesystem.layout import (
    ProjectLayout,
    ensure_current_schema,
    load_manifest,
    resolve_project_root,
)

_CAPSULE_ID = re.compile(r"ORQ-[0-9]{8}-[0-9]{4}\Z")


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class DoctorCheck(Contract):
    name: str
    status: CheckStatus
    message: str


class DoctorReport(Contract):
    project_root: Path
    schema_version: int | None = None
    checks: tuple[DoctorCheck, ...]
    healthy: bool
    task_capsules: int = Field(default=0, ge=0)
    memory_records: int = Field(default=0, ge=0)
    graph_nodes: int = Field(default=0, ge=0)


def _check(name: str, status: CheckStatus, message: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=status, message=message)


def _store_is_writable(layout: ProjectLayout) -> bool:
    """Probe the actual store instead of trusting platform-dependent mode checks."""

    path = layout.contained(layout.store / f".doctor-write.{uuid4().hex}.tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        return False
    try:
        try:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        except OSError:
            writable = False
        else:
            writable = True
    finally:
        os.close(descriptor)
    try:
        path.unlink()
    except OSError:
        return False
    return writable


def _validate_identity(layout: ProjectLayout, manifest: dict[str, object]) -> DoctorCheck:
    path = layout.project / "identity.yaml"
    if not path.exists():
        return _check(
            "project_identity",
            CheckStatus.WARN,
            "Project identity has not been generated yet",
        )
    identity = read_json_object(path)
    manifest_project = manifest.get("project")
    expected = manifest_project.get("id") if isinstance(manifest_project, dict) else None
    if identity.get("repo_root") != ".":
        raise ValueError("Project identity contains a machine-specific repository path")
    if identity.get("id") != expected:
        raise ValueError("Project identity does not match the manifest")
    UUID(str(identity.get("id")))
    return _check("project_identity", CheckStatus.PASS, "Project identity is root-relative")


def _validate_tasks(layout: ProjectLayout) -> tuple[DoctorCheck, int]:
    if not layout.tasks.exists():
        return (
            _check("tasks", CheckStatus.WARN, "No Task Capsules have been created"),
            0,
        )
    count = 0
    for capsule in sorted(layout.tasks.iterdir()):
        if not capsule.is_dir() or _CAPSULE_ID.fullmatch(capsule.name) is None:
            continue
        document = read_json_object(capsule / "task.yaml")
        if document.get("id") != capsule.name:
            raise ValueError(f"Task Capsule identity mismatch: {capsule.name}")
        UUID(str(document.get("run_id")))
        events_path = capsule / "execution" / "events.jsonl"
        events = read_jsonl(events_path)
        sequences = [record.get("sequence") for record in events]
        if sequences != list(range(1, len(events) + 1)):
            raise ValueError(f"Task Capsule event sequence is invalid: {capsule.name}")
        count += 1
    index = layout.tasks / "index.json"
    status = CheckStatus.PASS if index.is_file() else CheckStatus.WARN
    suffix = "task index is present" if index.is_file() else "task index can be rebuilt"
    return _check("tasks", status, f"Validated {count} Task Capsules; {suffix}"), count


def _validate_memory(layout: ProjectLayout) -> tuple[DoctorCheck, int]:
    records = CuratedMemoryStore(layout).list()
    return (
        _check("memory", CheckStatus.PASS, f"Validated {len(records)} curated records"),
        len(records),
    )


def _validate_graph(layout: ProjectLayout) -> tuple[DoctorCheck, int]:
    directory = layout.memory / "graph"
    graph_path, manifest_path = directory / "graph.json", directory / "manifest.json"
    if not graph_path.exists() and not manifest_path.exists():
        return _check("graph", CheckStatus.WARN, "Repository graph has not been built"), 0
    if not graph_path.is_file() or not manifest_path.is_file():
        raise ValueError("Repository graph and manifest must exist together")
    graph = ProjectGraph.model_validate(read_json_object(graph_path))
    GraphManifest.model_validate(read_json_object(manifest_path))
    node_ids = {node.id for node in graph.nodes}
    if len(node_ids) != len(graph.nodes):
        raise ValueError("Repository graph contains duplicate node identities")
    if any(
        edge.source_id not in node_ids or edge.target_id not in node_ids for edge in graph.edges
    ):
        raise ValueError("Repository graph contains a dangling relationship")
    return _check("graph", CheckStatus.PASS, f"Validated {len(graph.nodes)} graph nodes"), len(
        graph.nodes
    )


def _validate_containment(layout: ProjectLayout) -> DoctorCheck:
    for path in layout.store.rglob("*"):
        if path.is_symlink():
            layout.contained(path)
    return _check("containment", CheckStatus.PASS, "Project storage remains root-scoped")


def diagnose_project(root: Path | None = None) -> DoctorReport:
    """Migrate supported schemas, then validate canonical and rebuildable state."""

    resolved = resolve_project_root(root)
    layout = ProjectLayout(resolved)
    checks: list[DoctorCheck] = []
    schema_version: int | None = None
    task_count = memory_count = graph_nodes = 0

    if not layout.store.is_dir():
        checks.append(
            _check("store", CheckStatus.FAIL, "Project is not initialized; run orqalis init")
        )
        return DoctorReport(project_root=resolved, checks=tuple(checks), healthy=False)

    try:
        backup = ensure_current_schema(layout)
        manifest = load_manifest(layout)
        raw_schema_version = manifest["schema_version"]
        if isinstance(raw_schema_version, bool) or not isinstance(raw_schema_version, int):
            raise ValueError("Manifest schema version is invalid")
        schema_version = raw_schema_version
        checks.append(
            _check(
                "manifest",
                CheckStatus.PASS,
                (
                    f"Migrated filesystem schema 1 to supported schema {schema_version}"
                    if backup is not None
                    else f"Filesystem schema {schema_version} is supported"
                ),
            )
        )
    except Exception as exc:
        checks.append(_check("manifest", CheckStatus.FAIL, str(exc)))
        return DoctorReport(project_root=resolved, checks=tuple(checks), healthy=False)

    validations: tuple[tuple[str, Callable[[], DoctorCheck]], ...] = (
        ("config", lambda: _validate_config(layout)),
        ("project_identity", lambda: _validate_identity(layout, manifest)),
        ("containment", lambda: _validate_containment(layout)),
    )
    for name, validation in validations:
        try:
            checks.append(validation())
        except (OSError, ValueError, FilesystemFormatError, ValidationError) as exc:
            checks.append(_check(name, CheckStatus.FAIL, str(exc)))

    try:
        task_check, task_count = _validate_tasks(layout)
        checks.append(task_check)
    except (OSError, ValueError, FilesystemFormatError, ValidationError) as exc:
        checks.append(_check("tasks", CheckStatus.FAIL, str(exc)))

    try:
        memory_check, memory_count = _validate_memory(layout)
        checks.append(memory_check)
    except (OSError, ValueError, FilesystemFormatError, ValidationError) as exc:
        checks.append(_check("memory", CheckStatus.FAIL, str(exc)))

    try:
        graph_check, graph_nodes = _validate_graph(layout)
        checks.append(graph_check)
    except (OSError, ValueError, FilesystemFormatError, ValidationError) as exc:
        checks.append(_check("graph", CheckStatus.FAIL, str(exc)))

    if not layout.index.exists():
        checks.append(_check("index", CheckStatus.WARN, "Derived index can be rebuilt"))
    else:
        checks.append(_check("index", CheckStatus.PASS, "Derived index directory is present"))
    if not layout.cache.exists():
        checks.append(_check("cache", CheckStatus.WARN, "Parser/search cache can be regenerated"))
    else:
        checks.append(_check("cache", CheckStatus.PASS, "Rebuildable cache directory is present"))
    writable = _store_is_writable(layout)
    checks.append(
        _check(
            "writable",
            CheckStatus.PASS if writable else CheckStatus.FAIL,
            "Project store is writable" if writable else "Project store is read-only",
        )
    )
    return DoctorReport(
        project_root=resolved,
        schema_version=schema_version,
        checks=tuple(checks),
        healthy=not any(check.status == CheckStatus.FAIL for check in checks),
        task_capsules=task_count,
        memory_records=memory_count,
        graph_nodes=graph_nodes,
    )


def _validate_config(layout: ProjectLayout) -> DoctorCheck:
    document = read_json_object(layout.config)
    if document.get("schema_version") != 1:
        raise ValueError("Unsupported project configuration schema")
    return _check("config", CheckStatus.PASS, "Project configuration is valid")


__all__ = [
    "CheckStatus",
    "DoctorCheck",
    "DoctorReport",
    "diagnose_project",
]
