import difflib
import fnmatch
import hashlib
from collections.abc import Callable
from uuid import UUID, uuid5

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.core.runtime_support import emit, locked_run
from orqalis.domain.agent import ActorStatus, AgentRole
from orqalis.domain.artifact import Finding
from orqalis.domain.base import utc_now
from orqalis.domain.delivery import ChangedFile, ChangeReport, DeliveryPolicy
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.events import EventPayload, EventType
from orqalis.domain.execution import RunWorkspace
from orqalis.execution.filesystem import ScopedFilesystem
from orqalis.execution.review import workspace_digest
from orqalis.git.service import LocalGitService
from orqalis.security.redaction import safe_diagnostic

_SENSITIVE = {
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "uv.lock",
    "poetry.lock",
    "requirements.txt",
    "dockerfile",
    "compose.yaml",
    ".gitmodules",
    ".gitattributes",
}
_GENERATED = {"node_modules", "dist", "build", "__pycache__", ".venv"}
_TEST_MARKERS = ("def test_", "async def test_", "test(", "it(", "describe(")


class ChangeGuardian:
    """Independent deterministic scope/safety review; never accepts implementer assertions."""

    def __init__(self, git: LocalGitService) -> None:
        self.git = git

    def inspect(
        self, workspace: RunWorkspace, policy: DeliveryPolicy, actor_id: UUID, checkpoint: str
    ) -> ChangeReport:
        files = ScopedFilesystem(workspace.path, workspace.policy)
        findings: list[Finding] = []
        changes = []

        def flag(path: str, category: str, summary: str) -> None:
            findings.append(
                Finding(
                    run_id=workspace.run_id,
                    severity="blocking",
                    category=category,
                    summary=summary,
                    source_ref=safe_diagnostic(path),
                )
            )

        base_paths = set(self.git.tracked_files(workspace.path, workspace.base_commit))
        for path in self.git.status(workspace.path).changed_paths:
            if safe_diagnostic(path) != path:
                flag(path, "secret", "Sensitive content appears in a file name")
            if not any(
                fnmatch.fnmatchcase(path, pattern) for pattern in workspace.policy.write_paths
            ):
                flag(path, "scope", "File lies outside the accepted write scope")
            parts = path.lower().split("/")
            if any(part in _GENERATED for part in parts):
                flag(path, "generated", "Generated/build output must not be delivered")
            sensitive = parts[-1] in _SENSITIVE or parts[0] in {".github", ".gitlab", ".husky"}
            if sensitive and not any(
                fnmatch.fnmatchcase(path, pattern) for pattern in policy.approved_sensitive_paths
            ):
                flag(
                    path,
                    "sensitive_configuration",
                    "Build, dependency or governance change needs explicit policy",
                )
            try:
                target = files.target(path)
                after = target.read_bytes() if target.is_file() else None
                if after is not None and len(after) > 10_000_000:
                    raise PolicyDeniedError("Oversized change")
                before = self.git.read_file_if_present(
                    workspace.path, workspace.base_commit, path, 10_000_000
                )
            except (OSError, PolicyDeniedError):
                flag(path, "unsafe_path", "File cannot be safely inspected")
                continue
            if before is None and path in base_paths:
                flag(
                    path,
                    "unsupported_source",
                    "Original file is too large or is not a regular file",
                )
            old_hash = hashlib.sha256(before).hexdigest() if before is not None else None
            new_hash = hashlib.sha256(after).hexdigest() if after is not None else None
            binary = False
            try:
                old_text = (before or b"").decode("utf-8")
                new_text = (after or b"").decode("utf-8")
                if b"\x00" in (before or b"") + (after or b""):
                    raise UnicodeDecodeError("utf-8", b"\x00", 0, 1, "binary")
            except UnicodeDecodeError:
                old_text, new_text, binary = "", "", True
                flag(path, "binary", "Binary changes require explicit human inspection")
            if safe_diagnostic(new_text) != new_text:
                flag(path, "secret", "Secret-like or private diagnostic content detected")
            diff = list(difflib.ndiff(old_text.splitlines(), new_text.splitlines()))
            added = sum(line.startswith("+ ") for line in diff)
            deleted = sum(line.startswith("- ") for line in diff)
            if (
                deleted > 5
                and deleted / max(len(old_text.splitlines()), 1) > policy.max_deleted_line_ratio
            ):
                flag(path, "deletion_spike", "Change removes a large fraction of this file")
            if ("test" in parts[-1] or "tests" in parts) and any(
                line.startswith("- ") and any(marker in line[2:] for marker in _TEST_MARKERS)
                for line in diff
            ):
                flag(path, "test_reduction", "Existing tests were removed or rewritten")
            changes.append(
                ChangedFile(
                    path=safe_diagnostic(path),
                    status="deleted"
                    if after is None
                    else "added"
                    if before is None
                    else "modified",
                    old_hash=old_hash,
                    new_hash=new_hash,
                    added_lines=added,
                    deleted_lines=deleted,
                    binary=binary,
                )
            )
        try:
            tree_hash = workspace_digest(workspace, self.git)
        except PolicyDeniedError:
            # The failed report remains auditable but cannot authorize a tree.
            tree_hash = "unverified"
        return ChangeReport(
            run_id=workspace.run_id,
            actor_session_id=actor_id,
            checkpoint="final" if checkpoint == "final" else "implementation",
            base_commit=workspace.base_commit,
            tree_hash=tree_hash,
            passed=not findings and tree_hash != "unverified",
            changes=tuple(changes),
            findings=tuple(findings),
        )


