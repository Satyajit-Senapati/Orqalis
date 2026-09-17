"""Deterministic, incremental repository graph extraction and persistence."""

from __future__ import annotations

import ast
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pydantic import Field, ValidationError

from orqalis.domain.base import Contract, utc_now
from orqalis.domain.errors import PolicyDeniedError
from orqalis.git.contracts import GitService, GitStatus
from orqalis.git.service import LocalGitService, validate_relative_path
from orqalis.graph.models import (
    GraphEdge,
    GraphManifest,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
    GraphRefreshMetrics,
    GraphRefreshResult,
    GraphRelation,
    ProjectGraph,
)
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    atomic_write_json,
    read_json_object,
)
from orqalis.persistence.filesystem.layout import ProjectLayout, update_graph_cursor
from orqalis.persistence.filesystem.locking import FileLock

GRAPH_SCHEMA_VERSION = 1
PARSER_VERSION = "python-ast-v1"
MAX_FILE_BYTES = 1_000_000

_SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".php",
    ".py",
    ".pyi",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
}
_DOCUMENT_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}
_CONFIG_EXTENSIONS = {
    ".cfg",
    ".gradle",
    ".ini",
    ".json",
    ".jsonl",
    ".mod",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
}
_CONFIG_NAMES = {
    "dockerfile",
    "makefile",
    "procfile",
    "justfile",
    "jenkinsfile",
}
_BLOCKED_PARTS = {
    ".git",
    ".orqalis",
    ".tools",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "secrets",
    "credentials",
}
_LANGUAGES = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".h": "C",
    ".hpp": "C++",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".pyi": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".sh": "Shell",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}


class _CallSpec(Contract):
    name: str
    line: int = Field(ge=1)


class _ImportSpec(Contract):
    module: str
    names: tuple[str, ...] = ()
    level: int = Field(default=0, ge=0)
    owner: str | None = None
    line: int = Field(ge=1)


class _SymbolSpec(Contract):
    kind: str
    name: str
    qualified_name: str
    parent_qualified_name: str | None = None
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    bases: tuple[str, ...] = ()
    calls: tuple[_CallSpec, ...] = ()


class _ParsedSource(Contract):
    parser_version: str
    parser_kind: str
    content_hash: str
    line_count: int = Field(ge=1)
    syntax_error: bool = False
    symbols: tuple[_SymbolSpec, ...] = ()
    imports: tuple[_ImportSpec, ...] = ()
    module_calls: tuple[_CallSpec, ...] = ()


@dataclass(slots=True)
class _OpenSymbol:
    kind: str
    name: str
    qualified_name: str
    parent_qualified_name: str | None
    line_start: int
    line_end: int
    bases: tuple[str, ...]
    calls: list[_CallSpec] = field(default_factory=list)

    def freeze(self) -> _SymbolSpec:
        return _SymbolSpec(
            kind=self.kind,
            name=self.name,
            qualified_name=self.qualified_name,
            parent_qualified_name=self.parent_qualified_name,
            line_start=self.line_start,
            line_end=self.line_end,
            bases=self.bases,
            calls=tuple(self.calls),
        )


