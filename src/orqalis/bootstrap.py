"""Deterministic bootstrap of project-local Orqalis intelligence."""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path

from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.domain.project import Project
from orqalis.git.contracts import GitStatus
from orqalis.git.service import LocalGitService
from orqalis.indexing.models import IndexBuildMetrics
from orqalis.indexing.service import ProjectIndex
from orqalis.memory.curated import CuratedMemoryStore
from orqalis.persistence.filesystem.io import atomic_write_bytes, atomic_write_json
from orqalis.persistence.filesystem.layout import (
    ProjectLayout,
    bootstrap_project_store,
    load_manifest,
)
from orqalis.persistence.filesystem.locking import FileLock
from orqalis.security.redaction import safe_diagnostic

_LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}
_MANIFEST_NAMES = {
    "cargo.toml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
}


class DetectedCommand(Contract):
    name: str
    command: str
    source: str


class ProjectBootstrapResult(Contract):
    root: Path
    files_inspected: int = Field(ge=0)
    languages: tuple[str, ...]
    commands: tuple[DetectedCommand, ...]
    index_metrics: IndexBuildMetrics


class ProjectBootstrapService:
    """Create useful canonical project documents and all disposable indexes."""

    def __init__(self, root: Path, *, git: LocalGitService | None = None) -> None:
        self.git = git or LocalGitService()
        self.root = self.git.root(root)
        self.layout = ProjectLayout(self.root)

    def bootstrap(self, project: Project) -> ProjectBootstrapResult:
        if project.repo_root.resolve(strict=True) != self.root:
            raise ValueError("Project bootstrap root does not match the project identity")
        self.layout = bootstrap_project_store(
            self.root,
            project_id=project.id,
            project_name=project.name,
            initialized_at=project.created_at,
        )
        manifest = load_manifest(self.layout)
        manifest_project = manifest.get("project")
        if not isinstance(manifest_project, dict) or manifest_project.get("id") != str(project.id):
            raise ValueError("Project bootstrap identity does not match the manifest")

        files = self.git.tracked_files(self.root)
        languages = self._languages(files)
        commands = self._commands(files)
        self._write_project_documents(project, files, languages, commands)
        CuratedMemoryStore(self.layout).initialize()
        index_result = ProjectIndex(self.root, git=self.git).rebuild()
        self._record_index_state(
            index_result.manifest.indexed_commit,
            index_result.manifest.indexed_branch,
        )
        # Indexing may take long enough for the working tree to change; current-state
        # deliberately reflects the final observed Git state.
        self._write_current_state(self.git.status(self.root))
        return ProjectBootstrapResult(
            root=self.root,
            files_inspected=len(files),
            languages=languages,
            commands=commands,
            index_metrics=index_result.metrics,
        )

    def _languages(self, files: tuple[str, ...]) -> tuple[str, ...]:
        counts = Counter(
            language
            for path in files
            if (language := _LANGUAGE_BY_SUFFIX.get(Path(path).suffix.casefold())) is not None
        )
        return tuple(language for language, _ in counts.most_common())

    def _commands(self, files: tuple[str, ...]) -> tuple[DetectedCommand, ...]:
        detected: dict[tuple[str, str], DetectedCommand] = {}

        def add(name: str, command: str, source: str) -> None:
            if not command.strip() or len(command) > 500:
                return
            if safe_diagnostic(command) != command:
                return
            detected[(name, command)] = DetectedCommand(
                name=name,
                command=command,
                source=source,
            )

        file_set = set(files)
        if "pyproject.toml" in file_set:
            try:
                document = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                document = {}
            tool = document.get("tool", {})
            if isinstance(tool, dict) and "pytest" in tool:
                add("test", "python -m pytest", "pyproject.toml")
            if isinstance(document.get("build-system"), dict):
                add("build", "python -m build", "pyproject.toml")
            if isinstance(tool, dict) and "ruff" in tool:
                add("lint", "ruff check .", "pyproject.toml")
        if "package.json" in file_set:
            try:
                package = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                package = {}
            scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
            if isinstance(scripts, dict):
                for name, value in sorted(scripts.items()):
                    if (
                        isinstance(name, str)
                        and isinstance(value, str)
                        and safe_diagnostic(value) == value
                    ):
                        add(name, f"npm run {name}", "package.json")
        if "Cargo.toml" in file_set:
            add("build", "cargo build", "Cargo.toml")
            add("test", "cargo test", "Cargo.toml")
        if "go.mod" in file_set:
            add("test", "go test ./...", "go.mod")
        if "Makefile" in file_set:
            try:
                makefile = (self.root / "Makefile").read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                makefile = ""
            for target in re.findall(r"(?m)^([A-Za-z0-9_.-]+)\s*:(?![=])", makefile):
                if target in {"build", "check", "lint", "test"}:
                    add(target, f"make {target}", "Makefile")
        return tuple(sorted(detected.values(), key=lambda item: (item.name, item.command)))

    def _write_project_documents(
        self,
        project: Project,
        files: tuple[str, ...],
        languages: tuple[str, ...],
        commands: tuple[DetectedCommand, ...],
    ) -> None:
        self.layout.project.mkdir(parents=True, exist_ok=True)
        manifests = tuple(
            sorted(path for path in files if Path(path).name.casefold() in _MANIFEST_NAMES)
        )
        tests = tuple(
            sorted(
                path
                for path in files
                if "test" in {part.casefold() for part in Path(path).parts}
                or Path(path).name.casefold().startswith("test_")
            )
        )
        stack = {
            "schema_version": 1,
            "languages": list(languages),
            "manifests": list(manifests),
        }
        command_document = {
            "schema_version": 1,
            "commands": [command.model_dump(mode="json") for command in commands],
        }
        repository = {
            "schema_version": 1,
            "root": ".",
            "default_branch": project.default_branch,
            "tracked_files": len(files),
            "test_files": list(tests[:200]),
        }
        self._write_once(self.layout.project / "tech-stack.yaml", stack)
        self._write_once(self.layout.project / "commands.yaml", command_document)
        self._write_once(self.layout.project / "repository.yaml", repository)
        language_text = ", ".join(languages) if languages else "not yet detected"
        summary = (
            f"# {safe_diagnostic(project.name)}\n\n"
            "This repository owns its Orqalis project intelligence and task history "
            "under `.orqalis/`.\n\n"
            f"Detected languages: {language_text}.\n"
            f"Tracked files inspected: {len(files)}.\n"
        )
        self._write_once(self.layout.project / "summary.md", summary.encode("utf-8"))

    def _write_once(self, path: Path, value: dict[str, object] | bytes) -> None:
        if path.exists():
            return
        if isinstance(value, bytes):
            atomic_write_bytes(path, value)
        else:
            atomic_write_json(path, value)

    def _write_current_state(self, status: GitStatus) -> None:
        dirty = tuple(path for path in status.changed_paths if not path.startswith(".orqalis/"))
        lines = [
            "# Current repository state",
            "",
            f"- Branch: `{safe_diagnostic(status.branch or 'detached')}`",
            f"- HEAD: `{status.head}`",
            f"- Dirty relevant files: {len(dirty)}",
        ]
        lines.extend(f"  - `{safe_diagnostic(path)}`" for path in dirty[:200])
        atomic_write_bytes(
            self.layout.project / "current-state.md",
            ("\n".join(lines) + "\n").encode("utf-8"),
        )

    def _record_index_state(self, commit: str | None, branch: str | None) -> None:
        with FileLock(self.layout.lock("manifest")):
            manifest = load_manifest(self.layout)
            graph = manifest.get("graph")
            if not isinstance(graph, dict):
                raise ValueError("Project graph manifest section is invalid")
            manifest["graph"] = {
                **graph,
                "indexed_commit": commit,
                "indexed_branch": branch,
            }
            atomic_write_json(self.layout.manifest, manifest)
            load_manifest(self.layout)


__all__ = [
    "DetectedCommand",
    "ProjectBootstrapResult",
    "ProjectBootstrapService",
]
