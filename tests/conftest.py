import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


def fixture_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Orqalis Test",
            "-c",
            "user.email=test@orqalis.invalid",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    fixture_git(repo, "init", "-b", "main")
    (repo / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")
    (repo / "main.py").write_text("answer = 42\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("Run tests before delivery.\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_main.py").write_text("def test_answer():\n    assert 42 == 42\n")
    fixture_git(repo, "add", ".")
    fixture_git(repo, "commit", "-m", "test: create fixture")
    return repo


@pytest.fixture()
def commit_all() -> "Callable[[Path], str]":
    def commit(repo: Path) -> str:
        fixture_git(repo, "add", ".")
        fixture_git(repo, "commit", "-m", "test: update fixture")
        return fixture_git(repo, "rev-parse", "HEAD")

    return commit
