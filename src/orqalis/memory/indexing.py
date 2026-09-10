import ast
import hashlib
from pathlib import PurePosixPath

from orqalis.domain.base import Contract
from orqalis.domain.memory import MemoryType
from orqalis.security.redaction import redact


class IndexedContent(Contract):
    path: str
    content_hash: str
    language: str | None
    role: str
    memory_type: MemoryType
    summary: str


class DeterministicMemoryIndexer:
    """Deterministic source-backed summaries; never executes repository code."""

    MAX_BYTES = 256_000
    _ALLOWED = {
        ".py",
        ".md",
        ".rst",
        ".txt",
        ".toml",
        ".json",
        ".yaml",
        ".yml",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".kt",
        ".java",
        ".go",
        ".rs",
        ".cs",
    }

    def allows(self, path: str) -> bool:
        source = PurePosixPath(path.lower())
        blocked = {
            ".git",
            ".orqalis",
            ".tools",
            ".venv",
            "node_modules",
            "dist",
            "build",
            "secrets",
            "credentials",
            "__pycache__",
        }
        if any(part in blocked for part in source.parts):
            return False
        if any(word in source.name for word in (".env", "credential", "secret", "private_key")):
            return False
        if source.name.endswith((".lock", "-lock.json")):
            return False
        return source.suffix in self._ALLOWED

    def index(self, path: str, content: bytes) -> IndexedContent | None:
        if not self.allows(path) or len(content) > self.MAX_BYTES or b"\x00" in content:
            return None
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        # Exclude credential blocks and explicitly private reasoning rather than store excerpts.
        if any(
            marker in text.lower()
            for marker in (
                "-----begin private key",
                "-----begin rsa private key",
                "chain_of_thought",
                "<thinking>",
                "<analysis>",
            )
        ):
            return None
        source = PurePosixPath(path)
        role = "source"
        category = MemoryType.REPOSITORY_MAP
        language = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".kt": "Kotlin",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cs": "C#",
        }.get(source.suffix)
        details = ""
        if source.name in {"AGENTS.md", "CLAUDE.md", "copilot-instructions.md"}:
            role, category = "instructions", MemoryType.CONVENTION
            details = redact(text[:6000])
        elif source.suffix in {".md", ".rst", ".txt"}:
            role = "documentation"
            category = MemoryType.DECISION if "adr" in path.lower() else MemoryType.ARCHITECTURE
            details = redact(text[:6000])
        elif source.suffix == ".py":
            language = "Python"
            try:
                tree = ast.parse(text)
                names = [
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                ]
                details = "Top-level definitions: " + ", ".join(names[:80])
            except SyntaxError:
                details = "Python file; syntax requires verification."
        elif source.name in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"}:
            role = "build_manifest"
        if "tests" in source.parts or source.name.startswith("test_") or ".test." in source.name:
            role = "test"
        return IndexedContent(
            path=path,
            content_hash=hashlib.sha256(content).hexdigest(),
            language=language,
            role=role,
            memory_type=category,
            summary=f"{role}: {path}. {details}".strip(),
        )
