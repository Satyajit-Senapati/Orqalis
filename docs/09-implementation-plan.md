# Detailed Implementation Plan

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Delivery strategy

Build Orqalis as vertical slices. Every milestone must produce an executable feature and automated tests. Avoid implementing all agents or integrations before the lifecycle works end to end.

## Phase 0 - Repository foundation

### Objectives
Create a production-quality Python project and architecture boundaries.

### Tasks
- Create `pyproject.toml`, src layout, Ruff/formatter/type-check/test configuration.
- Add Pydantic domain models and common IDs/enums.
- Add settings system with environment overrides.
- Add structured logging and trace context.
- Add persistence interfaces and local PostgreSQL docker-compose.
- Add Alembic migrations.
- Add unit/integration test scaffolding.
- Document developer setup.

### Acceptance
- `pytest` succeeds.
- lint/type-check succeeds.
- database migration up/down works on clean database.
- CLI `orqalis --help` works.

## Phase 1 - Project initialization and Git workspace

### Objectives
Make Orqalis understand a repository and safely create an isolated run workspace.

### Tasks
- Implement repository resolver and root detection.
- Implement Git service wrappers: status, current branch, HEAD, diff names, log range.
- Implement project persistence.
- Implement `orqalis init`.
- Detect common languages/build manifests/tests/instruction files.
- Implement worktree manager with cleanup and collision handling.
- Implement branch/base-commit validation.

### Acceptance
- Can initialize a sample Git repo.
- Re-running init is idempotent.
- A run workspace can be created and removed without altering the source working tree.
- Unsafe branch/worktree operations fail closed.

## Phase 2 - Project Memory MVP

### Objectives
Create persistent, commit-aware context so future tasks avoid full rescans.

### Tasks
- Implement project snapshot and memory tables.
- Implement repository file index with content hash.
- Build deterministic bootstrap scanner.
- Add memory-item provenance and confidence fields.
- Add pgvector support behind embedding interface.
- Implement semantic + structured retrieval.
- Implement `orqalis memory status/search`.
- Implement `orqalis context <task>`.
- Add `indexed_commit_sha` and changed-file incremental refresh.
- Add simple relation graph tables/API.

### Acceptance
- Initial bootstrap stores project summary/file roles/facts.
- Context query returns relevant files/facts with provenance.
- No-change run performs no broad rescan.
- Changing one test/file triggers targeted refresh only.
- Secrets are excluded/redacted from stored memory.

## Phase 3 - Goal and acceptance engine

### Objectives
Turn a user request into a versioned, testable work contract.

### Tasks
- Define `GoalVersion`, `AcceptanceCriterion`, `ValidationSpec` models.
- Implement Requirements Agent interface.
- Implement deterministic validators: command exit code, file existence/diff pattern, test results.
- Persist goal versions.
- Add policies preventing silent goal mutation after execution begins.
- Expose goal in CLI.

### Acceptance
- Example task produces structured goal and criteria.
- Invalid criterion schemas are rejected.
- Criteria can be evaluated deterministically where validator is defined.
- Goal revisions are versioned and auditable.

## Phase 4 - Planner, task DAG, scheduler, and runtime event foundation

### Objectives
Convert goals into dependency-aware executable work.

### Tasks
- Define task/dependency models.
- Implement Planner Agent output schema.
- Validate DAG for cycles/missing dependencies.
- Implement ready-task scheduler.
- Implement status transitions and durable run state.
- Implement cancellation/resume.
- Add durable run event stream with monotonic sequence IDs.
- Persist phase/task/actor timestamps and status transitions.
- Add timing projection service for wall/active/waiting durations.

### Acceptance
- Planner creates valid DAG from fixture tasks.
- Scheduler exposes only ready tasks.
- Process restart resumes persisted run.
- Invalid/cyclic plan is rejected or repaired before execution.
- Events use monotonic per-run sequences and replay reconstructs timing/status projections.
- Actor/task/phase timers survive process restart.


## Phase 5 - Thin Local Control Center

### Objectives
Make orchestration observable early, using the durable event model rather than mock progress.