class _PythonCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[_OpenSymbol] = []
        self.imports: list[_ImportSpec] = []
        self.module_calls: list[_CallSpec] = []
        self._stack: list[_OpenSymbol] = []

    @property
    def _owner(self) -> str | None:
        return self._stack[-1].qualified_name if self._stack else None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                _ImportSpec(
                    module=alias.name,
                    names=(),
                    owner=self._owner,
                    line=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(
            _ImportSpec(
                module=node.module or "",
                names=tuple(alias.name for alias in node.names),
                level=node.level,
                owner=self._owner,
                line=node.lineno,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_symbol(
            node,
            GraphNodeKind.CLASS,
            tuple(name for item in node.bases if (name := _expression_name(item)) is not None),
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _expression_name(node.func)
        if name:
            call = _CallSpec(name=name, line=node.lineno)
            if self._stack:
                self._stack[-1].calls.append(call)
            else:
                self.module_calls.append(call)
        self.generic_visit(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        direct_method = bool(self._stack and self._stack[-1].kind == GraphNodeKind.CLASS)
        kind = GraphNodeKind.METHOD if direct_method else GraphNodeKind.FUNCTION
        if node.name.startswith("test_"):
            kind = GraphNodeKind.TEST
        self._visit_symbol(node, kind, ())

    def _visit_symbol(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        kind: GraphNodeKind,
        bases: tuple[str, ...],
    ) -> None:
        parent = self._owner
        qualified = f"{parent}.{node.name}" if parent else node.name
        symbol = _OpenSymbol(
            kind=kind.value,
            name=node.name,
            qualified_name=qualified,
            parent_qualified_name=parent,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            bases=bases,
        )
        self.symbols.append(symbol)
        self._stack.append(symbol)
        self.generic_visit(node)
        self._stack.pop()


def _expression_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _expression_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Subscript):
        return _expression_name(node.value)
    return None


@dataclass(slots=True)
class _EdgeAccumulator:
    source_id: str
    target_id: str
    relation: GraphRelation | str
    provenance: GraphProvenance
    confidence: float
    evidence: set[str] = field(default_factory=set)


class ProjectGraphEngine:
    """Build and persist a deterministic graph bound to exactly one Git repository."""

    def __init__(
        self,
        root: Path,
        *,
        source_root: Path | None = None,
        git: GitService | None = None,
        max_file_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        self.git = git or LocalGitService()
        self.store_root = self.git.root(root)
        self.root = self.git.root(source_root or self.store_root)
        if self.git.common_directory(self.store_root) != self.git.common_directory(self.root):
            raise PolicyDeniedError(
                "Repository graph source does not belong to the canonical project repository"
            )
        self.layout = ProjectLayout(self.store_root)
        self.max_file_bytes = max_file_bytes
        self.graph_dir = self._storage_target(self.layout.memory / "graph")
        self.cache_dir = self._storage_target(self.layout.cache / "parser")
        self.graph_path = self._storage_target(self.graph_dir / "graph.json")
        self.manifest_path = self._storage_target(self.graph_dir / "manifest.json")

    def refresh(self) -> GraphRefreshResult:
        """Refresh only content-changed paths, reusing content-addressed parser output."""

        return self._refresh(force=False)

    def rebuild(self) -> GraphRefreshResult:
        """Rebuild the complete derived graph while retaining safe parser-cache reuse."""

        return self._refresh(force=True)

    def load(self) -> ProjectGraph | None:
        """Load the persisted graph, returning ``None`` for missing or invalid data."""

        _, graph = self._load_state()
        return graph

    def _refresh(self, *, force: bool) -> GraphRefreshResult:
        started = time.perf_counter()
        with FileLock(self.layout.lock("graph")):
            return self._refresh_locked(force=force, started=started)

    def _refresh_locked(self, *, force: bool, started: float) -> GraphRefreshResult:
        previous_manifest, previous_graph = self._load_state()
        status = self.git.status(self.root)
        branch, head = status.branch, status.head
        dirty_paths = tuple(sorted(path for path in status.changed_paths if self._allows(path)))
        if (
            not force
            and previous_manifest is not None
            and previous_graph is not None
            and previous_manifest.indexed_commit == head
            and previous_manifest.indexed_branch == branch
            and not previous_manifest.dirty_paths
            and not dirty_paths
        ):
            update_graph_cursor(self.layout, head, branch)
            return GraphRefreshResult(
                graph=previous_graph,
                manifest=previous_manifest,
                metrics=GraphRefreshMetrics(
                    processed_files=0,
                    cache_hits=0,
                    cache_misses=0,
                    deleted_files=0,
                    total_files=len(previous_manifest.file_hashes),
                    duration_ms=self._duration_ms(started),
                ),
            )
        branch, head, file_hashes = self._discover(status)
        previous_hashes = previous_manifest.file_hashes if previous_manifest else {}
        incompatible = bool(
            previous_manifest
            and (
                previous_manifest.schema_version != GRAPH_SCHEMA_VERSION
                or previous_manifest.parser_version != PARSER_VERSION
            )
        )
        full = force or previous_manifest is None or previous_graph is None or incompatible
        deleted = set(previous_hashes) - set(file_hashes)
        changed = {
            path
            for path, content_hash in file_hashes.items()
            if previous_hashes.get(path) != content_hash
        }

        if not full and not changed and not deleted:
            manifest = previous_manifest
            graph = previous_graph
            if manifest is None or graph is None:
                raise RuntimeError("Graph state disappeared while refreshing")
            if (
                manifest.indexed_commit != head
                or manifest.indexed_branch != branch
                or manifest.dirty_paths != dirty_paths
            ):
                manifest = manifest.model_copy(
                    update={
                        "indexed_commit": head,
                        "indexed_head": head,
                        "indexed_branch": branch,
                        "dirty_paths": dirty_paths,
                        "last_indexed_at": utc_now(),
                    }
                )
                self._write_manifest(manifest)
            update_graph_cursor(self.layout, head, branch)
            return GraphRefreshResult(
                graph=graph,
                manifest=manifest,
                metrics=GraphRefreshMetrics(
                    processed_files=0,
                    cache_hits=0,
                    cache_misses=0,
                    deleted_files=0,
                    total_files=len(file_hashes),
                    duration_ms=self._duration_ms(started),
                ),
            )

        requested = set(file_hashes) if full else changed
        parsed: dict[str, _ParsedSource] = {}
        cache_hits = 0
        cache_misses = 0
        additionally_parsed: set[str] = set()
        for path, content_hash in sorted(file_hashes.items()):
            parser_kind = self._parser_kind(path)
            result = self._read_cache(content_hash, parser_kind)
            if result is None:
                result = self._parse(path, content_hash, parser_kind)
                self._write_cache(result)
                cache_misses += 1
                if path not in requested:
                    additionally_parsed.add(path)
            else:
                cache_hits += 1
            parsed[path] = result

        graph = self._assemble(parsed, file_hashes)
        manifest = GraphManifest(
            schema_version=GRAPH_SCHEMA_VERSION,
            parser_version=PARSER_VERSION,
            indexed_commit=head,
            indexed_head=head,
            indexed_branch=branch,
            dirty_paths=dirty_paths,
            file_hashes=dict(sorted(file_hashes.items())),
            graph_sha256=_graph_digest(graph),
        )
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.graph_path, graph.model_dump(mode="json"))
        self._write_manifest(manifest)
        update_graph_cursor(self.layout, head, branch)
        processed = requested | additionally_parsed
        return GraphRefreshResult(
            graph=graph,
            manifest=manifest,
            metrics=GraphRefreshMetrics(
                processed_files=len(processed),
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                deleted_files=len(deleted),
                total_files=len(file_hashes),
                duration_ms=self._duration_ms(started),
                changed_paths=tuple(sorted(processed | deleted)),
            ),
        )

    def _load_state(self) -> tuple[GraphManifest | None, ProjectGraph | None]:
        if not self.manifest_path.is_file() or not self.graph_path.is_file():
            return None, None
        try:
            manifest = GraphManifest.model_validate(read_json_object(self.manifest_path))
            graph = ProjectGraph.model_validate(read_json_object(self.graph_path))
        except (OSError, FilesystemFormatError, ValidationError, ValueError):
            return None, None
        if (
            manifest.schema_version != GRAPH_SCHEMA_VERSION
            or graph.schema_version != GRAPH_SCHEMA_VERSION
            or manifest.parser_version != PARSER_VERSION
            or graph.parser_version != PARSER_VERSION
            or manifest.graph_sha256 != _graph_digest(graph)
        ):
            return None, None
        return manifest, graph

    def _write_manifest(self, manifest: GraphManifest) -> None:
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.manifest_path, manifest.model_dump(mode="json"))

    def _discover(self, status: GitStatus | None = None) -> tuple[str | None, str, dict[str, str]]:
        status = status or self.git.status(self.root)
        candidates = set(self.git.tracked_files(self.root, status.head))
        candidates.update(status.changed_paths)
        hashes: dict[str, str] = {}
        for path in sorted(candidates):
            if not self._allows(path):
                continue
            try:
                content = self._read_source(path)
            except (OSError, PolicyDeniedError):
                continue
            if content is None:
                continue
            hashes[path] = hashlib.sha256(content).hexdigest()
        return status.branch, status.head, hashes

    def _allows(self, path: str) -> bool:
        try:
            validate_relative_path(path)
            path.encode("utf-8")
        except (PolicyDeniedError, UnicodeEncodeError):
            return False
        source = PurePosixPath(path)
        lowered = tuple(part.casefold() for part in source.parts)
        if any(part in _BLOCKED_PARTS for part in lowered):
            return False
        name = source.name.casefold()
        if (
            name.startswith(".env")
            or any(word in name for word in ("credential", "secret", "private_key"))
            or name.endswith((".lock", "-lock.json"))
        ):
            return False
        suffix = source.suffix.casefold()
        return bool(
            suffix in _SOURCE_EXTENSIONS
            or suffix in _DOCUMENT_EXTENSIONS
            or suffix in _CONFIG_EXTENSIONS
            or name in _CONFIG_NAMES
        )

    def _read_source(self, path: str) -> bytes | None:
        validate_relative_path(path)
        target = self.root.joinpath(*PurePosixPath(path).parts)
        current = self.root
        for part in PurePosixPath(path).parts:
            current /= part
            if current.is_symlink() or current.is_junction():
                raise PolicyDeniedError("Repository graph does not follow links or junctions")
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise PolicyDeniedError("Repository graph path escapes its project root")
        if resolved.stat().st_size > self.max_file_bytes:
            return None
        with resolved.open("rb") as stream:
            content = stream.read(self.max_file_bytes + 1)
        if len(content) > self.max_file_bytes or b"\x00" in content:
            return None
        return content

    def _parser_kind(self, path: str) -> str:
        return "python" if PurePosixPath(path).suffix.casefold() in {".py", ".pyi"} else "generic"

    def _cache_path(self, content_hash: str) -> Path:
        return self._storage_target(self.cache_dir / f"{content_hash}.json")

    def _read_cache(self, content_hash: str, parser_kind: str) -> _ParsedSource | None:
        path = self._cache_path(content_hash)
        if not path.is_file():
            return None
        try:
            parsed = _ParsedSource.model_validate(read_json_object(path))
        except (OSError, FilesystemFormatError, ValidationError, ValueError):
            return None
        if (
            parsed.parser_version != PARSER_VERSION
            or parsed.parser_kind != parser_kind
            or parsed.content_hash != content_hash
        ):
            return None
        return parsed

    def _write_cache(self, parsed: _ParsedSource) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self._cache_path(parsed.content_hash),
            parsed.model_dump(mode="json"),
        )

    def _parse(self, path: str, content_hash: str, parser_kind: str) -> _ParsedSource:
        content = self._read_source(path)
        if content is None:
            raise OSError(f"Repository file became unavailable while parsing: {path}")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=1,
                syntax_error=True,
            )
        line_count = max(1, len(text.splitlines()))
        if parser_kind != "python":
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=line_count,
            )
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=line_count,
                syntax_error=True,
            )
        collector = _PythonCollector()
        collector.visit(tree)
        return _ParsedSource(
            parser_version=PARSER_VERSION,
            parser_kind=parser_kind,
            content_hash=content_hash,
            line_count=line_count,
            symbols=tuple(item.freeze() for item in collector.symbols),
            imports=tuple(collector.imports),
            module_calls=tuple(collector.module_calls),
        )

    def _assemble(
        self,
        parsed: dict[str, _ParsedSource],
        file_hashes: dict[str, str],
    ) -> ProjectGraph:
        nodes: dict[str, GraphNode] = {}
        edges: dict[tuple[str, str, str, str], _EdgeAccumulator] = {}
        module_ids: dict[str, str] = {}
        path_modules: dict[str, tuple[str, str]] = {}
        path_symbols: dict[str, dict[str, str]] = {}
        qualified_symbols: dict[str, str] = {}
        simple_symbols: defaultdict[str, list[str]] = defaultdict(list)
        test_suites: dict[str, str] = {}

        for path, result in sorted(parsed.items()):
            content_hash = file_hashes[path]
            source = PurePosixPath(path)
            language = _LANGUAGES.get(source.suffix.casefold())
            role = _file_role(path)
            file_id = _node_id("file", path)
            metadata: dict[str, str | int | float | bool | None | list[str]] = {
                "role": role,
            }
            if result.syntax_error:
                metadata["parse_error"] = True
            nodes[file_id] = GraphNode(
                id=file_id,
                kind=GraphNodeKind.FILE,
                name=source.name,
                file_path=path,
                line_start=1,
                line_end=result.line_count,
                language=language,
                metadata=metadata,
                source_hash=content_hash,
            )

            if result.parser_kind == "python":
                module_name = _module_name(path)
                module_id = _node_id("module", path, module_name)
                module_ids[module_name] = module_id
                path_modules[path] = (module_name, module_id)
                nodes[module_id] = GraphNode(
                    id=module_id,
                    kind=GraphNodeKind.MODULE,
                    name=module_name,
                    file_path=path,
                    line_start=1,
                    line_end=result.line_count,
                    language="Python",
                    metadata={"qualified_name": module_name},
                    source_hash=content_hash,
                )
                self._add_edge(
                    edges,
                    file_id,
                    module_id,
                    GraphRelation.DEFINES,
                    GraphProvenance.EXTRACTED,
                    1.0,
                    f"{path}:1",
                )
                symbol_ids: dict[str, str] = {}
                for symbol in result.symbols:
                    qualified = f"{module_name}.{symbol.qualified_name}"
                    symbol_id = _node_id("symbol", path, symbol.qualified_name, symbol.kind)
                    symbol_ids[symbol.qualified_name] = symbol_id
                    qualified_symbols[qualified] = symbol_id
                    simple_symbols[symbol.name].append(symbol_id)
                    nodes[symbol_id] = GraphNode(
                        id=symbol_id,
                        kind=symbol.kind,
                        name=symbol.name,
                        file_path=path,
                        line_start=symbol.line_start,
                        line_end=symbol.line_end,
                        language="Python",
                        metadata={
                            "qualified_name": qualified,
                            "symbol_kind": symbol.kind,
                        },
                        source_hash=content_hash,
                    )
                path_symbols[path] = symbol_ids
                for symbol in result.symbols:
                    symbol_id = symbol_ids[symbol.qualified_name]
                    parent_id = (
                        symbol_ids.get(symbol.parent_qualified_name)
                        if symbol.parent_qualified_name
                        else module_id
                    )
                    self._add_edge(
                        edges,
                        parent_id or module_id,
                        symbol_id,
                        GraphRelation.DEFINES,
                        GraphProvenance.EXTRACTED,
                        1.0,
                        f"{path}:{symbol.line_start}",
                    )

            if role == "configuration":
                config_id = _node_id("configuration", path)
                nodes[config_id] = GraphNode(
                    id=config_id,
                    kind=GraphNodeKind.CONFIGURATION,
                    name=source.name,
                    file_path=path,
                    line_start=1,
                    line_end=result.line_count,
                    language=language,
                    metadata={"format": source.suffix.casefold() or source.name.casefold()},
                    source_hash=content_hash,
                )
                self._add_edge(
                    edges,
                    file_id,
                    config_id,
                    GraphRelation.DEFINES,
                    GraphProvenance.EXTRACTED,
                    1.0,
                    f"{path}:1",
                )
            elif role == "documentation":
                document_id = _node_id("documentation", path)
                nodes[document_id] = GraphNode(
                    id=document_id,
                    kind=GraphNodeKind.DOCUMENTATION,
                    name=source.name,
                    file_path=path,
                    line_start=1,
                    line_end=result.line_count,
                    metadata={"format": source.suffix.casefold()},
                    source_hash=content_hash,
                )
                self._add_edge(
                    edges,
                    file_id,
                    document_id,
                    GraphRelation.DEFINES,
                    GraphProvenance.EXTRACTED,
                    1.0,
                    f"{path}:1",
                )

            if _is_test_path(path):
                suite_id = _node_id("test-suite", path)
                test_suites[path] = suite_id
                nodes[suite_id] = GraphNode(
                    id=suite_id,
                    kind=GraphNodeKind.TEST,
                    name=source.stem,
                    file_path=path,
                    line_start=1,
                    line_end=result.line_count,
                    language=language,
                    metadata={"symbol_kind": "suite"},
                    source_hash=content_hash,
                )
                self._add_edge(
                    edges,
                    file_id,
                    suite_id,
                    GraphRelation.DEFINES,
                    GraphProvenance.EXTRACTED,
                    1.0,
                    f"{path}:1",
                )

        for path, result in sorted(parsed.items()):
            module_info = path_modules.get(path)
            if module_info is None:
                continue
            module_name, module_id = module_info
            symbol_ids = path_symbols[path]
            for item in result.imports:
                source_id = symbol_ids.get(item.owner, module_id) if item.owner else module_id
                imported_name = _resolve_import(
                    module_name,
                    item.module,
                    item.names,
                    item.level,
                    is_package=PurePosixPath(path).name in {"__init__.py", "__init__.pyi"},
                )
                if not imported_name:
                    continue
                target_id = module_ids.get(imported_name)
                local_target = target_id is not None
                if target_id is None:
                    target_id = _node_id("external-module", imported_name)
                    nodes.setdefault(
                        target_id,
                        GraphNode(
                            id=target_id,
                            kind=GraphNodeKind.MODULE,
                            name=imported_name,
                            metadata={"external": True, "reference_type": "import"},
                        ),
                    )
                self._add_edge(
                    edges,
                    source_id,
                    target_id,
                    GraphRelation.IMPORTS,
                    GraphProvenance.EXTRACTED,
                    1.0,
                    f"{path}:{item.line}",
                )
                test_suite_id = test_suites.get(path)
                if test_suite_id and local_target and target_id != module_id:
                    self._add_edge(
                        edges,
                        test_suite_id,
                        target_id,
                        GraphRelation.TESTS,
                        GraphProvenance.INFERRED,
                        0.75,
                        f"{path}:{item.line}",
                    )

            for call in result.module_calls:
                self._add_call(
                    nodes,
                    edges,
                    module_id,
                    call,
                    path,
                    module_name,
                    None,
                    qualified_symbols,
                    simple_symbols,
                )
            for symbol in result.symbols:
                source_id = symbol_ids[symbol.qualified_name]
                for call in symbol.calls:
                    self._add_call(
                        nodes,
                        edges,
                        source_id,
                        call,
                        path,
                        module_name,
                        symbol,
                        qualified_symbols,
                        simple_symbols,
                    )
                if symbol.kind == GraphNodeKind.CLASS:
                    for base in symbol.bases:
                        target_id = self._resolve_symbol(
                            base,
                            module_name,
                            symbol,
                            qualified_symbols,
                            simple_symbols,
                        )
                        if target_id is None:
                            target_id = _node_id("external-class", base)
                            nodes.setdefault(
                                target_id,
                                GraphNode(
                                    id=target_id,
                                    kind=GraphNodeKind.CLASS,
                                    name=base,
                                    metadata={
                                        "external": True,
                                        "reference_type": "inheritance",
                                    },
                                ),
                            )
                        self._add_edge(
                            edges,
                            source_id,
                            target_id,
                            GraphRelation.EXTENDS,
                            GraphProvenance.EXTRACTED,
                            1.0,
                            f"{path}:{symbol.line_start}",
                        )

        graph_edges = tuple(
            GraphEdge(
                id=_edge_id(
                    item.source_id,
                    item.target_id,
                    str(item.relation),
                    item.provenance.value,
                ),
                source_id=item.source_id,
                target_id=item.target_id,
                relation=item.relation,
                provenance=item.provenance,
                confidence=item.confidence,
                evidence=tuple(sorted(item.evidence)),
            )
            for _, item in sorted(edges.items())
        )
        return ProjectGraph(
            schema_version=GRAPH_SCHEMA_VERSION,
            parser_version=PARSER_VERSION,
            nodes=tuple(sorted(nodes.values(), key=lambda item: item.id)),
            edges=graph_edges,
        )

    def _add_call(
        self,
        nodes: dict[str, GraphNode],
        edges: dict[tuple[str, str, str, str], _EdgeAccumulator],
        source_id: str,
        call: _CallSpec,
        path: str,
        module_name: str,
        symbol: _SymbolSpec | None,
        qualified_symbols: dict[str, str],
        simple_symbols: defaultdict[str, list[str]],
    ) -> None:
        target_id = self._resolve_symbol(
            call.name,
            module_name,
            symbol,
            qualified_symbols,
            simple_symbols,
        )
        if target_id is None:
            target_id = _node_id("call-reference", call.name)
            nodes.setdefault(
                target_id,
                GraphNode(
                    id=target_id,
                    kind=GraphNodeKind.REFERENCE,
                    name=call.name,
                    metadata={"external": True, "reference_type": "call"},
                ),
            )
        self._add_edge(
            edges,
            source_id,
            target_id,
            GraphRelation.CALLS,
            GraphProvenance.EXTRACTED,
            1.0,
            f"{path}:{call.line}",
        )

    def _resolve_symbol(
        self,
        reference: str,
        module_name: str,
        symbol: _SymbolSpec | None,
        qualified_symbols: dict[str, str],
        simple_symbols: defaultdict[str, list[str]],
    ) -> str | None:
        if symbol and reference.startswith(("self.", "cls.")):
            parent = symbol.parent_qualified_name
            if parent:
                member = reference.rsplit(".", maxsplit=1)[-1]
                candidate = f"{module_name}.{parent}.{member}"
                if candidate in qualified_symbols:
                    return qualified_symbols[candidate]
        module_candidate = f"{module_name}.{reference}"
        if module_candidate in qualified_symbols:
            return qualified_symbols[module_candidate]
        if reference in qualified_symbols:
            return qualified_symbols[reference]
        matches = simple_symbols.get(reference.split(".")[-1], [])
        return matches[0] if len(matches) == 1 else None

    def _add_edge(
        self,
        edges: dict[tuple[str, str, str, str], _EdgeAccumulator],
        source_id: str,
        target_id: str,
        relation: GraphRelation | str,
        provenance: GraphProvenance,
        confidence: float,
        evidence: str,
    ) -> None:
        key = (source_id, target_id, str(relation), provenance.value)
        current = edges.get(key)
        if current is None:
            current = _EdgeAccumulator(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                provenance=provenance,
                confidence=confidence,
            )
            edges[key] = current
        current.confidence = max(current.confidence, confidence)
        current.evidence.add(evidence)

    def _storage_target(self, path: Path) -> Path:
        target = self.layout.contained(path)
        store = self.layout.store
        if store.exists() and (store.is_symlink() or store.is_junction()):
            raise PolicyDeniedError("Project store must not be a link or junction")
        resolved_store = store.resolve(strict=False)
        resolved_target = target.resolve(strict=False)
        if resolved_target != resolved_store and not resolved_target.is_relative_to(resolved_store):
            raise PolicyDeniedError("Graph storage path escapes the selected repository")
        return target

    @staticmethod
    def _duration_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)