class GuardianService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], guardian: ChangeGuardian) -> None:
        self.factory, self.guardian = factory, guardian

    def inspect(
        self, run_id: UUID, actor_id: UUID, policy: DeliveryPolicy, checkpoint: str
    ) -> ChangeReport:
        with self.factory() as uow:
            run = locked_run(uow, run_id)
            actor = next((item for item in uow.runtime.actors(run_id) if item.id == actor_id), None)
            if (
                actor is None
                or actor.role != AgentRole.CHANGE_GUARDIAN
                or actor.status != ActorStatus.WORKING
            ):
                raise PolicyDeniedError(
                    "Only an independent active Change Guardian may certify delivery"
                )
            workspace = uow.execution.workspace(run_id)
            if workspace is None:
                raise NotFoundError("Run workspace missing")
            report = self.guardian.inspect(workspace, policy, actor_id, checkpoint)
            if checkpoint == "final":
                accepted = [
                    r for r in uow.delivery.guardians(run_id) if r.checkpoint == "implementation"
                ]
                findings = list(report.findings)
                if not accepted:
                    raise PolicyDeniedError("Implementation certification is missing")
                old = {c.path: c.new_hash for c in accepted[-1].changes}
                new = {c.path: c.new_hash for c in report.changes}
                for path in old.keys() | new.keys():
                    if path != policy.documentation_path and old.get(path) != new.get(path):
                        findings.append(
                            Finding(
                                run_id=run_id,
                                severity="blocking",
                                category="post_review_change",
                                summary="Non-documentation content changed after acceptance",
                                source_ref=path,
                            )
                        )
                report = report.model_copy(
                    update={
                        "findings": tuple(findings),
                        "passed": report.passed and not findings,
                    }
                )
            report = report.model_copy(
                update={
                    "id": uuid5(
                        run_id,
                        f"guardian:{actor_id}:{checkpoint}:{report.tree_hash}:"
                        + hashlib.sha256(policy.model_dump_json().encode()).hexdigest(),
                    ),
                }
            )
            existing = next(
                (item for item in uow.delivery.guardians(run_id) if item.id == report.id), None
            )
            if existing:
                return existing
            uow.delivery.save_guardian(report)
            emit(
                uow,
                run,
                EventType.CHANGE_GUARD_COMPLETED,
                f"guardian:{report.id}",
                utc_now(),
                EventPayload(
                    status="PASS" if report.passed else "FAIL",
                    summary=f"Inspected {len(report.changes)} changed files",
                ),
                actor_id,
            )
            uow.commit()
            return report