### Tasks
- Add local FastAPI UI host and static frontend build integration.
- Add run snapshot, agents, tasks, acceptance, metrics, and event endpoints.
- Add WebSocket/SSE live stream with reconnect cursor.
- Build Mission Control: run header, phase timeline, visible Orchestrator, sub-agent cards, current tasks, per-agent/task timers, task counts, acceptance summary, repair status, and live activity.
- Add `orqalis ui`, `orqalis ui --open`, and `orqalis run --open`.
- Bind loopback by default.

### Acceptance
- Active run can be observed in a local browser.
- Orchestrator and every active agent show status, task, and elapsed time.
- Refresh/reconnect reconstructs correct timers/state from persisted events.
- Headless execution works with UI disabled.
- No private chain-of-thought/secrets appear in events.

## Phase 6 - Agent, skill, and provider framework

### Objectives
Make work executable by specialized interchangeable workers.

### Tasks
- Implement role definitions and permission profiles.
- Implement Skill registry/loader with versioned metadata.
- Implement capability matcher.
- Define provider protocol and typed execution contracts.
- Implement first provider adapter (recommended: OpenAI/Codex-compatible path).
- Implement second adapter skeleton to prove provider independence.
- Record execution usage/outcomes.

### Acceptance
- Same task contract can be executed through a mock provider and real configured provider.
- Skills are selected by capability rather than hardcoded task names.
- Provider-specific objects do not leak into domain/workflow modules.

## Phase 7 - Vertical slice executor

### Objectives
Achieve the first complete loop with one Developer, Test, and Reviewer path.

### Tasks
- Implement Developer execution in isolated workspace.
- Implement restricted filesystem/shell tool layer.
- Implement test command runner with captured evidence.
- Implement Reviewer structured output.
- Map evidence to criteria.
- Add final result summary.

### Acceptance
A fixture repository task completes:
`request -> context -> goal -> plan -> implementation -> tests -> review`.

## Phase 8 - Repair/convergence loop

### Objectives
Automatically repair failed acceptance criteria without endless execution.

### Tasks
- Add failed-criterion extraction.
- Implement root-cause/repair planner.
- Generate targeted repair tasks.
- Configure max repair iterations.
- Re-run impacted validators and regression set.
- Add BLOCKED/HUMAN_REVIEW_REQUIRED transitions.

### Acceptance
- Purposefully broken fixture fails first review, receives targeted repair, and passes second review.
- Infinite/oscillating fixture stops at configured maximum.

## Phase 9 - Change Guardian, docs, Git delivery

### Objectives
Safely convert an accepted workspace into a documented Git commit/push.

### Tasks
- Implement diff scope analyzer/Change Guardian.
- Implement secret scanner hooks.
- Implement Documentation Agent over accepted diff.
- Implement final validation gate after docs.
- Generate detailed commit message.
- Implement explicit staging/commit.
- Implement optional push with branch policy.
- Deny force push/protected-branch direct delivery by default.

### Acceptance
- Out-of-scope file change blocks delivery.
- Accepted run updates docs, commits with run ID, and optionally pushes test remote.
- Git operations are idempotent/resumable.

## Phase 10 - Memory curation loop

### Objectives
Let completed runs improve future context.

### Tasks
- Implement Memory Curator input from goal, accepted diff, decisions, evidence.
- Promote only durable source-backed facts.
- Tie promoted facts to resulting commit SHA.
- Supersede affected previous facts.
- Update graph relations and file roles.

### Acceptance
- After a completed task, a new context query includes new architecture/decision knowledge.
- Memory provenance points to the exact commit/run.
- Transient execution chatter is not stored.

## Phase 11 - MCP server

### Objectives
Expose Orqalis as a project brain/workflow service to coding assistants.

### Tasks
- Implement MCP transport and server lifecycle.
- Expose compact context/workflow/capability tool set.
- Add read-only MCP resources.
- Map MCP authentication/policy hooks for future remote mode.
- Write example configurations for supported clients.
- Add end-to-end tests with MCP client fixture.

### Acceptance
- MCP client can retrieve project context.
- Client can create a run, get next work, report result, and request review.
- Tool permissions are enforced independently of client.

## Phase 12 - Claude/Copilot and external adapters

### Objectives
Prove cross-assistant continuity.

