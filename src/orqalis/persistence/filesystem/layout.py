"""Project-root resolution, layout bootstrap, and filesystem schema management."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from orqalis.domain.errors import ConflictError, InputError, NotFoundError, PolicyDeniedError
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    atomic_write_bytes,
    atomic_write_json,
    ensure_no_filesystem_links,
    read_json_object,
)
from orqalis.persistence.filesystem.locking import FileLock

CURRENT_SCHEMA_VERSION = 2
PROJECT_ROOT_ENV = "ORQALIS_PROJECT_ROOT"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

# This file lives inside .orqalis. Patterns are deliberately selective: durable
# project knowledge and task summaries remain eligible for Git tracking.
DEFAULT_STORE_GITIGNORE = """# Orqalis derived and machine-local data
/cache/
/index/
/runtime/
/memory/graph/graph.html
/tasks/*/execution/events.jsonl
**/*.lock
**/.*.tmp
"""


class ProjectRootError(InputError):
    """The requested project root is unavailable or unsafe."""


class ManifestNotFoundError(NotFoundError):
    """The selected repository has not been initialized by Orqalis."""


class ManifestValidationError(InputError):
    """The project manifest is malformed."""


class SchemaMigrationRequired(ConflictError):
    """The project store uses an older, migratable schema."""


class UnsupportedSchemaError(ConflictError):
    """The project store schema cannot be read by this Orqalis version."""


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve(strict=False))

    @property
    def store(self) -> Path:
        return ensure_no_filesystem_links(self.root / ".orqalis")

    def _storage_path(self, *parts: str) -> Path:
        store = self.store
        candidate = ensure_no_filesystem_links(store.joinpath(*parts))
        resolved_store = store.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
        if resolved_candidate != resolved_store and not resolved_candidate.is_relative_to(
            resolved_store
        ):
            raise PolicyDeniedError("Project storage path escapes the selected repository")
        return candidate

    @property
    def orqalis(self) -> Path:
        return self.store

    @property
    def manifest(self) -> Path:
        return self._storage_path("manifest.yaml")

    @property
    def config(self) -> Path:
        return self._storage_path("config.yaml")

    @property
    def gitignore(self) -> Path:
        return self._storage_path(".gitignore")

    @property
    def project(self) -> Path:
        return self._storage_path("project")

    @property
    def memory(self) -> Path:
        return self._storage_path("memory")

    @property
    def tasks(self) -> Path:
        return self._storage_path("tasks")

    @property
    def index(self) -> Path:
        return self._storage_path("index")

    @property
    def runtime(self) -> Path:
        return self._storage_path("runtime")

    @property
    def cache(self) -> Path:
        return self._storage_path("cache")

    @property
    def locks(self) -> Path:
        return self._storage_path("runtime", "locks")

    def task(self, task_id: str) -> Path:
        return self._storage_path("tasks", _safe_name(task_id, "task ID"))

    def lock(self, name: str) -> Path:
        value = _safe_name(name, "lock name")
        filename = value if value.endswith(".lock") else f"{value}.lock"
        return self._storage_path("runtime", "locks", filename)

    def contained(self, path: Path) -> Path:
        candidate = ensure_no_filesystem_links(path)
        store = self.store.resolve(strict=False)
        resolved = candidate.resolve(strict=False)
        if resolved != store and not resolved.is_relative_to(store):
            raise PolicyDeniedError("Project storage path escapes the selected repository")
        return candidate


def _safe_name(value: str, label: str) -> str:
    if not _NAME.fullmatch(value):
        raise PolicyDeniedError(f"Invalid {label}")
    return value


def _directory(path: Path, label: str) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ProjectRootError(f"{label} is unavailable") from exc
    if not resolved.is_dir():
        raise ProjectRootError(f"{label} must be a directory")
    return resolved


def _git_root(cwd: Path) -> Path | None:
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            env=environment,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    try:
        root = Path(result.stdout.decode("utf-8").strip()).resolve(strict=True)
    except (OSError, UnicodeDecodeError):
        return None
    return root if root.is_dir() and (cwd == root or cwd.is_relative_to(root)) else None


def resolve_project_root(explicit: Path | None = None, *, cwd: Path | None = None) -> Path:
    """Resolve explicit root, configured root, Git root, then current directory.

    Explicit and ``ORQALIS_PROJECT_ROOT`` paths are authoritative selections. If
    either is invalid, resolution fails instead of silently falling through to a
    different directory. A selected path inside a Git worktree is normalized to
    that worktree's root so canonical state cannot be split across nested stores.
    """

    if explicit is not None:
        selected = _directory(explicit, "Explicit project root")
        return _git_root(selected) or selected
    configured = os.environ.get(PROJECT_ROOT_ENV)
    if configured is not None:
        if not configured.strip():
            raise ProjectRootError(f"{PROJECT_ROOT_ENV} must name a project directory")
        selected = _directory(Path(configured), "Configured project root")
        return _git_root(selected) or selected
    working = _directory(cwd or Path.cwd(), "Working directory")
    return _git_root(working) or working


def _git_metadata(root: Path) -> tuple[str | None, str | None]:
    if _git_root(root) != root:
        return None, None
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})

    def run(*arguments: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments],
                env=environment,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode:
            return None
        try:
            return result.stdout.decode("utf-8").strip() or None
        except UnicodeDecodeError:
            return None

    return run("rev-parse", "--verify", "HEAD"), run("symbolic-ref", "--short", "-q", "HEAD")


def _default_config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "context": {"max_chars": 20_000},
        "git": {
            "track_execution_events": False,
            "track_generated_graph_html": False,
            "track_project_memory": True,
            "track_task_history": True,
        },
        "memory": {"durable_updates": "review"},
    }


def load_project_config(layout: ProjectLayout) -> dict[str, object]:
    """Load and validate the project-local configuration document."""

    try:
        document = read_json_object(layout.config)
    except (OSError, FilesystemFormatError) as exc:
        raise ManifestValidationError("Project config is not valid JSON/YAML") from exc
    git = document.get("git", {})
    if not isinstance(git, dict):
        raise ManifestValidationError("Project config git must be an object")
    defaults = _default_config()["git"]
    if not isinstance(defaults, dict):  # pragma: no cover - internal invariant
        raise AssertionError("Default Git configuration must be an object")
    for key, default in defaults.items():
        value = git.get(key, default)
        if not isinstance(value, bool):
            raise ManifestValidationError(f"Project config git.{key} must be a boolean")
    return document


def render_store_gitignore(config: dict[str, object]) -> str:
    """Render the derived-data tracking policy from ``config.yaml``."""

    git_value = config.get("git", {})
    if not isinstance(git_value, dict):
        raise ManifestValidationError("Project config git must be an object")
    defaults = _default_config()["git"]
    if not isinstance(defaults, dict):  # pragma: no cover - internal invariant
        raise AssertionError("Default Git configuration must be an object")

    policy: dict[str, bool] = {}
    for key, default in defaults.items():
        value = git_value.get(key, default)
        if not isinstance(value, bool):
            raise ManifestValidationError(f"Project config git.{key} must be a boolean")
        policy[key] = value

    lines = [
        "# Orqalis derived and machine-local data",
        "/cache/",
        "/index/",
        "/runtime/",
    ]
    if not policy["track_project_memory"]:
        lines.append("/memory/")
    elif not policy["track_generated_graph_html"]:
        lines.append("/memory/graph/graph.html")
    if not policy["track_task_history"]:
        lines.append("/tasks/")
    elif not policy["track_execution_events"]:
        lines.append("/tasks/*/execution/events.jsonl")
    lines.extend(("**/*.lock", "**/.*.tmp"))
    return "\n".join(lines) + "\n"


def _sync_store_gitignore(layout: ProjectLayout) -> None:
    config = load_project_config(layout)
    content = render_store_gitignore(config).encode("utf-8")
    if not layout.gitignore.is_file() or layout.gitignore.read_bytes() != content:
        atomic_write_bytes(layout.gitignore, content)


def _manifest(
    root: Path,
    project_id: UUID,
    project_name: str,
    initialized_at: datetime,
) -> dict[str, object]:
    commit, branch = _git_metadata(root)
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project": {"id": str(project_id), "name": project_name},
        "storage": {"backend": "filesystem"},
        "initialized_at": initialized_at.astimezone(UTC).isoformat(),
        "graph": {
            "schema_version": 1,
            "indexed_commit": commit,
            "indexed_branch": branch,
        },
        "memory": {"schema_version": 1},
        "tasks": {"schema_version": 1},
    }


def bootstrap_project_store(
    root: Path,
    *,
    project_id: UUID | None = None,
    project_name: str | None = None,
    initialized_at: datetime | None = None,
) -> ProjectLayout:
    """Create the minimal schema-v2 project store without empty placeholder trees.

    ``manifest.yaml`` and ``config.yaml`` contain formatted JSON. JSON is valid
    YAML 1.2, avoids a required YAML runtime dependency, and remains human-readable.
    """

    resolved = _directory(root, "Project root")
    layout = ProjectLayout(resolved)
    layout.store.mkdir(parents=False, exist_ok=True)
    with FileLock(layout.contained(layout.store / ".bootstrap.lock")):
        if layout.manifest.exists():
            # Opening an existing initialized project is the supported migration
            # boundary. The migrator validates and backs up schema 1 before it
            # publishes the schema-2 manifest as the final atomic write.
            ensure_current_schema(layout)
        else:
            name = project_name or resolved.name
            if not name.strip():
                raise ManifestValidationError("Project name must not be empty")
            document = _manifest(
                resolved,
                project_id or uuid4(),
                name,
                initialized_at or datetime.now(UTC),
            )
            validate_manifest(document)
            if not layout.config.exists():
                atomic_write_json(layout.config, _default_config())
            _sync_store_gitignore(layout)
            # The manifest is written last: its presence marks a completed bootstrap.
            atomic_write_json(layout.manifest, document)
        if not layout.config.exists():
            atomic_write_json(layout.config, _default_config())
        _sync_store_gitignore(layout)
    return layout


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ManifestValidationError(f"Manifest {label} must be an object")
    return value


def _positive_version(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ManifestValidationError(f"Manifest {label} must be a positive integer")
    return value


def _validate_common(document: dict[str, object]) -> None:
    project = _mapping(document.get("project"), "project")
    project_id = project.get("id")
    name = project.get("name")
    try:
        UUID(project_id) if isinstance(project_id, str) else None
    except ValueError as exc:
        raise ManifestValidationError("Manifest project.id must be a UUID") from exc
    if not isinstance(project_id, str):
        raise ManifestValidationError("Manifest project.id must be a UUID")
    if not isinstance(name, str) or not name.strip():
        raise ManifestValidationError("Manifest project.name must not be empty")
    initialized = document.get("initialized_at")
    if not isinstance(initialized, str):
        raise ManifestValidationError("Manifest initialized_at must be a timestamp")
    try:
        parsed = datetime.fromisoformat(initialized)
    except ValueError as exc:
        raise ManifestValidationError("Manifest initialized_at must be a timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestValidationError("Manifest initialized_at must include a timezone")


def validate_manifest(document: dict[str, object]) -> dict[str, object]:
    version = document.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ManifestValidationError("Manifest schema_version must be an integer")
    if version == 1:
        raise SchemaMigrationRequired("Project store schema 1 requires migration to schema 2")
    if version != CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaError(f"Unsupported project store schema: {version}")
    _validate_common(document)
    storage = _mapping(document.get("storage"), "storage")
    if storage.get("backend") != "filesystem":
        raise ManifestValidationError("Manifest storage backend must be filesystem")
    graph = _mapping(document.get("graph"), "graph")
    memory = _mapping(document.get("memory"), "memory")
    tasks = _mapping(document.get("tasks"), "tasks")
    _positive_version(graph.get("schema_version"), "graph.schema_version")
    _positive_version(memory.get("schema_version"), "memory.schema_version")
    _positive_version(tasks.get("schema_version"), "tasks.schema_version")
    for field in ("indexed_commit", "indexed_branch"):
        if graph.get(field) is not None and not isinstance(graph.get(field), str):
            raise ManifestValidationError(f"Manifest graph.{field} must be text or null")
    return document


def load_manifest(layout: ProjectLayout) -> dict[str, object]:
    if not layout.manifest.is_file():
        raise ManifestNotFoundError("Project is not initialized; run orqalis init")
    try:
        document = read_json_object(layout.manifest)
    except FilesystemFormatError as exc:
        raise ManifestValidationError("Project manifest is not valid JSON/YAML") from exc
    return validate_manifest(document)


def update_graph_cursor(
    layout: ProjectLayout,
    indexed_commit: str | None,
    indexed_branch: str | None,
) -> None:
    """Synchronize the top-level project manifest after a graph/index refresh."""

    with FileLock(layout.lock("manifest")):
        manifest = load_manifest(layout)
        graph = manifest.get("graph")
        if not isinstance(graph, dict):
            raise ManifestValidationError("Manifest graph must be an object")
        if (
            graph.get("indexed_commit") == indexed_commit
            and graph.get("indexed_branch") == indexed_branch
        ):
            return
        manifest["graph"] = {
            **graph,
            "indexed_commit": indexed_commit,
            "indexed_branch": indexed_branch,
        }
        validate_manifest(manifest)
        atomic_write_json(layout.manifest, manifest)


def _validate_v1(document: dict[str, object]) -> None:
    if document.get("schema_version") != 1:
        raise ManifestValidationError("Expected project store schema 1")
    _validate_common(document)
    storage = document.get("storage")
    if storage is not None and _mapping(storage, "storage").get("backend") not in {
        None,
        "filesystem",
    }:
        raise ManifestValidationError("Schema 1 manifest is not a filesystem project store")


def migrate_manifest(layout: ProjectLayout) -> Path | None:
    """Migrate schema 1 to 2, preserving the exact old manifest in ``backups/``."""

    if not layout.manifest.is_file():
        raise ManifestNotFoundError("Project is not initialized; run orqalis init")
    with FileLock(layout.lock("manifest-migration")):
        try:
            old = read_json_object(layout.manifest)
        except FilesystemFormatError as exc:
            raise ManifestValidationError("Project manifest is not valid JSON/YAML") from exc
        version = old.get("schema_version")
        if version == CURRENT_SCHEMA_VERSION:
            validate_manifest(old)
            return None
        if version != 1:
            if isinstance(version, int) and not isinstance(version, bool):
                raise UnsupportedSchemaError(f"Unsupported project store schema: {version}")
            raise ManifestValidationError("Manifest schema_version must be an integer")
        _validate_v1(old)
        raw = layout.manifest.read_bytes()
        backup_dir = layout.store / "backups"
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = backup_dir / f"manifest.schema-1.{stamp}.yaml"
        atomic_write_bytes(backup, raw)

        graph_value = old.get("graph")
        graph_v1: dict[str, object] = graph_value if isinstance(graph_value, dict) else {}
        migrated = {
            **old,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "storage": {"backend": "filesystem"},
            "graph": {
                "schema_version": 1,
                "indexed_commit": graph_v1.get("indexed_commit"),
                "indexed_branch": graph_v1.get("indexed_branch"),
            },
            "memory": {"schema_version": 1},
            "tasks": {"schema_version": 1},
        }
        validate_manifest(migrated)
        if not layout.config.exists():
            atomic_write_json(layout.config, _default_config())
        _sync_store_gitignore(layout)
        atomic_write_json(layout.manifest, migrated)
        load_manifest(layout)
        return backup


def ensure_current_schema(layout: ProjectLayout) -> Path | None:
    """Validate the manifest and migrate only when its supported schema is old.

    Current and unsupported-future manifests are inspected without creating a lock
    or otherwise mutating the project. A schema-1 result is revalidated under the
    migration lock by :func:`migrate_manifest` before any backup or replacement.
    """

    try:
        load_manifest(layout)
    except SchemaMigrationRequired:
        return migrate_manifest(layout)
    return None
