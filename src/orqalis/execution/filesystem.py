import fnmatch
import hashlib
import os
import tempfile
from pathlib import Path

from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ExecutionPolicy
from orqalis.git.service import validate_relative_path
from orqalis.security.redaction import safe_diagnostic


class ScopedFilesystem:
    def __init__(self, root: Path, policy: ExecutionPolicy) -> None:
        self.root = root.resolve(strict=True)
        self.policy = policy

    def target(self, path: str, write: bool = False) -> Path:
        validate_relative_path(path)
        pieces = path.split("/")
        if any(
            part.casefold() in {".git", ".env", ".ssh", ".aws", ".codex", ".agents"}
            or part.casefold().startswith(".env.")
            for part in pieces
        ):
            raise PolicyDeniedError("Protected or credential paths are unavailable to workers")
        target = self.root
        for part in pieces:
            target = target / part
            if target.is_symlink() or target.is_junction():
                raise PolicyDeniedError("Links and junctions are not permitted in tool paths")
        if not target.resolve().is_relative_to(self.root):
            raise PolicyDeniedError("Tool path escapes workspace")
        if target.is_file() and target.stat().st_nlink > 1:
            raise PolicyDeniedError("Hard-linked files are not permitted")
        if write and not any(
            fnmatch.fnmatchcase(path, pattern) for pattern in self.policy.write_paths
        ):
            raise PolicyDeniedError("Write lies outside explicitly configured scope")
        return target

    def read(self, path: str) -> str:
        target = self.target(path)
        if not target.is_file() or target.stat().st_size > self.policy.max_file_bytes:
            raise PolicyDeniedError("File is missing or exceeds the tool limit")
        try:
            with target.open("rb") as stream:
                raw = stream.read(self.policy.max_file_bytes + 1)
            if len(raw) > self.policy.max_file_bytes:
                raise PolicyDeniedError("File exceeds the tool limit")
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise PolicyDeniedError("Binary files are not readable by this tool") from None
        return safe_diagnostic(content)

    def write(self, path: str, content: str) -> str:
        if (
            len(content.encode()) > self.policy.max_file_bytes
            or safe_diagnostic(content) != content
        ):
            raise PolicyDeniedError("Write content exceeds policy or contains sensitive data")
        target = self.target(path, write=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = self.target(path, write=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".orqalis-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            self.target(path, write=True)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return hashlib.sha256(content.encode()).hexdigest()
