import fnmatch
from pathlib import PurePosixPath
from uuid import uuid5

from orqalis.domain.acceptance import GoalContract
from orqalis.domain.agent import AgentRole
from orqalis.domain.memory import ContextPack
from orqalis.domain.plan import TaskPlan
from orqalis.domain.task import Task, TaskDependency

_CAPABILITY_SUFFIXES = {
    "python": (".py", ".pyi"),
    "typescript": (".ts", ".tsx", ".mts", ".cts"),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "react": (".tsx", ".jsx"),
    "database": (".sql", ".ddl", ".prisma"),
    "documentation": (".md", ".mdx", ".rst", ".txt"),
}
_DATABASE_DIRECTORIES = {"alembic", "database", "db", "migrations", "persistence", "prisma"}
_DOCUMENTATION_DIRECTORIES = {"docs", "documentation"}


def _normalize_scope(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    return "." if normalized in {".", "./"} else normalized.removeprefix("./").rstrip("/")


def _matches_scope(path: str, scope: str) -> bool:
    return scope == "." or fnmatch.fnmatchcase(path, scope) or path.startswith(f"{scope}/")


def implementation_capabilities(goal: GoalContract, context: ContextPack) -> tuple[str, ...]:
    """Infer skills from accepted paths, never unrelated project languages or goal prose.

    Explicit filenames/globs also cover new files missing from Project Memory. Directory
    scopes use only relevant files inside that directory, with deterministic database/docs
    directory cues. Prose scopes do not activate a technology simply because it exists in
    the repository; names with spaces are considered when matched by an actual context path.
    """
    scopes = tuple(_normalize_scope(scope) for scope in goal.goal.scope)
    excluded = tuple(_normalize_scope(scope) for scope in goal.goal.out_of_scope)
    paths = {scope for scope in scopes if scope and not any(c.isspace() for c in scope)}
    paths.update(
        normalized
        for path in context.relevant_files
        if (normalized := _normalize_scope(path))
        and any(_matches_scope(normalized, scope) for scope in scopes)
    )
    capabilities = set()
    for path in paths:
        if any(_matches_scope(path, scope) for scope in excluded):
            continue
        source = PurePosixPath(path.casefold())
        suffix = source.suffix
        for capability, suffixes in _CAPABILITY_SUFFIXES.items():
            if suffix in suffixes:
                capabilities.add(capability)
        if (
            suffix not in _CAPABILITY_SUFFIXES["documentation"]
            and not _DOCUMENTATION_DIRECTORIES.intersection(source.parts)
            and (_DATABASE_DIRECTORIES.intersection(source.parts) or source.name == "alembic.ini")
        ):
            capabilities.add("database")
        if _DOCUMENTATION_DIRECTORIES.intersection(source.parts) or source.name in {
            "readme",
            "changelog",
            "contributing",
        }:
            capabilities.add("documentation")
    return tuple(capability for capability in _CAPABILITY_SUFFIXES if capability in capabilities)


class VerticalPlanner:
    """Minimal deterministic Developer -> Test -> Reviewer DAG for a single slice."""

    def plan(self, goal: GoalContract, context: ContextPack, version: int = 1) -> TaskPlan:
        ids = tuple(criterion.id for criterion in goal.criteria)
        tasks = tuple(
            Task(
                id=uuid5(goal.goal.id, f"vertical:{version}:{role}"),
                run_id=goal.goal.run_id,
                plan_version=version,
                description=description,
                expected_outcome=outcome,
                preferred_role=role,
                validation_method=validation,
                acceptance_criterion_ids=ids,
                required_capabilities=("evidence_review",)
                if role == AgentRole.REVIEWER
                else implementation_capabilities(goal, context)
                if role == AgentRole.DEVELOPER
                else (),
            )
            for role, description, outcome, validation in (
                (
                    AgentRole.DEVELOPER,
                    goal.goal.goal,
                    "Implement the accepted scope with focused code and test changes",
                    "Acceptance validators",
                ),
                (
                    AgentRole.TESTER,
                    "Validate the current acceptance contract",
                    "Persist deterministic evidence for every executable criterion",
                    "Acceptance validators",
                ),
                (
                    AgentRole.REVIEWER,
                    "Review implementation against every acceptance criterion",
                    "Return evidence-backed PASS/FAIL for each criterion",
                    "Structured acceptance review",
                ),
            )
        )
        return TaskPlan(
            run_id=goal.goal.run_id,
            goal_version_id=goal.goal.id,
            version=version,
            tasks=tasks,
            dependencies=(
                TaskDependency(task_id=tasks[1].id, depends_on_task_id=tasks[0].id),
                TaskDependency(task_id=tasks[2].id, depends_on_task_id=tasks[1].id),
            ),
        )