### Tasks
- Document Claude Code MCP configuration.
- Document VS Code/GitHub Copilot MCP configuration.
- Implement/test Anthropic provider adapter if Orqalis-driven execution is desired in V1.
- Implement external CLI adapter contract for future assistants.
- Add provider capability configuration.

### Acceptance
- A run created by one MCP client can be inspected/continued by another using the same Orqalis state.


## Phase 13 - Full Control Center

### Objectives
Complete the local visual operating surface after the orchestration vertical slice is reliable.

### Tasks
- Interactive task DAG and agent relationship graph.
- Gantt/timeline with critical path and parallelism.
- Agent detail metrics/utilization/provider usage.
- Acceptance evidence explorer and repair-loop visualization.
- Project Brain memory/knowledge-graph view.
- Changes/diff, tests, tools, and delivery views.
- Historical run/project metrics and run comparison.
- Light/dark/system themes, responsive/a11y, developer mode.

### Acceptance
- User can understand who is working on what, for how long, what is blocked, why a criterion failed, and what Orqalis will do next without reading raw logs.
- Historical runs reconstruct from persisted state/events.

## Phase 14 - Hardening

### Tasks
- Docker sandbox profiles.
- Time/memory/network limits.
- Structured secret redaction.
- OpenTelemetry spans/metrics.
- Failure-injection tests.
- concurrency/locking tests.
- migration compatibility tests.
- performance tests for large repositories.
- documentation completeness and ADRs.

### Release gate for V1
- End-to-end fixture passes reliably.
- Cross-session resume works.
- Memory incremental refresh works.
- MCP context retrieval works.
- Safe commit/push works against test remote.
- Security-denied operations remain denied.
- No core workflow depends on a single provider.
- Thin Mission Control reflects authoritative state/timers and survives refresh/reconnect.
- Orchestrator and active sub-agents expose current tasks/status without chain-of-thought leakage.

## 2. Suggested implementation sequence by pull request

1. `chore: bootstrap Orqalis Python project`
2. `feat(domain): add project run goal task acceptance and runtime models`
3. `feat(persistence): add PostgreSQL repositories migrations and idempotency`
4. `feat(git): add safe repository and worktree services`
5. `feat(cli): add project initialization and status shell`
6. `feat(memory): add project bootstrap index and provenance`
7. `feat(memory): add incremental Git-aware refresh and invalidation`
8. `feat(context): add task Context Pack retrieval`
9. `feat(goal): add versioned goal and acceptance contracts`
10. `feat(observability): add canonical events actor/task/phase timing and projections`
11. `feat(plan): add task DAG scheduler plan versions and work weights`
12. `feat(ui): add thin local Mission Control with reconnect-safe timers`
13. `feat(skills): add skill registry capability matching and permissions`
14. `feat(providers): add provider protocol mock adapter and invocation telemetry`
15. `feat(providers): add first real provider adapter`
16. `feat(execution): add developer test reviewer vertical slice`
17. `feat(repair): add bounded targeted acceptance repair loop`
18. `feat(review): add Change Guardian and final evidence gate`
19. `feat(docs): add documentation and ADR updater`
20. `feat(git): add gated commit and optional push`
21. `feat(memory): add run-to-project Memory Curator`
22. `feat(mcp): expose compact context workflow and capability tools`
23. `docs(integrations): add Codex Claude Code and Copilot setup`
24. `feat(adapters): add second/external provider path and cross-assistant fixture`
25. `feat(ui): add DAG Gantt agent analytics Project Brain diffs tests and delivery`
26. `feat(security): add sandbox command policy redaction and remote UI hardening`
27. `test(e2e): add complete task-to-accepted-commit resume and UI replay scenarios`

## 3. Testing strategy

### Unit tests
Domain validation, DAG algorithms, skill matching, policy decisions, memory ranking, invalidation, commit-message formatting.

### Integration tests
PostgreSQL repositories, Git worktrees, MCP server, provider adapters mocked at network boundary, sandbox command runner.

### E2E fixture repositories
Maintain small repositories representing Python API, React app, Android/Gradle project, and mixed monorepo. Test successful execution, repair loop, stale memory refresh, out-of-scope diff rejection, resume after process failure, and cross-client MCP continuation.

### Golden tests
Store expected structured outputs for context packs, plans, acceptance records, and final run summaries. Avoid golden-testing prose where unnecessary.
