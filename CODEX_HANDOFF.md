# CODEX HANDOFF - Orqalis

> **Canonical baseline:** Consolidated End-to-End Design v1.2 (2026-09-10).

## Mission

Implement Orqalis according to the design documents in this package. Orqalis is a provider-agnostic, goal-driven multi-agent engineering orchestrator with durable Git-aware project memory. It coordinates specialized agents/skills, verifies work against explicit acceptance criteria, performs bounded repair loops, updates documentation, and safely commits/pushes accepted changes.

## Source-of-truth order

1. `SIGNOFF.md`
2. `docs/00-product-design.md`
3. `docs/01-system-architecture.md`
4. `docs/02-agent-and-skill-model.md`
5. `docs/03-project-memory.md`
6. `docs/04-workflow-and-acceptance.md`
7. `docs/05-interfaces-and-integrations.md`
8. `docs/06-security-git-and-governance.md`
9. `docs/07-data-model-and-observability.md`
10. `docs/08-features-and-roadmap.md`
11. `docs/09-implementation-plan.md`
12. `docs/10-local-control-center.md`
13. `CONSOLIDATION_NOTES.md`

This v1.2 package supersedes earlier Orqalis files from the session. Do not combine it with the older ZIP/DOCX as parallel requirements. If wording appears ambiguous, follow `SIGNOFF.md`, then the domain-specific canonical document listed above.

## Codex operating instructions

1. Read the design docs before creating code.
2. Inspect the current repository before assuming it is empty.
3. Preserve any existing project conventions unless they conflict with the approved architecture.
4. Work incrementally by implementation phase/PR-sized slice.
5. Do not implement future-phase complexity early without a concrete dependency.
6. Keep domain models independent from FastAPI, MCP, database, and provider SDKs.
7. All external side effects must be behind interfaces/services and testable with fakes.
8. Use Pydantic typed contracts for agent/provider/workflow inputs and outputs.
9. Add database migrations for persistence changes.
10. Add tests in the same change as production code.
11. Prefer deterministic validation over LLM judgment wherever possible.
12. Never allow developer/reviewer agents to directly bypass Git delivery gates.
13. Never store secrets or model scratch reasoning in project memory.
14. Tie durable memory to provenance and Git commit SHAs.
15. Design for process restart/resume from the beginning.
16. Persist the canonical `Event` stream and actor/task/phase timestamps before building UI timers; UI/historical views must be authoritative.
17. Treat the Orchestrator and sub-agents as runtime `ActorSession`s, planned work as `Task`, attempts as `TaskExecution`, and phases/acceptance/repairs as observable persisted state.
18. Never expose private model chain-of-thought in UI, logs, telemetry, or memory.
19. Do not introduce duplicate runtime models (`RunEvent`, `AgentExecution`, alternate timer stores) that compete with the canonical data model.
20. UI progress is deterministic current-plan completion; do not invent ETA/confidence percentages.
21. Implement phase/PR order from `docs/09-implementation-plan.md`; observability/event foundation precedes thin Mission Control.

## Initial stack

- Python 3.12+
- Pydantic v2
- Typer
- FastAPI
- PostgreSQL
- pgvector
- SQLAlchemy 2.x
- Alembic
- pytest
- OpenTelemetry
- React + TypeScript + Vite for Local Control Center
- WebSocket/SSE event streaming
- React Flow / Recharts / Monaco only where required by `docs/10-local-control-center.md`
- Docker for sandboxing later in the plan

Do not require Redis for the first vertical slice. Add it only when distributed locks/queues are needed.

## First implementation target

Complete Phases 0-2 before adding real multi-agent execution:

### Phase A - bootstrap
- Create project structure and quality tooling.
- Implement domain IDs/enums/base models.
- Add settings/logging.
- Add PostgreSQL persistence + migrations.
- Add Typer CLI shell.

### Phase B - Git/project initialization
- Implement repository root detection.
- Implement safe Git service.
- Implement Project persistence.
- Implement `orqalis init`.
- Implement isolated worktree manager.

### Phase C - Project Memory MVP
- Implement file index, snapshots, memory items/sources.
- Implement bootstrap scanner.
- Implement commit-aware incremental refresh.
- Implement semantic interface with pgvector, but keep retrieval functional with structured search if embeddings are unavailable.
- Implement `orqalis memory status`, `orqalis memory search`, and `orqalis context`.

Stop after these phases only if explicitly asked to make a staged handoff; otherwise continue through the implementation plan in order.

## Required architecture invariants

