import asyncio
from pathlib import Path

import pytest

from orqalis.domain.acceptance import CriterionDefinition, FileValidation, GoalDraft
from orqalis.domain.agent import AgentRole
from orqalis.domain.capabilities import ToolName
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import CriterionReview, ExecutionPolicy, ReviewResult, WorkerResult
from orqalis.domain.provider import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderToolCall,
)
from orqalis.providers.fake import FakeProvider
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git

STACKS = {
    "react": (
        {
            "package.json": '{"name":"react-fixture","dependencies":{"react":"19.2.0"}}\n',
            "src/App.tsx": "export function App() { return <h1>Before</h1> }\n",
        },
        "src/App.tsx",
        "export function App() { return <h1>Accepted</h1> }\n",
        {"TypeScript"},
    ),
    "android": (
        {
            "build.gradle.kts": 'plugins { id("com.android.application") }\n',
            "app/src/main/java/example/Screen.kt": 'package example\nconst val title = "Before"\n',
        },
        "app/src/main/java/example/Screen.kt",
        'package example\nconst val title = "Accepted"\n',
        {"Kotlin"},
    ),
    "monorepo": (
        {
            "services/api/pyproject.toml": '[project]\nname="fixture-api"\n',
            "services/api/main.py": 'title = "Before"\n',
            "apps/web/package.json": '{"name":"fixture-web"}\n',
            "apps/web/src/App.tsx": 'export const title = "Before";\n',
        },
        "apps/web/src/App.tsx",
        'export const title = "Accepted";\n',
        {"Python", "TypeScript"},
    ),
}


@pytest.mark.parametrize("stack", tuple(STACKS))
def test_language_neutral_source_contract_to_accepted_commit(
    tmp_path: Path,
    stack: str,
) -> None:
    contents, source, replacement, languages = STACKS[stack]
    repo = tmp_path / stack
    repo.mkdir()
    for path, content in contents.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    fixture_git(repo, "init", "-b", "main")
    fixture_git(repo, "add", ".")
    fixture_git(repo, "commit", "-m", "test: seed stack fixture")
    sdk = Orqalis(root=repo)
    project = sdk.initialize(repo)
    assert set(project.settings.repository_profile.languages) == languages
    draft = GoalDraft(
        goal="Change the displayed title to Accepted",
        scope=(source, "README.md"),
        definition_of_done=("The source contract and review pass",),
        criteria=(
            CriterionDefinition(
                key="AC-1",
                description="Source has the accepted title",
                validation_spec=FileValidation(path=source, contains="Accepted"),
            ),
        ),
    )
    run = sdk.prepare_run(project.id, draft.goal, "feature/title", draft).run

    if stack == "monorepo":
        (repo / source).write_text('export const title = "New source branch";\n', encoding="utf-8")
        fixture_git(repo, "add", source)
        fixture_git(repo, "commit", "-m", "test: advance source branch independently")

    def respond(request: ProviderExecutionRequest) -> ProviderExecutionResult:
        assert request.context.freshness.current_commit == run.base_commit
        assert request.context.freshness.fresh
        if request.role == AgentRole.DEVELOPER:
            if not request.observations:
                return ProviderExecutionResult(
                    tool_calls=(
                        ProviderToolCall(
                            id="write-source",
                            name=ToolName.FILE_WRITE,
                            arguments={"path": source, "content": replacement},
                        ),
                    )
                )
            return ProviderExecutionResult(
                output=WorkerResult(
                    completed=True,
                    summary="Updated title",
                    artifact_paths=(source,),
                ).model_dump(mode="json")
            )
        assert request.acceptance
        return ProviderExecutionResult(
            output=ReviewResult(
                overall="PASS",
                criteria=tuple(
                    CriterionReview(
                        criterion_id=c.id,
                        status="PASS",
                        reason="Verified actual source evidence",
                        evidence_refs=c.evidence_refs,
                        source_checks=(),
                    )
                    for c in request.acceptance.criteria
                ),
                blocking_findings=(),
                non_blocking_findings=(),
            ).model_dump(mode="json")
        )

    summary = asyncio.run(
        sdk.executor(tmp_path / "workers", (FakeProvider(respond),)).execute(
            run.id,
            "fixture",
            ExecutionPolicy(write_paths=(source, "README.md")),
        )
    )
    delivered = asyncio.run(
        sdk.delivery.finalize(
            run.id,
            DeliveryPolicy(
                documentation_path="README.md",
                author_name="Orqalis Test",
                author_email="test@orqalis.invalid",
            ),
        )
    )
    assert delivered.state == "COMPLETED" and delivered.commit_sha
    assert (summary.workspace / source).read_text() == replacement
    if stack == "monorepo":
        assert "New source branch" in (repo / source).read_text()
    else:
        assert (repo / source).read_text() == contents[source]
    assert sdk.git.status(repo).branch == "main"
    assert sdk.snapshot(run.id).plan_completion == 100
    assert (
        sdk.brain.get(project.id, "title", run.id).freshness.indexed_commit == delivered.commit_sha
    )
