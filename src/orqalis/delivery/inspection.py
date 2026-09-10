from collections.abc import Callable
from difflib import unified_diff
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.base import Contract
from orqalis.domain.errors import NotFoundError
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.git.service import LocalGitService
from orqalis.security.redaction import safe_diagnostic


class DiffView(Contract):
    path: str
    diff: str
    truncated: bool


class ChangeInspectionService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], git: LocalGitService) -> None:
        self.factory, self.git = factory, git

    def diff(self, run_id: UUID, path: str) -> DiffView:
        with self.factory() as uow:
            workspace = uow.execution.workspace(run_id)
            if workspace is None:
                raise NotFoundError("Run workspace missing")
        files = ScopedFilesystem(workspace.path, workspace.policy)
        target = files.target(path)
        original = self.git.read_file_if_present(
            workspace.path,
            workspace.base_commit,
            path,
            workspace.policy.max_file_bytes,
        )
        before = safe_diagnostic(original.decode("utf-8", errors="replace")) if original else ""
        after = files.read(path) if target.exists() else ""
        parts: list[str] = []
        size = 0
        truncated = False
        for line in unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        ):
            if size + len(line) > 100_000:
                parts.append(line[: 100_000 - size])
                truncated = True
                break
            parts.append(line)
            size += len(line)
        return DiffView(path=path, diff="".join(parts), truncated=truncated)
