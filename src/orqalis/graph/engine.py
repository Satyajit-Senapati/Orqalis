"""Deterministic, incremental repository graph extraction and persistence."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import posixpath
import re
import time
import tokenize
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.git.contracts import GitService, GitStatus
from orqalis.git.service import LocalGitService, validate_relative_path
from orqalis.graph.ecmascript import KINDS as SCRIPT_PARSERS
from orqalis.graph.ecmascript import extract as extract_script
from orqalis.graph.ecmascript import parser_identity
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
from orqalis.graph.parsing import (
    MAX_BINDINGS,
    MAX_CALLS,
    MAX_DEPTH,
    MAX_IMPORTS,
    MAX_NAME,
    MAX_QUALIFIED_NAME,
    MAX_SYMBOLS,
    MAX_VISITS,
)
from orqalis.graph.parsing import (
    CallSpec as _CallSpec,
)
from orqalis.graph.parsing import (
    ImportSpec as _ImportSpec,
)
from orqalis.graph.parsing import (
    ParsedSource as _ParsedSource,
)
from orqalis.graph.parsing import (
    SymbolSpec as _SymbolSpec,
)
from orqalis.persistence.filesystem.io import (
    FilesystemFormatError,
    atomic_write_bytes,
    atomic_write_json,
    read_json_object,
    read_json_object_with_sha256,
)
from orqalis.persistence.filesystem.layout import ProjectLayout, update_graph_cursor
from orqalis.persistence.filesystem.locking import FileLock

GRAPH_SCHEMA_VERSION = 1
PARSER_VERSION = f"source-ast-v5;{parser_identity()}"
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
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
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
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
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


@dataclass(slots=True)
class _OpenSymbol:
    kind: str
    name: str
    qualified_name: str
    parent_qualified_name: str | None
    line_start: int
    line_end: int
    bases: tuple[str, ...]
    byte_start: int | None = None
    byte_end: int | None = None
    calls: list[_CallSpec] = field(default_factory=list)
    bound_names: set[str] = field(default_factory=set)

    def freeze(self) -> _SymbolSpec:
        return _SymbolSpec(
            kind=self.kind,
            name=self.name,
            qualified_name=self.qualified_name,
            parent_qualified_name=self.parent_qualified_name,
            line_start=self.line_start,
            line_end=self.line_end,
            bases=self.bases,
            byte_start=self.byte_start,
            byte_end=self.byte_end,
            calls=tuple(self.calls),
            bound_names=tuple(sorted(self.bound_names)),
        )


class _PythonCollector(ast.NodeVisitor):
    def __init__(self, source: str | None = None) -> None:
        self.symbols: list[_OpenSymbol] = []
        self.imports: list[_ImportSpec] = []
        self.module_calls: list[_CallSpec] = []
        self._stack: list[_OpenSymbol] = []
        self.diagnostics: set[str] = set()
        self._visits = self._depth = self._call_count = self._binding_count = 0
        self._line_offsets: list[int] = []
        self._decorators: list[tuple[int, int]] = []
        if source is not None:
            # AST rows count physical CR/LF newlines, not Unicode separators inside
            # literals. Offsets always refer to the unchanged original UTF-8 bytes.
            self._line_offsets = [
                0,
                *(match.end() for match in re.finditer(rb"\r\n|\r|\n", source.encode("utf-8"))),
            ]
            # Token positions distinguish real decorator markers from strings/comments,
            # including parenthesized decorators whose AST expression starts later.
            for token in tokenize.generate_tokens(io.StringIO(source, newline=None).readline):
                if token.type == tokenize.OP and token.string == "@":
                    row, column = token.start
                    if not token.line[:column].strip():
                        self._decorators.append((row, len(token.line[:column].encode("utf-8"))))

    def visit(self, node: ast.AST) -> None:
        self._visits += 1
        if self._visits > MAX_VISITS or self._depth >= MAX_DEPTH:
            self.diagnostics.add("visit_limit" if self._visits > MAX_VISITS else "depth_limit")
            return
        self._depth += 1
        try:
            super().visit(node)
        finally:
            self._depth -= 1

    def _bind(self, names: list[str], target: set[str]) -> None:
        for name in names:
            if len(name) > MAX_NAME or self._binding_count >= MAX_BINDINGS:
                self.diagnostics.add("binding_limit")
                continue
            target.add(name)
            self._binding_count += 1

    @property
    def _owner(self) -> str | None:
        return self._stack[-1].qualified_name if self._stack else None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if (
                len(self.imports) >= MAX_IMPORTS
                or len(alias.name) > 500
                or len(alias.asname or "") > MAX_NAME
            ):
                self.diagnostics.add("import_limit")
                continue
            self.imports.append(
                _ImportSpec(
                    module=alias.name,
                    aliases=(
                        (
                            alias.asname or alias.name.split(".")[0],
                            alias.name if alias.asname else alias.name.split(".")[0],
                        ),
                    ),
                    names=(),
                    owner=self._owner,
                    line=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if len(self.imports) >= MAX_IMPORTS or len(node.module or "") > 500:
            self.diagnostics.add("import_limit")
            return
        aliases = [
            alias
            for alias in node.names[:256]
            if len(alias.name) <= MAX_NAME and len(alias.asname or "") <= MAX_NAME
        ]
        if len(aliases) != len(node.names):
            self.diagnostics.add("import_alias_limit")
        self.imports.append(
            _ImportSpec(
                module=node.module or "",
                names=tuple(alias.name for alias in aliases),
                aliases=tuple((alias.asname or alias.name, alias.name) for alias in aliases),
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
        if name and self._call_count >= MAX_CALLS:
            self.diagnostics.add("call_limit")
        elif name:
            self._call_count += 1
            call = _CallSpec(name=name, line=node.lineno)
            if self._stack:
                self._stack[-1].calls.append(call)
            else:
                self.module_calls.append(call)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self._stack and isinstance(node.ctx, (ast.Store, ast.Del)):
            self._bind([node.id], self._stack[-1].bound_names)

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
        if (
            len(qualified) > MAX_QUALIFIED_NAME
            or len(node.name) > MAX_NAME
            or len(self.symbols) >= MAX_SYMBOLS
        ):
            self.diagnostics.add("symbol_limit")
            return
        start_line = min((item.lineno for item in node.decorator_list), default=node.lineno)
        start_column = node.col_offset
        if node.decorator_list and self._decorators:
            candidates = [
                (row, col)
                for row, col in self._decorators
                if row <= start_line and col == node.col_offset
            ]
            if candidates:
                start_line, start_column = candidates[-1]
        end_line = node.end_lineno or node.lineno
        symbol = _OpenSymbol(
            kind=kind.value,
            name=node.name,
            qualified_name=qualified,
            parent_qualified_name=parent,
            line_start=start_line,
            line_end=end_line,
            byte_start=self._line_offsets[start_line - 1] + start_column
            if self._line_offsets
            else None,
            byte_end=self._line_offsets[end_line - 1] + (node.end_col_offset or 0)
            if self._line_offsets
            else None,
            bases=bases[:256],
        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            self._bind(
                [arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)],
                symbol.bound_names,
            )
            if args.vararg:
                self._bind([args.vararg.arg], symbol.bound_names)
            if args.kwarg:
                self._bind([args.kwarg.arg], symbol.bound_names)
        self.symbols.append(symbol)
        self._stack.append(symbol)
        self.generic_visit(node)
        self._stack.pop()


def _expression_name(node: ast.expr) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute) and len(parts) < 32:
        parts.append(current.attr[:300])
        current = current.value
    prefix = current.id if isinstance(current, ast.Name) and len(current.id) <= 300 else "<dynamic>"
    # Structural placeholders retain call occurrence evidence without persisting
    # dynamic receiver arguments/subscript literals or claiming their target binding.
    return ".".join((prefix, *reversed(parts)))[:500]


@dataclass(slots=True)
class _EdgeAccumulator:
    source_id: str
    target_id: str
    relation: GraphRelation | str
    provenance: GraphProvenance
    confidence: float
    evidence: set[str] = field(default_factory=set)
    resolution_basis: set[str] = field(default_factory=set)
    source_expressions: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class _SymbolResolution:
    target_id: str
    basis: str


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
        if (
            isinstance(self.git, LocalGitService)
            and type(self.git) is LocalGitService
            and not {"root", "common_directory", "_execute"}.intersection(self.git.__dict__)
        ):
            self.store_root, canonical_directory = self.git.root_and_common_directory(root)
            if source_root is None or source_root == root:
                self.root, source_directory = self.store_root, canonical_directory
            else:
                self.root, source_directory = self.git.root_and_common_directory(source_root)
        else:
            # Injected services and instance overrides retain their original dispatch.
            self.store_root = self.git.root(root)
            self.root = self.store_root if source_root is None else self.git.root(source_root)
            canonical_directory = self.git.common_directory(self.store_root)
            source_directory = (
                canonical_directory
                if self.root == self.store_root
                else self.git.common_directory(self.root)
            )
        if self.root != self.store_root and canonical_directory != source_directory:
            raise PolicyDeniedError(
                "Repository graph source does not belong to the canonical project repository"
            )
        self.layout = ProjectLayout(self.store_root)
        self.max_file_bytes = max_file_bytes
        self.graph_dir = self._storage_target(self.layout.memory / "graph")
        self.cache_dir = self._storage_target(self.layout.cache / "parser")
        self.graph_path = self._storage_target(self.graph_dir / "graph.json")
        self.manifest_path = self._storage_target(self.graph_dir / "manifest.json")
        self._graph_digest_proof: tuple[str, str] | None = None

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

    def refresh_with_status(self) -> tuple[GraphRefreshResult, GitStatus]:
        """Return the graph and the Git status captured inside its refresh lock."""
        return self._refresh_with_status(force=False)

    def _refresh(self, *, force: bool) -> GraphRefreshResult:
        return self._refresh_with_status(force=force)[0]

    def _refresh_with_status(self, *, force: bool) -> tuple[GraphRefreshResult, GitStatus]:
        started = time.perf_counter()
        with FileLock(self.layout.lock("graph")):
            return self._refresh_locked(force=force, started=started)

    def _refresh_locked(
        self, *, force: bool, started: float
    ) -> tuple[GraphRefreshResult, GitStatus]:
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
            ), status
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
            ), status

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
        graph_payload = _graph_payload(graph)
        manifest = GraphManifest(
            schema_version=GRAPH_SCHEMA_VERSION,
            parser_version=PARSER_VERSION,
            indexed_commit=head,
            indexed_head=head,
            indexed_branch=branch,
            dirty_paths=dirty_paths,
            file_hashes=dict(sorted(file_hashes.items())),
            graph_sha256=hashlib.sha256(graph_payload).hexdigest(),
        )
        self.graph_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self.graph_path, graph_payload + b"\n")
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
        ), status

    def _load_state(self) -> tuple[GraphManifest | None, ProjectGraph | None]:
        if not self.manifest_path.is_file() or not self.graph_path.is_file():
            self._graph_digest_proof = None
            return None, None
        # Keep the pair coherent even when callers load concurrently. No models are cached:
        # every read decodes strictly, validates fresh objects, and checks the current manifest.
        proof = self._graph_digest_proof
        try:
            manifest = GraphManifest.model_validate(read_json_object(self.manifest_path))
            document, raw_digest = read_json_object_with_sha256(self.graph_path)
            eligible = "generated_at" in document
            graph = ProjectGraph.model_validate(document)
            del document  # Release the decoded tree before a cache-miss canonical dump.
            graph_digest = (
                proof[1]
                if eligible and proof is not None and proof[0] == raw_digest
                else _graph_digest(graph)
            )
        except PolicyDeniedError:
            self._graph_digest_proof = None
            raise
        except (OSError, FilesystemFormatError, ValidationError, ValueError):
            self._graph_digest_proof = None
            return None, None
        if (
            manifest.schema_version != GRAPH_SCHEMA_VERSION
            or graph.schema_version != GRAPH_SCHEMA_VERSION
            or manifest.parser_version != PARSER_VERSION
            or graph.parser_version != PARSER_VERSION
            or manifest.graph_sha256 != graph_digest
        ):
            self._graph_digest_proof = None
            return None, None
        # Missing timestamps use a volatile model default, so cannot establish a proof.
        self._graph_digest_proof = (raw_digest, graph_digest) if eligible else None
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
        suffix = PurePosixPath(path).suffix.casefold()
        if suffix in {".py", ".pyi"}:
            return "python"
        if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            return "javascript"
        if suffix in {".ts", ".mts", ".cts"}:
            return "typescript"
        return "tsx" if suffix == ".tsx" else "generic"

    def _cache_path(self, content_hash: str, parser_kind: str) -> Path:
        return self._storage_target(self.cache_dir / f"{parser_kind}-{content_hash}.json")

    def _read_cache(self, content_hash: str, parser_kind: str) -> _ParsedSource | None:
        path = self._cache_path(content_hash, parser_kind)
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
            self._cache_path(parsed.content_hash, parsed.parser_kind),
            parsed.model_dump(mode="json"),
        )

    def _parse(self, path: str, content_hash: str, parser_kind: str) -> _ParsedSource:
        content = self._read_source(path)
        if content is None:
            raise OSError(f"Repository file became unavailable while parsing: {path}")
        if hashlib.sha256(content).hexdigest() != content_hash:
            raise ConflictError("Repository source changed during graph parsing; refresh again")
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
        line_count = len(re.split(r"\r\n|\r|\n", text))
        if parser_kind in SCRIPT_PARSERS:
            return extract_script(content, parser_kind, content_hash, PARSER_VERSION)
        if parser_kind != "python":
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=line_count,
            )
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, RecursionError):
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=line_count,
                syntax_error=True,
            )
        collector = _PythonCollector(text)
        try:
            collector.visit(tree)
        except RecursionError:
            return _ParsedSource(
                parser_version=PARSER_VERSION,
                parser_kind=parser_kind,
                content_hash=content_hash,
                line_count=line_count,
                syntax_error=True,
            )
        return _ParsedSource(
            parser_version=PARSER_VERSION,
            parser_kind=parser_kind,
            content_hash=content_hash,
            line_count=line_count,
            extraction_truncated=bool(collector.diagnostics),
            diagnostics=tuple(sorted(collector.diagnostics)),
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
        test_suites: dict[str, str] = {}

        for path, result in sorted(parsed.items()):
            content_hash = file_hashes[path]
            source = PurePosixPath(path)
            language = _LANGUAGES.get(source.suffix.casefold())
            role = _file_role(path)
            file_id = _node_id("file", path)
            metadata: dict[str, str | int | float | bool | None | list[str]] = {
                "role": role,
                "parser": result.parser_kind,
                "extraction_truncated": result.extraction_truncated,
                "extraction_diagnostics": list(result.diagnostics),
                "capabilities": ["definitions", "imports", "call_occurrences"]
                if result.parser_kind == "python" or result.parser_kind in SCRIPT_PARSERS
                else [],
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

            if result.parser_kind == "python" or result.parser_kind in SCRIPT_PARSERS:
                module_name = _module_name(path) if result.parser_kind == "python" else f"js:{path}"
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
                    language=language,
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
                    nodes[symbol_id] = GraphNode(
                        id=symbol_id,
                        kind=symbol.kind,
                        name=symbol.name,
                        file_path=path,
                        line_start=symbol.line_start,
                        line_end=symbol.line_end,
                        language=language,
                        metadata={
                            "qualified_name": qualified,
                            "symbol_kind": symbol.kind,
                            "byte_start": symbol.byte_start,
                            "byte_end": symbol.byte_end,
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
                imported_name = (
                    _resolve_script_import(path, item.module, path_modules)
                    if result.parser_kind in SCRIPT_PARSERS
                    else _resolve_import(
                        module_name,
                        item.module,
                        item.names,
                        item.level,
                        is_package=PurePosixPath(path).name in {"__init__.py", "__init__.pyi"},
                    )
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
                            metadata={
                                "external": not imported_name.startswith("js:unresolved:"),
                                "reference_type": "import",
                            },
                        ),
                    )
                self._add_edge(
                    edges,
                    source_id,
                    target_id,
                    GraphRelation.IMPORTS,
                    GraphProvenance.INFERRED
                    if result.parser_kind in SCRIPT_PARSERS and local_target
                    else GraphProvenance.EXTRACTED,
                    0.75 if result.parser_kind in SCRIPT_PARSERS and local_target else 1.0,
                    f"{path}:{item.line}",
                    resolution_basis="relative_module_candidate"
                    if result.parser_kind in SCRIPT_PARSERS and local_target
                    else "import_syntax",
                    source_expression=item.module,
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
                    result,
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
                        result,
                    )
                if symbol.kind in {GraphNodeKind.CLASS, GraphNodeKind.INTERFACE}:
                    for base in symbol.bases:
                        self._add_expression_edge(
                            nodes,
                            edges,
                            source_id,
                            base,
                            symbol.line_start,
                            path,
                            module_name,
                            symbol,
                            qualified_symbols,
                            result,
                            GraphRelation.EXTENDS,
                            "inheritance",
                        )
                    for interface in symbol.implements:
                        self._add_expression_edge(
                            nodes,
                            edges,
                            source_id,
                            interface,
                            symbol.line_start,
                            path,
                            module_name,
                            symbol,
                            qualified_symbols,
                            result,
                            GraphRelation.IMPLEMENTS,
                            "implementation",
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
                resolution_basis=tuple(sorted(item.resolution_basis)),
                source_expressions=tuple(sorted(item.source_expressions)),
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
        parsed: _ParsedSource,
    ) -> None:
        self._add_expression_edge(
            nodes,
            edges,
            source_id,
            call.name,
            call.line,
            path,
            module_name,
            symbol,
            qualified_symbols,
            parsed,
            GraphRelation.CALLS,
            "call",
        )

    def _add_expression_edge(
        self,
        nodes: dict[str, GraphNode],
        edges: dict[tuple[str, str, str, str], _EdgeAccumulator],
        source_id: str,
        expression: str,
        line: int,
        path: str,
        module_name: str,
        symbol: _SymbolSpec | None,
        qualified_symbols: dict[str, str],
        parsed: _ParsedSource,
        relation: GraphRelation,
        reference_type: str,
    ) -> None:
        # ECMAScript extraction intentionally does not emulate lexical environments,
        # closures, block scopes, re-exports or type-directed dispatch. Calls and
        # inheritance expressions remain occurrences, never guessed global bindings.
        resolution = (
            None
            if parsed.extraction_truncated or parsed.parser_kind in SCRIPT_PARSERS
            else self._resolve_symbol(
                expression,
                module_name,
                symbol,
                qualified_symbols,
                parsed,
                path,
            )
        )
        if resolution is None:
            # The AST proves this expression occurs, not which object it binds to.
            # Keep occurrences distinct across files/scopes rather than merging
            # unrelated receiver expressions into a single "external" symbol.
            target_id = _node_id("reference", path, source_id, str(line), expression)
            nodes[target_id] = GraphNode(
                id=target_id,
                kind=GraphNodeKind.REFERENCE,
                name=expression,
                file_path=path,
                line_start=line,
                line_end=line,
                language=_LANGUAGES.get(PurePosixPath(path).suffix.casefold()),
                source_hash=parsed.content_hash,
                metadata={"resolution": "unresolved", "reference_type": reference_type},
            )
            provenance, confidence, basis = GraphProvenance.EXTRACTED, 1.0, "syntax_occurrence"
        else:
            target_id = resolution.target_id
            # Even an exact lexical/import candidate is not proof of Python
            # runtime dispatch: bindings can be reassigned or monkey patched.
            provenance, confidence, basis = GraphProvenance.INFERRED, 0.75, resolution.basis
        self._add_edge(
            edges,
            source_id,
            target_id,
            relation,
            provenance,
            confidence,
            f"{path}:{line}",
            resolution_basis=basis,
            source_expression=expression,
        )

    def _resolve_symbol(
        self,
        reference: str,
        module_name: str,
        symbol: _SymbolSpec | None,
        qualified_symbols: dict[str, str],
        parsed: _ParsedSource,
        path: str,
    ) -> _SymbolResolution | None:
        """Find a supported static candidate, never a global last-name guess."""
        scopes = {item.qualified_name: item for item in parsed.symbols}
        head, separator, tail = reference.partition(".")
        member_prefixes = ("self.", "cls.") if parsed.parser_kind == "python" else ("this.",)
        if symbol and reference.startswith(member_prefixes) and tail and "." not in tail:
            parent = scopes.get(symbol.parent_qualified_name or "")
            if parent and parent.kind == GraphNodeKind.CLASS:
                candidate = f"{module_name}.{parent.qualified_name}.{tail}"
                if candidate in qualified_symbols:
                    return _SymbolResolution(qualified_symbols[candidate], "class_member_candidate")
        owners: list[str | None] = []
        current = symbol
        while current is not None:
            owners.append(current.qualified_name)
            if head in current.bound_names:
                return None
            current = scopes.get(current.parent_qualified_name or "")
        owners.append(None)
        for owner in owners:
            for item in parsed.imports:
                if item.owner != owner:
                    continue
                for local_name, imported_name in item.aliases:
                    if parsed.parser_kind in SCRIPT_PARSERS and local_name == head:
                        # Module resolution does not prove named/default re-export bindings.
                        return None
                    if local_name != head or imported_name == "*":
                        continue
                    if item.names:
                        imported_module = _resolve_import(
                            module_name,
                            item.module,
                            (),
                            item.level,
                            is_package=PurePosixPath(path).name in {"__init__.py", "__init__.pyi"},
                        )
                        binding = ".".join(
                            part for part in (imported_module, imported_name) if part
                        )
                    else:
                        binding = imported_name
                    candidate = binding + (f".{tail}" if separator else "")
                    target = qualified_symbols.get(candidate)
                    return _SymbolResolution(target, "import_candidate") if target else None
            # A class namespace is not an enclosing lexical scope for methods.
            scoped = scopes.get(owner or "")
            if owner is not None and scoped and scoped.kind == GraphNodeKind.CLASS:
                continue
            prefix = f"{module_name}.{owner}" if owner else module_name
            candidate = f"{prefix}.{reference}"
            target = qualified_symbols.get(candidate)
            if target:
                return _SymbolResolution(target, "lexical_candidate")
        return None

    def _add_edge(
        self,
        edges: dict[tuple[str, str, str, str], _EdgeAccumulator],
        source_id: str,
        target_id: str,
        relation: GraphRelation | str,
        provenance: GraphProvenance,
        confidence: float,
        evidence: str,
        *,
        resolution_basis: str | None = None,
        source_expression: str | None = None,
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
        if resolution_basis:
            current.resolution_basis.add(resolution_basis)
        if source_expression:
            current.source_expressions.add(source_expression)

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


def _resolve_script_import(
    path: str, specifier: str, path_modules: dict[str, tuple[str, str]]
) -> str:
    if not specifier.startswith("."):
        return f"js:package:{specifier}"
    normalized = posixpath.normpath(str(PurePosixPath(path).parent / specifier))
    if normalized.startswith("../") or normalized == ".." or "\\" in normalized:
        return f"js:unresolved:{path}:{specifier}"
    candidates = {normalized}
    if not PurePosixPath(normalized).suffix:
        extensions = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
        candidates.update(normalized + suffix for suffix in extensions)
        candidates.update(normalized + "/index" + suffix for suffix in extensions)
    matches = [
        path_modules[candidate][0]
        for candidate in sorted(candidates)
        if candidate in path_modules and path_modules[candidate][0].startswith("js:")
    ]
    return matches[0] if len(matches) == 1 else f"js:unresolved:{path}:{specifier}"


def _graph_payload(graph: ProjectGraph) -> bytes:
    try:
        return json.dumps(
            graph.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FilesystemFormatError("Value is not valid JSON") from exc


def _graph_digest(graph: ProjectGraph) -> str:
    return hashlib.sha256(_graph_payload(graph)).hexdigest()


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