### Orchestrator owns state
Agents return proposals/results. They do not directly mutate the workflow state machine.

### Goal immutability
After execution begins, goal/acceptance changes require an explicit versioned revision.

### Evidence gate
A criterion cannot PASS without evidence references.

### Bounded convergence
Repair loops have a configurable maximum and move to BLOCKED or HUMAN_REVIEW_REQUIRED when exceeded.

### Project memory is advisory
Source code and deterministic tooling remain authoritative. Low-confidence/stale memory triggers targeted verification.

### Provider independence
Core/domain/workflow modules never import provider SDKs.

### Git safety
No force push, destructive clean/reset, protected-branch push, or secret commit by default.

## Required domain contracts

Implement typed versions of at least:
- `Project`
- `ProjectSnapshot`
- `Run`
- `GoalVersion`
- `AcceptanceCriterion`
- `Task`
- `TaskDependency`
- `TaskExecution`
- `PhaseExecution`
- `ActorSession`
- `Event`
- `Evidence`
- `Finding`
- `Artifact`
- `AgentRole`
- `SkillDefinition`
- `ProviderExecutionRequest`
- `ProviderExecutionResult`
- `MemoryItem`
- `MemorySource`
- `ContextPack`

Use UUID/ULID-style IDs consistently. Do not use mutable global state.

## Required service boundaries

Define interfaces/protocols before implementations for:
- ProjectRepository
- RunRepository
- MemoryRepository
- EventRepository
- ProjectionRepository
- GitService
- WorkspaceManager
- ContextService
- MemoryIndexer
- MemoryRetriever
- ProviderAdapter
- SkillRegistry
- Evaluator
- TimingProjectionService
- DocumentationUpdater

## MVP CLI acceptance

The following must work in a fixture Git repository:

```bash
orqalis init
orqalis status
orqalis memory status
orqalis memory search "architecture"
orqalis context "change authentication validation"
```

Later vertical-slice target:

```bash
orqalis run "implement a small validated feature" --branch feature/orqalis-test --no-push
```

The command must produce a persisted run with `GoalVersion`, plan, `TaskExecution` attempts, `ActorSession` activity, canonical `Event`s, validation evidence, review outcome, and final summary.

## MCP target

Once the workflow vertical slice is stable, implement these first MCP tools:

```text
get_project
get_project_context
search_project_memory
start_task
get_run
get_goal
get_plan
get_next_work
report_result
report_finding
review_run
finalize_run
list_agents
list_skills
```

Keep MCP wrappers thin and call application services.

## Definition of Done for each implementation slice

- Code compiles/imports.
- Unit tests added and pass.
- Relevant integration tests pass.
- Lint/type checks pass.
- Migration included when schema changes.
- Public behavior documented.
- No provider-specific leakage into core domain.
- No secrets committed.
- Git diff contains only slice-related changes.

## Commit guidance

Use Conventional Commit style and include architectural significance in the body for non-trivial changes. Keep commits reviewable and phase-aligned rather than producing one monolithic implementation commit.

## Do not do

- Do not build the full advanced dashboard before the core vertical slice; build only the thin Mission Control immediately after canonical events/timing/projections exist.
- Do not fake UI progress with browser-only timers or inferred agent activity.
- Do not build a custom vector database.
- Do not couple memory retrieval solely to embeddings.
- Do not let agents write directly to canonical memory tables.
- Do not let reviewers modify implementation files.
- Do not let a provider conversation become the source of truth for run state.
- Do not swallow tool/test failures to force a PASS.
- Do not auto-push to protected branches.

## Start instruction

Begin by checking the repository state. If the repository is empty or only contains these design docs, implement Phase 0 from `docs/09-implementation-plan.md`. If code already exists, perform a gap analysis against Phases 0-2 and continue from the earliest incomplete requirement. Produce working code and tests, not another architecture proposal.

## Canonical UI/telemetry handoff

Before implementing Mission Control, implement `Event`, `ActorSession`, `TaskExecution`, `PhaseExecution`, monotonic per-run sequencing, timing semantics, and snapshot projections from `docs/07-data-model-and-observability.md`. Then implement the V1 thin UI from Phase 5. Do not use browser-only status/timing mock state except isolated visual unit fixtures.

The required live experience is: visible Orchestrator -> visible sub-agent roster -> current task and timer per agent -> phase/task/acceptance/repair status -> structured activity -> final Git/memory delivery. Full DAG/Gantt/Project Brain analytics are Phase 13: they are not prerequisites for the first working agent runtime, but they are part of the signed-off V1 completion before the Phase 14 release gate.
