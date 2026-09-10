from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.delivery.guardian import ChangeGuardian
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import ExecutionPolicy, RunWorkspace
from orqalis.git.service import LocalGitService


def workspace(repo: Path, paths: tuple[str, ...]) -> RunWorkspace:
    git = LocalGitService()
    return RunWorkspace(
        run_id=uuid4(),
        path=repo,
        branch="main",
        base_commit=git.status(repo).head,
        policy=ExecutionPolicy(write_paths=paths),
    )


def test_guardian_independently_checks_scope_and_current_tree(git_repo: Path) -> None:
    binding = workspace(git_repo, ("main.py",))
    (git_repo / "main.py").write_text("answer = 43\n")
    guardian = ChangeGuardian(LocalGitService())
    accepted = guardian.inspect(binding, DeliveryPolicy(), uuid4(), "implementation")
    assert accepted.passed and accepted.changes[0].path == "main.py"
    (git_repo / "unrelated.py").write_text("unrelated = True\n")
    rejected = guardian.inspect(binding, DeliveryPolicy(), uuid4(), "implementation")
    assert not rejected.passed
    assert any(finding.category == "scope" for finding in rejected.findings)
    assert rejected.tree_hash != accepted.tree_hash


@pytest.mark.parametrize(
    ("path", "content", "category"),
    [
        ("main.py", "api_key=unsafe-value\n", "secret"),
        ("pyproject.toml", "[project]\nname='changed'\n", "sensitive_configuration"),
        ("tests/test_main.py", "# test removed\n", "test_reduction"),
        ("dist/output.txt", "generated\n", "generated"),
        ("main.py", "\x00binary", "binary"),
    ],
)
def test_guardian_blocks_secret_governance_test_reduction_and_binary_changes(
    git_repo: Path,
    path: str,
    content: str,
    category: str,
) -> None:
    binding = workspace(git_repo, ("*",))
    target = git_repo / path
    target.parent.mkdir(exist_ok=True)
    target.write_text(content)
    report = ChangeGuardian(LocalGitService()).inspect(binding, DeliveryPolicy(), uuid4(), "final")
    assert not report.passed
    assert category in {finding.category for finding in report.findings}
    assert "unsafe-value" not in report.model_dump_json()
