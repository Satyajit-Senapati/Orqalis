import json
import subprocess
from pathlib import Path

from orqalis.bootstrap import ProjectBootstrapService
from orqalis.domain.project import Project
from orqalis.persistence.filesystem.io import read_json_object
from orqalis.persistence.filesystem.layout import bootstrap_project_store


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "Orqalis Tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Orqalis Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
        },
    )


def repository(tmp_path: Path) -> tuple[Path, Project]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "pyproject.toml").write_text(
        "[build-system]\nrequires=[]\nbuild-backend='x'\n"
        "[tool.pytest.ini_options]\ntestpaths=['tests']\n"
        "[tool.ruff]\nline-length=100\n",
        encoding="utf-8",
    )
    (repo / "app.py").write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("from app import hello\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture")
    project = Project(name="Fixture", repo_root=repo, default_branch="main")
    bootstrap_project_store(repo, project_id=project.id, project_name=project.name)
    return repo, project


def test_bootstrap_creates_project_memory_graph_and_index(tmp_path: Path) -> None:
    repo, project = repository(tmp_path)
    result = ProjectBootstrapService(repo).bootstrap(project)
    store = repo / ".orqalis"

    assert result.files_inspected == 3
    assert result.languages == ("Python",)
    assert {command.name for command in result.commands} == {"build", "lint", "test"}
    assert (store / "project" / "summary.md").is_file()
    assert read_json_object(store / "project" / "repository.yaml")["root"] == "."
    assert (store / "memory" / "architecture.md").is_file()
    assert (store / "memory" / "graph" / "graph.json").is_file()
    assert (store / "index" / "manifest.json").is_file()
    manifest = read_json_object(store / "manifest.yaml")
    graph = manifest["graph"]
    assert isinstance(graph, dict) and graph["indexed_branch"] == "main"


def test_bootstrap_preserves_curated_project_documents(tmp_path: Path) -> None:
    repo, project = repository(tmp_path)
    service = ProjectBootstrapService(repo)
    service.bootstrap(project)
    summary = repo / ".orqalis" / "project" / "summary.md"
    summary.write_text("# Curated by a person\n", encoding="utf-8")

    service.bootstrap(project)
    assert summary.read_text(encoding="utf-8") == "# Curated by a person\n"


def test_bootstrap_excludes_secret_bearing_commands(tmp_path: Path) -> None:
    repo, project = repository(tmp_path)
    (repo / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "safe": "echo safe",
                    "unsafe": (
                        "curl -H 'Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz123456'"
                    ),
                }
            }
        ),
        encoding="utf-8",
    )
    git(repo, "add", "package.json")
    git(repo, "commit", "-m", "package")

    result = ProjectBootstrapService(repo).bootstrap(project)
    names = {command.name for command in result.commands}
    assert "safe" in names
    assert "unsafe" not in names
    commands = (repo / ".orqalis" / "project" / "commands.yaml").read_text()
    assert "ghp_" not in commands