def _module_name(path: str) -> str:
    source = PurePosixPath(path)
    parts = list(source.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or "__init__"


def _graph_digest(graph: ProjectGraph) -> str:
    payload = json.dumps(
        graph.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolve_import(
    current_module: str,
    imported_module: str,
    imported_names: tuple[str, ...],
    level: int,
    *,
    is_package: bool,
) -> str:
    if level == 0:
        return imported_module
    package = current_module.split(".")
    if package and not is_package:
        package.pop()
    remove = max(0, level - 1)
    if remove:
        package = package[:-remove] if remove <= len(package) else []
    if imported_module:
        package.extend(imported_module.split("."))
    elif imported_names:
        package.append(imported_names[0])
    return ".".join(package)


def _file_role(path: str) -> str:
    source = PurePosixPath(path)
    suffix = source.suffix.casefold()
    if _is_test_path(path):
        return "test"
    if suffix in _DOCUMENT_EXTENSIONS:
        return "documentation"
    if suffix in _CONFIG_EXTENSIONS or source.name.casefold() in _CONFIG_NAMES:
        return "configuration"
    return "source"


def _is_test_path(path: str) -> bool:
    source = PurePosixPath(path.casefold())
    return bool(
        "tests" in source.parts
        or "test" in source.parts
        or source.name.startswith(("test_", "tests_"))
        or source.name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def _node_id(kind: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join((kind, *parts)).encode("utf-8")).hexdigest()[:24]
    return f"{kind}:{digest}"


def _edge_id(source_id: str, target_id: str, relation: str, provenance: str) -> str:
    digest = hashlib.sha256(
        "\x1f".join((source_id, target_id, relation, provenance)).encode("utf-8")
    ).hexdigest()[:24]
    return f"edge:{digest}"
