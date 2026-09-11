# ORQALIS - Consolidated End-to-End System Design v1.2

Canonical baseline dated 2026-09-10. Supersedes earlier Orqalis design artifacts from this session.


---

<!-- SOURCE: SIGNOFF.md -->

# Orqalis Architecture and Product Design Sign-Off

**Status:** APPROVED CANONICAL BASELINE FOR IMPLEMENTATION  
**Baseline:** Consolidated End-to-End Design v1.2  
**Date:** 2026-09-10  
**Supersedes:** Original Orqalis handoff package and Enhanced v1.1 package from this session.

## 1. Approved product scope

Orqalis is a provider-agnostic, goal-driven multi-agent engineering orchestrator and durable project-intelligence layer. The canonical scope includes Git-aware Project Memory/Context Packs; versioned goals and measurable acceptance criteria; dependency-aware planning/scheduling; specialized agents with dynamic skills; provider abstraction; deterministic Orchestrator-owned state; resumable execution; evidence-based review; bounded targeted repair; Change Guardian; documentation; gated commit/optional push; memory curation; CLI/MCP/REST/WebSocket interfaces; cross-assistant continuity; durable telemetry; and a local browser Control Center.

## 2. Approved Local Control Center scope

The Local Control Center is a core observability/operating surface and a client of Orqalis Core. It must expose:
- the Orchestrator as a visible first-class runtime actor;
- all active/queued/completed/blocked sub-agent sessions, providers/models where known, loaded skills, current tasks, dependencies, and structured activity;
- authoritative run/phase/task/agent wall, active, waiting, blocked, and queue timing;
- deterministic plan completion, phase state, task counts, attempts, blockers, parallelism, critical path, and repair loops;
- acceptance criteria, validators, evidence, failures, and targeted repair linkage;
- tool/test/provider usage, tokens and reliable cost when available;
- Project Brain memory freshness, Context Pack retrieval, provenance, invalidation, and promotion;
- Git diff/documentation/change-guardian/final-validation/commit/push/memory-finalization state;
- historical replay and project/run statistics derived from persisted state/events.

The browser must never simulate workflow truth, fabricate timers/progress, expose private model chain-of-thought, or bypass policy/Git gates.

## 3. Canonical architectural invariants

1. The Orchestrator owns canonical workflow state and state transitions.
2. Agents are specialized workers that return typed results/proposals; they cannot bypass state, evidence, security, or delivery gates.
3. Goals/acceptance criteria are explicit and versioned; material changes after execution begins create a new goal version.
4. PASS requires evidence. Deterministic validation is preferred over model judgment when possible.
5. Repair is targeted, bounded, auditable, and escalates when convergence fails.
6. Project Memory is advisory; source code, Git state, deterministic tools, and validation remain authoritative.
7. Durable memory has provenance, confidence/status, and Git commit association; stale knowledge is incrementally invalidated.
8. Provider and interface independence are architectural requirements. CLI, MCP, REST, UI, Codex, Claude, Copilot, and future clients use one core.
9. External side effects are permissioned, idempotent where feasible, auditable, and behind testable services.
10. Git delivery is gated; force push, protected-branch bypass, destructive cleanup, and secret commits are denied by default.
11. Runtime telemetry is typed, durable, replayable, sequence-ordered per run, privacy-safe, and the sole source for authoritative UI timing/status.
12. The UI is optional for headless execution and cannot become a second workflow engine.
13. Private chain-of-thought/scratch reasoning and secrets are never persisted in memory, events, logs, artifacts, or UI.
14. Process restart/resume is designed from the beginning; completed non-repeatable side effects are not duplicated.

## 4. Canonical implementation sequence

0. Repository/domain/persistence foundation.  
1. Safe Git/project initialization and isolated workspace.  
2. Project Memory MVP and Context Packs.  
3. Versioned goals and acceptance engine.  
4. Planner/DAG/scheduler plus durable event/timing/projection foundation.  
5. Thin Local Mission Control.  
6. Agent/skill/provider framework.  
7. Developer/Test/Reviewer vertical execution slice.  
8. Bounded repair/convergence.  
9. Change Guardian, docs, final validation, commit/push.  
10. Memory curation/finalization.  
11. MCP server.  
12. Cross-assistant/external provider integrations.  
13. Full Control Center.  
14. Security/scale/reliability hardening and release gate.

This ordering is intentional: events/timing are built before the thin UI; the thin UI arrives early enough to observe the runtime; advanced visualization follows a working orchestration vertical slice.

## 5. Canonical terminology decisions

- Use **Event** as the single durable append-only runtime-event entity; do not create a parallel `RunEvent` model.
- Use **ActorSession** for runtime Orchestrator/sub-agent sessions; do not maintain competing `AgentExecution` and `AgentSession` entities.
- Use **Task** for planned work and **TaskExecution** for each attempt.
- Use **GoalVersion** for immutable/versioned execution goals.
- UI percentage means **plan completion**, not ETA or model-estimated confidence.

## 6. Implementation authority

`docs/` and this `SIGNOFF.md` are the architecture source of truth. `docs/09-implementation-plan.md` is the authoritative phase/PR sequence. `CODEX_HANDOFF.md` tells Codex how to execute the plan. `docs/10-local-control-center.md` is the authoritative browser UX/runtime-visualization contract. `docs/07-data-model-and-observability.md` is the authoritative runtime entity/event/timing contract.

## 7. Change control

Material changes to state ownership, goal/acceptance versioning, evidence gates, repair bounds, memory provenance, provider independence, security/Git gates, event/timing semantics, UI truthfulness, or chain-of-thought/privacy policy require an explicit ADR/design amendment before implementation. Ordinary implementation details can evolve within these constraints.


---

<!-- SOURCE: docs/00-product-design.md -->

# Orqalis Product Design

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Product vision

Orqalis is a durable engineering orchestration system for software projects. It provides a shared project brain and a governed execution engine around AI coding assistants. It keeps project-specific knowledge across tasks, converts user requests into explicit goals and acceptance criteria, decomposes work into a dependency graph, selects specialist agents and skills, coordinates execution, validates evidence, performs bounded repair loops, updates documentation, and completes controlled Git delivery.

The primary value proposition is continuity and reliability. A project should not be re-discovered from scratch every time the user changes assistants or starts a new task. Codex, Claude Code, GitHub Copilot, future MCP-compatible assistants, and Orqalis-native agents should all be able to operate against the same project identity, architecture knowledge, decisions, task history, constraints, and current workflow state.

## 2. Product positioning

Orqalis should be positioned as an orchestration and project-intelligence layer rather than a replacement IDE or coding model.

- Coding assistants remain excellent interactive workers.
- Orqalis owns durable state, project memory, task lifecycle, policy, evidence, and delivery governance.
- MCP provides the standard assistant-facing interface.
- CLI provides a universal developer and CI interface.
- REST/WebSocket APIs provide automation and future UI integration.
- Provider adapters let Orqalis invoke external coding agents when Orqalis itself is running the workflow.

## 3. Core principles

### 3.1 Goal before implementation
Every run starts by converting the user request into a measurable goal, explicit acceptance criteria, constraints, and a definition of done.

### 3.2 Memory before rediscovery
Agents retrieve current project memory first. Repository analysis is incremental and targeted to gaps, changed files, or low-confidence knowledge.

### 3.3 Deterministic orchestration around agentic reasoning
LLMs reason, plan, code, diagnose, review, and document. Deterministic software controls state transitions, permissions, task dependencies, iteration limits, Git operations, locks, test command execution, and audit records.

### 3.4 Evidence over assertion
A criterion cannot pass merely because an agent claims success. Passing requires evidence such as command output, exit codes, tests, static analysis, changed files, screenshots where relevant, or structured reviewer findings.

### 3.5 Specialized agents, dynamic skills
Agents represent roles. Skills represent reusable capabilities loaded for a task. Tools are executable actions. These are modeled separately.

### 3.6 Provider independence
The architecture must not bind Orqalis to one model vendor. Providers are adapters selected by capability, policy, availability, cost, and later empirical quality metrics.

### 3.7 Least privilege
Developer agents may modify a workspace but cannot directly push. Reviewer agents are read-only. Git delivery occurs only after acceptance gates pass.

### 3.8 Git-aware truth
Permanent memory is versioned against Git commit SHAs and can be invalidated incrementally when code changes.

### 3.9 Observable execution
The Orchestrator, sub-agents, phases, tasks, acceptance checks, repair loops, tools, tests, memory operations, and delivery gates are observable runtime entities. Status and timers come from persisted Orqalis events/state, never simulated browser progress. Visibility must use structured activity summaries and evidence, never private model chain-of-thought.

## 4. Primary personas

- Individual developer: wants reliable task completion without repeatedly explaining the repository.
- Tech lead: wants architecture decisions, acceptance criteria, change scope, and review evidence preserved.
- Team: wants different assistants to share project context and operating conventions.
- Platform engineer: wants headless automation in CI and policy-controlled agent execution.
- AI engineering team: wants to benchmark providers and skills while retaining a stable orchestration layer.

## 5. Key user journeys

### 5.1 Initialize a project
`orqalis init` detects the repository, stack, build system, tests, documentation, modules, instructions, and current Git commit. It creates the first project-memory snapshot and minimal local configuration.

### 5.2 Run an end-to-end task
`orqalis run "Implement offline sync" --branch feature/offline-sync` creates the goal and criteria, retrieves context, builds a plan, delegates work, validates results, repairs failures if needed, updates docs, commits, pushes, and promotes durable knowledge to project memory.

### 5.3 Use from Codex/Claude/Copilot
The assistant calls Orqalis MCP tools such as `get_project_context`, `start_task`, `get_next_work`, `report_result`, `review_run`, and `finalize_run`. The same project memory is used regardless of assistant.

### 5.4 Switch assistants mid-task
A task begun with Claude can continue in Codex because the run state, goal, acceptance criteria, decisions, artifacts, and task graph are stored by Orqalis rather than in a model-specific conversation.

### 5.5 Inspect project context without executing
`orqalis context "tablet navigation"` returns the relevant architecture, files, decisions, previous tasks, known issues, and confidence/provenance without creating a run.

### 5.6 Observe a live run
`orqalis run "Implement offline sync" --open` starts or reuses the local Control Center and opens the run in the browser. The user can see the Orchestrator, every active sub-agent, current task, dependencies, elapsed/active/waiting/blocked time, acceptance evidence, repair loops, tools/tests, project-memory activity, Git state, and final delivery without reading raw logs.

### 5.7 Run headlessly
CI or automation can use `orqalis run --no-ui --json` (or equivalent configuration) against the same Orqalis Core. UI availability never changes workflow semantics.

## 6. Non-goals for V1

- Building a full IDE.
- Fully autonomous production deployment.
- Unlimited self-repair loops.
- Arbitrary remote shell execution without sandboxing.
- Replacing source control review or protected-branch policy.
- Automatically trusting model-generated memory without provenance and validation.


---

<!-- SOURCE: docs/01-system-architecture.md -->

# Orqalis System Architecture

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Logical architecture

```text
Human / Coding Assistant / CI / Local Web UI
                    |
      +-------------+-------------+
      |             |             |
     CLI           MCP        REST/WS API
      |             |             |
      +-------------+-------------+
                    |
             Orqalis Core
                    |
    +---------------+----------------+
    |               |                |
Workflow Engine  Context Engine   Policy Engine
    |               |                |
    |          Project Memory         |
    |          Knowledge Graph        |
    |          Semantic Index         |
    |               |                |
    +------- Agent Runtime -----------+
                    |
        +-----------+-----------+
        |           |           |
      Codex       Claude      Other/Local
        |           |           |
        +-----------+-----------+
                    |
           Isolated Workspace
                    |
       Tests / Build / Git / Docs
```

## 2. Major subsystems

### 2.1 Interface layer
Provides CLI, MCP server, HTTP/WebSocket API, and the packaged Local Control Center. Interfaces are thin projections/command adapters; business logic and canonical state belong in the core.

### 2.2 Workflow engine
Owns the finite-state lifecycle, durable checkpoints, orchestration decisions, and authoritative progress. It must support dependency-aware scheduling, controlled parallel-ready tasks, retries, bounded repair loops, cancellation, resume, human-review states, idempotent transitions, and event emission.

Recommended implementation: Python with a durable graph/state-machine abstraction. LangGraph is a reasonable implementation candidate, but Orqalis domain objects should remain framework-independent.

### 2.3 Context engine
Builds compact task-specific context packs using structured memory, semantic retrieval, Git history, repository metadata, and dependency relationships. It determines whether memory is sufficient or targeted repository inspection is required.

### 2.4 Project memory service
Stores canonical project knowledge, architecture entities, conventions, decisions, previous runs, known issues, file roles, provenance, confidence, embeddings, and memory-version metadata tied to source commits.

### 2.5 Agent runtime
Executes role-specific agents with restricted tools and skills. It passes typed task contracts rather than unstructured chat transcripts.

### 2.6 Skill registry
Stores reusable skills with metadata describing capability, applicability, required tools, expected outputs, constraints, and optional prompt/instruction content.

### 2.7 Provider adapter layer
Normalizes external model/agent providers behind one interface. Provider choice must not leak into orchestration logic.

### 2.8 Workspace manager
Creates isolated Git worktrees or equivalent workspaces per run. It manages locks, branch verification, base commit, cleanup, and artifact paths.

### 2.9 Evaluation service
Maps acceptance criteria to evidence, runs deterministic validators, collects reviewer findings, computes pass/fail state, and generates targeted repair scopes.

### 2.10 GitOps service
Performs safe Git status checks, diff collection, staging, commit generation, push, and later PR creation. It enforces policies before destructive or remote operations.

### 2.11 Documentation service
Uses final accepted diff and decisions to update relevant docs, ADRs, changelog, and project instructions without rewriting unrelated documentation.

### 2.12 Observability service
Captures durable structured events, traces, agent/task/phase timers, prompt/template versions, provider usage, reliable cost, latency, task outcomes, repairs, tests, Git activity, memory activity, and acceptance evidence. It is the telemetry source for the Local Control Center.

### 2.13 Local Control Center
A browser UI served locally by Orqalis. It visualizes the orchestrator as a first-class runtime entity, sub-agents, current tasks, dependency DAG, parallel execution, phases, elapsed/active/waiting time, utilization, acceptance evidence, repair loops, tools/tests, Git delivery, and Project Brain state. It never owns canonical workflow state. See `10-local-control-center.md`.

### 2.14 Durable event/projection model
Workflow components emit typed events to a durable stream. UI clients load a run snapshot and subscribe via WebSocket/SSE from an event sequence/cursor, supporting reconnect, historical replay, and reliable timing metrics.

## 3. Runtime deployment modes

### Local developer mode
- Orqalis daemon/process runs on developer machine.
- SQLite may be permitted only for a prototype, but PostgreSQL is preferred quickly.
- Local Git worktrees and Docker sandbox.
- MCP transport can be stdio initially for IDE/CLI-local integration.

### Team/server mode
- Orqalis API/MCP server hosted centrally.
- PostgreSQL + pgvector.
- Redis optional for queueing/cache/locks.
- Remote runners or container workers execute tasks.
- Authentication, tenancy, audit, and secrets management enabled.

### CI mode
- Non-interactive CLI invokes the same core.
- Run state persists remotely or in an ephemeral DB depending on environment.
- Output includes machine-readable JSON and exit status.

## 4. Recommended technology stack

- Python 3.12+ for core, services, CLI, and providers.
- Pydantic v2 for typed contracts and validation.
- FastAPI for REST/WebSocket interface and local UI host.
- Typer for CLI.
- React + TypeScript + Vite for the packaged Local Control Center.
- React Flow for task/agent DAG visualization; Recharts for metrics; Monaco for diff/config views when needed.
- PostgreSQL for durable state.
- pgvector for semantic retrieval.
- SQLAlchemy 2.x + Alembic for persistence/migrations.
- Git CLI via controlled subprocess wrapper; avoid custom Git implementation.
- Docker/OCI containers for isolated execution.
- OpenTelemetry for traces/metrics/log correlation.
- pytest for tests.
- Optional Redis for distributed locks, queues, and transient cache.

## 5. Repository structure

```text
orqalis/
  pyproject.toml
  README.md
  src/orqalis/
    cli/
    api/
    mcp/
    core/
      orchestrator.py
      state_machine.py
      scheduler.py
      events.py
    domain/
      project.py
      run.py
      task.py
      acceptance.py
      agent.py
      skill.py
      memory.py
      artifact.py
    agents/
      requirements.py
      planner.py
      architect.py
      developer.py
      tester.py
      reviewer.py
      change_guardian.py
      documentation.py
      gitops.py
      memory_curator.py
    skills/
      registry.py
      loader.py
    providers/
      base.py
      openai.py
      anthropic.py
      external_cli.py
      local.py
    memory/
      service.py
      retrieval.py
      indexing.py
      invalidation.py
      graph.py
      embeddings.py
    workspace/
      manager.py
      worktree.py
      sandbox.py
    evaluation/
      evaluator.py
      evidence.py
      validators.py
      repair.py
    git/
      service.py
      policies.py
    docs/
      updater.py
      adr.py
    persistence/
      models.py
      repositories/
      migrations/
    observability/
      events.py
      projections.py
      timing.py
      tracing.py
      metrics.py
      logging.py
    security/
      permissions.py
      secrets.py
      policy.py
    config/
      settings.py
  web/
    src/
      pages/
      components/
      features/
      api/
  tests/
    unit/
    integration/
    e2e/
  docs/
```

## 6. Architectural boundaries

The domain layer must not import vendor SDKs, FastAPI, React, CLI libraries, or MCP libraries. Provider-specific code belongs under `providers/`. Interface layers translate external requests into domain commands. Persistence is accessed through repositories/interfaces. The Local Control Center consumes snapshots/projections/events and cannot mutate state except through the same command/policy APIs used by CLI/MCP. This keeps Orqalis testable and prevents an early framework or UI decision from becoming the product architecture.


---

<!-- SOURCE: docs/02-agent-and-skill-model.md -->

# Agent and Skill Model

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Core distinction

- Agent = role with responsibilities, authority, policies, and output contract.
- Skill = reusable task capability that can be dynamically loaded.
- Tool = executable action such as file read, shell command, test runner, Git diff, or memory query.
- Provider = execution backend such as Codex/OpenAI, Claude/Anthropic, local model, or external coding CLI.

These concepts must remain independent.

## 2. Initial agent catalog

### Requirements Agent
Transforms user intent into a goal, scope, constraints, acceptance criteria, and definition of done. It may identify ambiguities but V1 should prefer safe assumptions when the task is actionable.

### Architect Agent
Evaluates architecture impact, cross-module boundaries, compatibility constraints, and whether an ADR is required.

### Planner Agent
Produces a dependency DAG of typed tasks with expected artifacts, agent capability requirements, validation strategy, and estimated risk.

### Developer Agent
Implements code changes in the isolated workspace. It cannot approve its own work or push to Git.

### Test Agent
Adds/runs unit, integration, UI, static, build, or other deterministic validation as appropriate.

### Reviewer Agent
Evaluates implementation against acceptance criteria using evidence. Read-only by default.

### Change Guardian
Detects out-of-scope or suspicious changes and flags unrelated modifications, accidental deletions, generated files, secrets, or architecture drift.

### Root Cause/Repair Agent
Given failed criteria and evidence, proposes the smallest repair plan. It should not restart the full run unless the plan is invalidated broadly.

### Documentation Agent
Updates docs based on accepted implementation and actual diff.

### GitOps Agent/Service
Prepares a detailed commit message and performs commit/push after all gates pass. Prefer deterministic Git service with an agent generating commit text, rather than allowing an unconstrained Git agent.

### Memory Curator
Promotes durable knowledge from a successful run into project memory with provenance and confidence. It rejects transient implementation chatter.

## 3. Skill schema

Example metadata:

```yaml
id: android-compose
version: 1.0.0
description: Android development with Kotlin and Jetpack Compose
capabilities:
  - kotlin
  - compose
  - material3
  - responsive-layout
applicable_when:
  any:
    - android
    - kotlin
    - jetpack-compose
required_tools:
  - filesystem.read
  - filesystem.write
  - shell.run
  - test.run
constraints:
  - follow repository conventions
outputs:
  - code_changes
  - validation_evidence
```

Skills may include instructions, examples, validation recipes, tool declarations, compatibility constraints, and version metadata.

## 4. Dynamic routing

The Capability Router should operate in two stages:

1. Determine required capabilities from a task.
2. Match capabilities to agent role + skill set + allowed provider.

Selection factors:
- Capability fit.
- Repository/project policy.
- Provider availability.
- Cost/latency limits.
- Security restrictions.
- Historical quality score (later phase).
- Context-window requirements.

## 5. Typed inter-agent messages

Agents should coordinate through structured records rather than unrestricted free-form conversations.

```json
{
  "run_id": "ORQ-2026-001",
  "task_id": "T4",
  "from_role": "architect",
  "to_role": "developer",
  "type": "decision",
  "summary": "Keep sync orchestration centralized in SyncCoordinator.",
  "artifact_refs": ["ADR-014"],
  "requires_ack": true
}
```

Shared findings belong in run state/artifacts, not private conversation histories.

## 6. Provider abstraction

```python
class AgentProvider(Protocol):
    async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult: ...
```

`ProviderExecutionRequest` should contain role, task contract, context pack, selected skills, allowed tools, constraints, output schema, timeout/budget, and trace identifiers.

Provider adapters must normalize:
- Model/agent invocation.
- Tool-call representation.
- Structured outputs.
- Usage/cost metadata where available.
- Cancellation/timeouts.
- Provider errors.

## 7. Provider independence rule

No workflow node should contain logic such as `if provider == "openai"`. Provider-specific behavior is isolated behind adapters and capability metadata.

## 8. Runtime actor and observability contract

The Orchestrator and each sub-agent are visible runtime actors. The deterministic Orchestrator is the workflow owner; sub-agents are worker sessions created for roles/tasks. Each active actor must have a stable runtime/session ID and emit structured status transitions.

Canonical agent statuses: `STARTING`, `WORKING`, `WAITING_FOR_DEPENDENCY`, `IDLE`, `BLOCKED`, `FAILED`, `COMPLETE`, `CANCELLED`. Task statuses are defined in the workflow/data-model documents.

Every sub-agent session records, where available: role, provider/model, assigned task, loaded skills, allowed tools, start/end timestamps, working/waiting/blocked time, task attempts/outcomes, tool/test/LLM invocation counts, token usage, reliable provider cost, and artifact/evidence references.

Agents may emit concise structured `activity_summary`, `decision`, `finding`, `blocker`, and `result` records for coordination and UI display. These must describe observable work or conclusions and must never contain hidden chain-of-thought, scratch reasoning, secrets, or unredacted sensitive tool arguments.

## 9. Orchestrator visibility

The Orchestrator appears in Mission Control as a first-class actor showing current lifecycle state/UI phase, execution wave, ready/running/blocked/completed task counts, active parallel branches, repair iteration, policy/approval gates, elapsed/active/waiting time, and structured next-transition reason. It does not pretend to be another coding model; provider-backed reasoning used by Requirements/Planner/Repair agents remains represented as those agent sessions.


---

<!-- SOURCE: docs/03-project-memory.md -->

# Project Memory Design

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Objective

Project Memory allows Orqalis and connected coding assistants to retain reliable repository-specific context across tasks without full repository re-analysis. Memory supplements the repository; it never replaces source-of-truth verification.

## 2. Memory scopes

### Global memory
Reusable engineering knowledge, skill definitions, organization policies, generic patterns, and tool instructions.

### Project memory
Repository-specific architecture, modules, file roles, business/domain rules, conventions, decisions, CI/build/test rules, known issues, previous tasks, and high-value implementation facts.

### Run memory
Goal, acceptance criteria, plan, current task state, findings, artifacts, test results, reviewer comments, repair attempts, decisions, and temporary coordination for a single run.

After successful completion, selected run knowledge is promoted to project memory by the Memory Curator.

## 3. Memory categories

- Project identity and purpose.
- Technology stack and versions where stable.
- Architecture and module boundaries.
- Repository map and important file roles.
- Data flows and API contracts.
- Domain entities and business rules.
- Coding/testing conventions.
- CI/CD and Git policies.
- Architecture Decision Records.
- Previous accepted changes.
- Known issues, technical debt, flaky tests, and limitations.
- Relationships/dependencies among files, modules, services, and concepts.

## 4. Provenance model

Every durable fact should include:

```json
{
  "fact": "Room is the primary local persistence layer.",
  "memory_type": "architecture",
  "confidence": 0.98,
  "source_paths": ["data/database/AppDatabase.kt", "docs/architecture.md"],
  "source_commit": "91abc22",
  "introduced_by_run": "ORQ-2026-0202",
  "last_verified_at": "2026-09-10T10:00:00Z",
  "status": "active"
}
```

Memory must support superseding rather than destructive rewriting so history is auditable.

## 5. Git-aware freshness

Each project-memory snapshot records `indexed_commit_sha`. At run start:

1. Read current HEAD/base commit.
2. Compare to indexed commit.
3. If equal, memory is considered structurally current.
4. If different, calculate changed paths and commit range.
5. Determine impacted memory entries and graph neighborhoods.
6. Invalidate or mark stale only affected knowledge.
7. Re-index changed areas.
8. Update snapshot metadata.

This turns repository refresh into an incremental process.

## 6. Dependency-aware invalidation

Memory should model relationships such as:

```text
Theme.kt -> defines -> AppTheme
AppTheme -> used_by -> HomeScreen
AppTheme -> used_by -> EditorScreen
NotesRepository -> backed_by -> Room
NotesRepository -> syncs_through -> SyncCoordinator
```

If a foundational file changes, Orqalis invalidates related facts and summaries rather than the whole project.

## 7. Context Pack

Agents should normally receive a Context Pack, not raw memory search results.

```yaml
context_pack:
  project: Novra Android
  task: Add tablet split-pane editor
  architecture:
    - MVVM
    - responsive layout uses WindowSizeClass
  relevant_files:
    - EditorScreen.kt
    - EditorViewModel.kt
    - ResponsiveScaffold.kt
  conventions:
    - UI state is immutable
  decisions:
    - ADR-008
  related_runs:
    - ORQ-0113
  known_issues:
    - ISSUE-42
  confidence: 0.94
  freshness:
    indexed_commit: abc123
    current_commit: abc123
```

## 8. Retrieval pipeline

1. Parse current task into concepts/capabilities.
2. Retrieve structured facts by project/type.
3. Semantic search over memory text/embeddings.
4. Traverse relevant knowledge-graph relations.
5. Include related prior runs and ADRs.
6. Rank file candidates.
7. Apply token/size budget.
8. Return provenance and confidence.
9. If confidence is below threshold or memory is stale, request targeted repository inspection.

## 9. Bootstrap

`orqalis init` performs the only intentionally broad analysis:

- Detect languages/frameworks/build files.
- Read repository instructions and documentation.
- Identify entry points and module boundaries.
- Detect tests, lint, build, format commands.
- Map high-value files and dependencies.
- Identify Git conventions/protected-branch assumptions where available.
- Generate architecture summary and initial facts.
- Build embeddings and initial graph.
- Store current commit as memory baseline.

## 10. Memory storage

V1 recommendation: PostgreSQL + pgvector. Core relational entities should remain queryable without vector search. Embeddings augment, not replace, structured retrieval.

Core tables: projects, project_memory, memory_sources, memory_versions, repository_files, architecture_entities, architecture_relations, decisions, runs, run_findings, known_issues, embeddings.

## 11. Memory safety rules

- Never store secrets, tokens, passwords, or raw credential files.
- Redact likely secrets before persistence.
- Do not promote transient chain-of-thought or model scratch reasoning.
- Do not trust a single agent assertion as high-confidence architecture truth.
- Prefer source-backed facts.
- Mark inferred facts explicitly.
- Tie accepted changes to commit SHAs.

## 12. Project Brain observability

Project Memory is exposed in the Local Control Center as the **Project Brain**. The UI may show memory categories, indexed commit, freshness, relevant architecture entities/relations, ADRs, known issues, related runs, Context Pack composition, and source provenance.

Memory retrieval and curation emit privacy-safe structured events including query/task reference, selected memory IDs/types, source/commit freshness, count/size, invalidations, and promotions. Do not log full secrets, raw hidden prompts, or private chain-of-thought.

## 13. Memory performance metrics

Track memory hit rate, context-pack size, percentage of repository re-analyzed, changed-file refresh scope, stale-memory invalidations, retrieval latency, and post-run promotions. These metrics help verify the core product claim that Orqalis reduces repeated repository analysis over time.


---

<!-- SOURCE: docs/04-workflow-and-acceptance.md -->

# Workflow, Acceptance, and Convergence

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Run lifecycle

```text
RECEIVED
  -> CONTEXT_SYNC
  -> ANALYZING
  -> GOAL_DEFINED
  -> PLANNED
  -> EXECUTING
  -> INTEGRATING
  -> TESTING
  -> REVIEWING
      -> REPAIR_PLANNING -> EXECUTING (bounded loop)
      -> CHANGE_GUARD
  -> DOCUMENTING
  -> DELIVERY_VALIDATION
  -> COMMITTING
  -> PUSHING
  -> MEMORY_FINALIZATION
  -> COMPLETED
```

Additional terminal/intermediate states:
- BLOCKED
- HUMAN_REVIEW_REQUIRED
- FAILED
- CANCELLED
- PAUSED


## 1.1 UI phase projection

The detailed state machine remains canonical. Mission Control projects it into stable user-facing phases:

```text
CONTEXT -> GOAL -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> REPAIR -> DOCS -> DELIVER
```

`REPAIR` appears only while a repair loop is active. `DELIVER` covers final validation, commit, optional push, and memory finalization. The UI phase is a projection; it does not replace detailed workflow states.

## 1.2 Runtime status and progress semantics

Canonical task statuses: `PENDING`, `READY`, `RUNNING`, `WAITING`, `BLOCKED`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `SKIPPED`. Attempt state is recorded separately so repair attempts remain visible.

Overall progress must be derived from persisted task/phase state. V1 should use deterministic plan weights/work units (default equal task weights unless the Planner supplies validated weights) and explicit phase gates. A displayed percentage means plan completion, not an ETA or probability of success. If repair adds work, the plan version/denominator is updated and the UI explains the revision rather than faking monotonic progress.

Wall, active, waiting, and blocked durations are derived from timestamps/status events. LLM/tool/test durations are breakdowns that may overlap with actor working time and must not be naively summed into wall time.

## 2. Goal contract

A goal must include:
- User intent.
- In-scope behavior.
- Explicit out-of-scope behavior when material.
- Constraints.
- Risks/assumptions.
- Acceptance criteria.
- Definition of done.
- Goal version.

Once implementation begins, the goal cannot be silently changed. Material scope changes create a new goal version and are audited.

## 3. Acceptance criterion schema

```json
{
  "id": "AC-003",
  "description": "Application build succeeds.",
  "priority": "required",
  "validator": "command",
  "validation_spec": {
    "command": "./gradlew build",
    "expected_exit_code": 0
  },
  "status": "pending",
  "evidence_refs": []
}
```

Validator types should include command, test-suite, static-analysis, file/diff assertion, structured agent review, manual/human evidence, and later visual/browser validation.

## 4. Planning contract

A task contains:
- ID and parent goal.
- Description and expected outcome.
- Dependencies.
- Required capabilities.
- Suggested role/provider constraints.
- Relevant context references.
- Allowed tool classes.
- Files/modules likely involved.
- Expected artifacts.
- Validation method.
- Risk score.
- Status and attempts.

The planner produces a DAG. Scheduler executes only dependency-ready tasks. Independent tasks may run concurrently when workspace conflict risk is acceptable.

## 5. Integration model

Parallel agents should not blindly write into the same working tree. V1 may serialize write tasks while allowing read/review tasks concurrently. Later phases can use per-task worktrees/patches and an Integrator to merge results.

## 6. Review contract

Reviewer output must be structured:

```json
{
  "overall": "FAIL",
  "criteria": [
    {
      "id": "AC-001",
      "status": "PASS",
      "evidence_refs": ["ev-10"]
    },
    {
      "id": "AC-002",
      "status": "FAIL",
      "reason": "Hard-coded color remains in SettingsScreen.kt:143",
      "evidence_refs": ["ev-11"]
    }
  ],
  "blocking_findings": ["AC-002"],
  "non_blocking_findings": []
}
```

## 7. Repair loop

On failure:

1. Identify only failed criteria and blocking findings.
2. Determine root cause and affected dependency area.
3. Create targeted repair tasks.
4. Re-run affected validations plus required regression checks.
5. Review again.
6. Increment repair iteration.
7. Escalate after configured maximum (default proposal: 5).

The original goal remains stable unless the system enters explicit goal-revision flow.

## 8. Change Guardian gate

After criteria pass, compare actual diff with planned scope. Flag:
- unrelated modules/files;
- deletion spikes;
- lockfile/dependency changes not justified by task;
- generated/binary files;
- secret-like content;
- build/CI/security policy modifications;
- architecture boundary violations;
- test removal/reduction.

A blocking unexpected change returns the run to repair/review.

## 9. Documentation and delivery gates

Documentation runs only after functional acceptance. Before Git delivery, Orqalis re-runs configured final validations on the complete final tree and confirms clean policy state.

## 10. Idempotency and resume

Every state transition and external side effect should have an idempotency key. A process restart must resume from persisted state without duplicating commits, re-running successful non-repeatable actions, or losing evidence.

## 11. Runtime event requirements

Every consequential lifecycle transition must emit a durable event after/with the state transaction. Events use a monotonic per-run sequence for replay. UI reconnect loads a snapshot and resumes from the last sequence. Event payloads contain typed IDs, statuses, timestamps, evidence/artifact references, and concise structured summaries; they never contain private chain-of-thought or secrets.


---

<!-- SOURCE: docs/05-interfaces-and-integrations.md -->

# Interfaces and Coding-Assistant Integrations

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Interface strategy

Orqalis exposes one core through three primary interfaces:

- CLI for developers and CI.
- MCP server for coding assistants.
- REST/WebSocket API for automation, dashboards, and future IDE extensions.

The core must not depend on any interface.

## 2. CLI design

Initial command surface:

```text
orqalis init
orqalis status
orqalis doctor
orqalis context <task>
orqalis run <request>
orqalis runs
orqalis run show <run-id>
orqalis run resume <run-id>
orqalis run cancel <run-id>
orqalis memory status
orqalis memory search <query>
orqalis memory refresh
orqalis agents
orqalis skills
orqalis config show
orqalis ui
orqalis ui --open
orqalis serve
```

Important flags:
- `--repo`
- `--branch`
- `--provider`
- `--non-interactive`
- `--json`
- `--max-repair-loops`
- `--no-push`
- `--require-human-approval`

CLI output should have human-readable default and deterministic JSON mode for CI.

## 3. MCP design

MCP is the primary seamless integration mechanism for Codex, Claude, Copilot, Cursor-like clients, and future assistants.

Keep the MCP tool surface compact and high value.

### Project/context tools
- `get_project`
- `get_project_context(task, depth)`
- `search_project_memory(query, types, limit)`
- `get_architecture(area)`
- `get_decisions(topic)`
- `get_related_files(task)`

### Workflow tools
- `start_task(request, options)`
- `get_run(run_id)`
- `get_goal(run_id)`
- `get_plan(run_id)`
- `get_next_work(run_id, worker_capabilities)`
- `report_result(run_id, task_id, result)`
- `report_finding(run_id, finding)`
- `review_run(run_id)`
- `finalize_run(run_id)`

### Capability tools
- `list_agents()`
- `list_skills(query)`
- `get_skill(skill_id)`

Avoid exposing raw database methods through MCP.

## 4. MCP resource model

In addition to tools, expose read-only resources where useful:
- project summary;
- active run summary;
- architecture index;
- ADR list;
- known issues;
- project conventions.

## 5. Codex integration

Codex acts either as:

### Assistant-driven mode
The user is already in Codex. Codex calls Orqalis via MCP for context, workflow, acceptance criteria, and reporting. Orqalis does not need to replace the Codex interface.

### Orqalis-driven mode
Orqalis invokes an OpenAI provider adapter to execute a delegated task. The adapter receives the same typed task and context contract used by other providers.

## 6. Claude Code integration

Use the same MCP surface in assistant-driven mode. For Orqalis-driven execution, the Anthropic provider adapter converts the generic agent request to Claude-compatible invocation and tool policy.

## 7. GitHub Copilot integration

Copilot clients that support MCP can attach Orqalis as a local or remote server. Repository instructions should direct the assistant to request Orqalis context before significant work.

## 8. Native repository instruction files

Orqalis may generate or update lightweight integration files:
- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`

These files must not duplicate full project memory. They should state project-specific guardrails and instruct compatible assistants to retrieve Orqalis context.

## 9. Suggested MCP usage flow

```text
Assistant receives user task
 -> get_project_context(task)
 -> start_task(request)
 -> get_goal(run_id)
 -> get_next_work(...)
 -> implement using assistant-native file/code tools
 -> report_result(...)
 -> review_run(...)
 -> repair if assigned
 -> finalize_run(...)
```

## 10. REST API

Initial endpoints may mirror domain use cases:
- `POST /projects/init`
- `GET /projects/{id}`
- `POST /projects/{id}/context`
- `POST /runs`
- `GET /runs/{id}`
- `POST /runs/{id}/cancel`
- `POST /runs/{id}/resume`
- `GET /runs/{id}/events`
- `GET /projects/{id}/memory`
- `GET /runs/{id}/agents`
- `GET /runs/{id}/tasks`
- `GET /runs/{id}/timeline`
- `GET /runs/{id}/metrics`
- `GET /runs/{id}/acceptance`
- `GET /runs/{id}/events?after=<sequence>`
- `WS /ws/runs/{id}`

Use WebSocket/SSE for event streaming rather than polling. The Local Control Center loads an authoritative snapshot/projection through REST, then subscribes from a per-run event sequence/cursor. `orqalis run --open` starts/reuses the local UI host and launches the run URL; `orqalis ui` opens/reuses the project dashboard; `orqalis serve` explicitly hosts API/MCP/UI services. Headless mode remains fully supported.

## 11. Integration design rule

Assistant integrations are clients of Orqalis, not owners of Orqalis state. A user can switch assistants without losing the project/run context.

## 12. Local Control Center integration contract

Default local URL: `http://127.0.0.1:7842` (configurable). Bind loopback by default. The frontend is a packaged client of REST/WebSocket projections and must not directly query persistence or execute Git/tool commands.

Recommended run flow: `GET /runs/{id}` for snapshot, then subscribe to `WS /ws/runs/{id}?after=<sequence>` (or SSE equivalent). On disconnect, reload/reconcile the snapshot and resume after the last durable sequence. All UI commands (cancel, pause, approve, resume, open artifact) invoke normal command endpoints and Policy Engine checks.

The same project/run can be observed while work is driven from CLI, Codex, Claude Code, Copilot, MCP, or Orqalis-native providers.


---

<!-- SOURCE: docs/06-security-git-and-governance.md -->

# Security, Git, and Governance

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Threat model

Orqalis executes model-generated actions against source code, local tools, and potentially remote Git. Treat every agent output as untrusted until validated against tool schemas, policies, workspace boundaries, and acceptance gates.

## 2. Permission model

Define permissions by role and tool class.

Example:

```text
Developer
  read repo: yes
  write workspace: yes
  run approved commands: yes
  read memory: yes
  mutate canonical memory: no
  commit: no
  push: no

Reviewer
  read repo: yes
  write code: no
  run tests: yes
  read memory: yes
  commit/push: no

Git delivery service
  stage/commit: yes after gates
  push: yes after gates
  force push: denied by default
```

## 3. Sandbox

Commands run with:
- workspace-scoped filesystem mounts;
- resource/time limits;
- network policy;
- environment-variable allowlist;
- no host secrets exposure;
- command audit logs.

V1 may implement Docker-based sandboxing with configurable fallback for trusted local development.

## 4. Command policy

Classify commands:
- read-only/safe;
- build/test;
- workspace-mutating;
- networked;
- destructive;
- privileged.

Deny or require human approval for destructive/privileged classes. Explicitly block unsafe defaults such as force push, deleting parent directories, rewriting protected branch history, and unscoped credential access.

## 5. Git workflow

At run start:
1. Confirm repository root.
2. Record base commit.
3. Fetch if policy allows/requests.
4. Confirm target branch.
5. Create isolated worktree.
6. Record initial status.

Before commit:
1. Confirm reviewer PASS.
2. Confirm Change Guardian PASS.
3. Confirm final validation PASS.
4. Check secrets and forbidden files.
5. Inspect full diff.
6. Ensure target branch remains valid.
7. Generate documentation updates.
8. Stage explicit files.
9. Generate commit message from goal/diff/evidence.
10. Commit.
11. Push only if configured.

## 6. Commit message format

Recommended:

```text
feat(sync): add offline note synchronization

Implement background synchronization and conflict handling for offline note edits.

Changes:
- add SyncCoordinator and persistence queue
- integrate WorkManager scheduling
- add conflict-resolution tests
- update architecture documentation

Validation:
- build passed
- unit tests passed
- sync integration tests passed

Acceptance:
- AC-001 PASS
- AC-002 PASS
- AC-003 PASS

Orqalis-Run: ORQ-2026-0202
```

## 7. Protected operations

Default deny:
- force push;
- branch deletion;
- `git reset --hard` against user work;
- cleaning untracked user files;
- pushing directly to protected branches;
- secret/credential commits;
- disabling security tests to make acceptance pass.

## 8. Secrets

Secrets belong in OS keychain, environment injection, vault integration, or CI secret stores. Never persist them in project memory, run artifacts, prompts, traces, or docs. Add redaction to logs and memory ingestion.

## 9. Audit

Persist who/what caused each consequential transition:
- user request;
- selected provider/model;
- task assignment;
- tool execution;
- file-change summary;
- reviewer decision;
- repair reason;
- commit/push event;
- memory promotion.

## 10. Human-in-the-loop policy

Support configurable approval gates for:
- architecture-changing tasks;
- dependency upgrades;
- migrations;
- network access;
- pushes;
- protected files;
- max cost/time thresholds;
- repeated repair failures.

## 11. Control Center and telemetry security

The local UI binds to loopback by default. Any non-loopback/remote binding requires explicit configuration, authentication, authorization, CSRF/origin protections appropriate to the transport, and the same project/role policies used by CLI/MCP.

Telemetry/event payloads are security boundaries. Redact or omit credentials, auth headers, environment secrets, sensitive command arguments, provider raw responses that may contain secrets, and private model chain-of-thought. Developer mode may reveal additional structured diagnostics only after the same redaction pipeline.

Browser controls never bypass policy. Pause/cancel/resume/approval/delivery operations are normal Orqalis commands recorded in the audit log. UI display data must be sourced from persisted projections/events so browser refresh cannot invent or alter workflow history.


---

<!-- SOURCE: docs/07-data-model-and-observability.md -->

# Data Model and Observability

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file replaces earlier duplicate `Event`/`RunEvent` and `AgentExecution`/`AgentSession` terminology.

## 1. Modeling rules

- Definitions and executions are separate: `Task` is planned work; `TaskExecution` is an attempt. Agent roles/definitions are configuration; `ActorSession` is runtime activity.
- `Event` is the one canonical append-only runtime event record. There is no separate `RunEvent` entity.
- The Orchestrator and sub-agents are runtime actors. `ActorSession.actor_type` is `ORCHESTRATOR` or `AGENT`.
- Durable workflow tables are canonical state; event/projector tables support audit, replay, telemetry, and UI projections.
- Every mutable/side-effecting record has IDs, timestamps, run/project linkage, and idempotency/audit metadata where relevant.

## 2. Core project and memory entities

### Project
`id, name, repo_uri, repo_root, default_branch, settings, created_at, updated_at`

### ProjectSnapshot
`id, project_id, indexed_commit_sha, created_at, status, repo_fingerprint`

### RepositoryFile
`id, project_id, path, language, role, content_hash, last_seen_commit, metadata`

### MemoryItem
`id, project_id, type, title, content, structured_data, confidence, status, source_commit, introduced_by_run, last_verified_at, superseded_by`

### MemorySource
`id, memory_item_id, source_type, source_ref, content_hash, commit_sha`

### ArchitectureEntity
`id, project_id, entity_type, name, source_refs, metadata`

### ArchitectureRelation
`id, project_id, source_entity_id, relation_type, target_entity_id, confidence, source_refs`

### Decision
`id, project_id, adr_key, title, status, decision, rationale, source_commit, introduced_by_run`

## 3. Run, goal, planning, and evidence entities

### Run
`id, project_id, request, target_branch, base_commit, current_goal_version_id, state, ui_phase, repair_iteration, max_repair_iterations, created_at, started_at, completed_at, last_event_sequence, settings_snapshot`

### GoalVersion
`id, run_id, version, goal, scope, out_of_scope, constraints, assumptions, definition_of_done, created_at, supersedes_goal_version_id`

### AcceptanceCriterion
`id, goal_version_id, key, description, priority, validator_type, validation_spec, status, attempt_count, last_validated_at`

### Task
`id, run_id, plan_version, parent_task_id, description, expected_outcome, status, risk, required_capabilities, preferred_role, provider_constraints, expected_artifacts, validation_method, work_weight`

### TaskDependency
`task_id, depends_on_task_id, dependency_type`

### TaskExecution
`id, run_id, task_id, attempt, assigned_actor_session_id, created_at, ready_at, started_at, completed_at, status, queue_ms, active_ms, waiting_ms, blocked_ms, result_ref`

### Evidence
`id, run_id, task_id, task_execution_id, criterion_id, evidence_type, artifact_ref, structured_data, status, created_at`

### Artifact
`id, run_id, task_id, type, path_or_uri, content_hash, metadata, created_at`

### Finding
`id, run_id, task_id, criterion_id, severity, category, summary, source_ref, status, created_at`

## 4. Runtime actor and invocation entities

### ActorSession
Represents the visible Orchestrator or one sub-agent session.

`id, run_id, actor_type, role, provider, model, status, current_task_id, started_at, completed_at, working_ms, waiting_ms, blocked_ms, tasks_attempted, tasks_completed, tasks_failed, activity_summary, metadata`

The Orchestrator normally has no provider/model. Provider-backed Requirements/Planner/Developer/Test/Reviewer/etc. work is represented by AGENT actor sessions.

### SkillBinding
`id, actor_session_id, task_id, skill_id, skill_version, loaded_at, unloaded_at`

### ProviderInvocation
`id, run_id, actor_session_id, task_execution_id, provider, model, started_at, completed_at, status, input_tokens, output_tokens, cached_tokens, reliable_cost, trace_ref, error_code`

### ToolInvocation
`id, run_id, actor_session_id, task_execution_id, tool_name, tool_class, started_at, completed_at, status, safe_command_summary, artifact_refs, error_code`

### TestExecution
`id, run_id, task_execution_id, suite_or_command, started_at, completed_at, status, passed, failed, skipped, evidence_ref`

### PhaseExecution
`id, run_id, phase, iteration, started_at, completed_at, status, active_ms, waiting_ms, blocked_ms`

## 5. Canonical Event

### Event
`id, project_id, run_id, sequence, event_type, occurred_at, phase, task_id, task_execution_id, actor_session_id, correlation_id, causation_id, status, payload, trace_id`

Properties:
- append-only;
- unique `(run_id, sequence)` with monotonically increasing sequence;
- persisted transactionally with/after the state transition it describes;
- safe to replay for projections/audit, while workflow state remains authoritative;
- payload contains concise structured summaries and references, not secrets or private chain-of-thought.

## 6. Required event taxonomy

Core run/phase: `RUN_CREATED`, `RUN_STARTED`, `RUN_PAUSED`, `RUN_RESUMED`, `RUN_BLOCKED`, `RUN_CANCELLED`, `RUN_FAILED`, `RUN_COMPLETED`, `PHASE_STARTED`, `PHASE_COMPLETED`.

Context/memory: `MEMORY_SYNC_STARTED`, `MEMORY_SYNC_COMPLETED`, `MEMORY_RETRIEVED`, `MEMORY_INVALIDATED`, `MEMORY_PROMOTED`, `CONTEXT_PACK_CREATED`.

Goal/plan: `GOAL_VERSION_CREATED`, `ACCEPTANCE_CREATED`, `PLAN_CREATED`, `PLAN_REVISED`, `TASK_CREATED`, `TASK_READY`, `TASK_STARTED`, `TASK_WAITING`, `TASK_BLOCKED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_CANCELLED`.

Actors/skills/providers/tools: `ACTOR_STARTED`, `ACTOR_STATUS_CHANGED`, `ACTOR_COMPLETED`, `AGENT_ASSIGNED`, `SKILL_LOADED`, `PROVIDER_INVOCATION_STARTED`, `PROVIDER_INVOCATION_COMPLETED`, `TOOL_STARTED`, `TOOL_COMPLETED`.

Validation/review/repair: `TEST_STARTED`, `TEST_COMPLETED`, `EVIDENCE_RECORDED`, `REVIEW_STARTED`, `REVIEW_COMPLETED`, `CRITERION_PASSED`, `CRITERION_FAILED`, `REPAIR_REQUESTED`, `REPAIR_STARTED`, `REPAIR_COMPLETED`, `CHANGE_GUARD_COMPLETED`.

Delivery: `DOCUMENTATION_UPDATED`, `FINAL_VALIDATION_COMPLETED`, `COMMIT_CREATED`, `PUSH_COMPLETED`, `DELIVERY_BLOCKED`.

Security/human actions: `POLICY_DENIED`, `APPROVAL_REQUESTED`, `APPROVAL_RECORDED`.

## 7. Timing semantics

All timers derive from persisted timestamps/status events. Browser timers may interpolate display seconds from a known server timestamp, but refresh/reconnect must recompute from persisted state.

- **Wall time:** elapsed real time from start to end/now.
- **Active time:** intervals in a working/running state.
- **Waiting time:** intervals intentionally waiting for dependencies, provider/tool response, scheduling, or approval as classified by the runtime.
- **Blocked time:** intervals where progress cannot continue without remediation/decision.
- **Queue time:** task `ready_at -> started_at`.
- **LLM/tool/test time:** nested breakdowns; these can overlap with actor/task active time and must not be added to wall time as independent components.

## 8. Progress semantics

Progress is not model-estimated. Each plan version assigns `work_weight` to tasks (equal weight by default). A run's plan-completion percentage is the accepted/succeeded weight divided by total current-plan weight, with explicit handling for skipped/cancelled tasks according to policy. Phase status is derived from workflow state. Repair-generated tasks create a new/revised plan denominator and the UI displays the revision; progress is not forced to remain monotonic.

The UI must label this as **plan completion**, not estimated time remaining or probability of success.

## 9. Projections for API/UI

Maintain query projections/materialized views for:
- run snapshot/header and phase timeline;
- Orchestrator/agent roster with current task and timers;
- task DAG, attempts, blockers, dependencies, and critical path;
- acceptance/evidence/repair linkage;
- timeline/Gantt;
- live activity feed;
- tools/tests/provider usage;
- Git/delivery state;
- Project Brain/memory health;
- historical run/project metrics.

The Local Control Center reads projections through REST and streams new `Event`s via WebSocket/SSE. It never directly mutates projection tables.

## 10. Derived metrics

Run: success rate, wall/active/waiting/blocked time, first-pass acceptance, repair count/time, plan revisions, completion status.

Task: counts by state, queue/active/waiting/blocked/wall durations, first-attempt rate, rework, longest/shortest/average duration, critical-path membership.

Actor/agent: working/waiting/blocked/idle time, utilization, tasks attempted/completed/failed, current task, concurrency.

Parallelism: peak/average active agents, critical-path duration, parallel efficiency, blocked dependency time.

Provider/model: invocations, task outcomes, latency, token usage, reliable cost, errors; later success/cost/repair rate by task type.

Tools/tests: invocation counts, errors, duration, test pass/fail/skip counts.

Memory: hit rate, retrieval latency, context-pack size, repository re-analysis percentage, invalidations, indexed commit freshness, promotions.

Git/delivery: files changed, insertions/deletions, Change Guardian findings, commit/push status.

## 11. Tracing and logging

All operations include `trace_id`, `run_id`, and relevant task/actor/invocation IDs. Provider and tool calls are child spans. Use structured logs correlated to events; do not log secrets, full credentials, or private chain-of-thought. Raw provider prompts/responses are off by default and require explicit local debugging policy plus redaction.

## 12. Retention

Operational events, traces, provider/tool details, and run artifacts have configurable retention. Durable accepted project knowledge, ADRs, provenance, and required audit records follow longer project policy. Retention must not break source provenance for surviving memory items.


---

<!-- SOURCE: docs/08-features-and-roadmap.md -->

# Features and Roadmap

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10).

## 1. V1 foundation and end-to-end features

- Repository/project initialization and identity.
- Safe Git service and isolated worktree.
- Git-aware Project Memory bootstrap, incremental refresh, provenance, semantic/structured retrieval, and Context Packs.
- Versioned goal, measurable acceptance criteria, constraints, and definition of done.
- Dependency DAG planning, scheduling, durable state, idempotency, cancel/resume, and bounded repair.
- Specialized agent roles, dynamic skill registry, provider abstraction, and least-privilege tools.
- Developer -> Test -> Reviewer vertical slice with evidence-backed acceptance.
- Change Guardian, documentation update, final validation, safe commit, optional push, and memory curation.
- CLI, MCP, REST/WebSocket interfaces and cross-session/cross-assistant continuity.
- Durable runtime event/timing/projection model, tracing, audit, and core metrics.
- **Early V1 Thin Mission Control:** live run header, phase timeline, visible Orchestrator, sub-agent roster, current task per agent, authoritative timers, task status/counts, acceptance summary, repair state, and structured live activity.
- **V1 Full Local Control Center before release:** interactive task/agent DAG, Gantt/timeline, critical path, utilization, acceptance evidence/repair explorer, Project Brain, diffs, tests/tools, Git delivery, provider/token/cost metrics where reliable, and run/project history.
- Headless/CI mode independent of UI.

## 2. V1 CLI experience

```text
orqalis init
orqalis context "task"
orqalis run "task" --branch feature/x
orqalis run "task" --open
orqalis status
orqalis runs
orqalis memory status
orqalis ui
orqalis serve
```

## 3. V1 MCP experience

A connected coding assistant can retrieve project context, create/join a run, receive next work, report structured results/findings/evidence, request review, inspect status, and finalize a run. A run created by one compatible client can be continued by another because project/run state belongs to Orqalis.

## 4. V1.5 - richer execution and advanced operating features

- Parallel read/review agents and safe parallel implementation with per-task patch/worktree isolation plus Integrator.
- PR creation and GitHub issue ingestion.
- Rich human approval workflows in UI.
- Richer ADR generation and architecture visualization.
- Advanced run comparison, provider/skill quality benchmarking, cost optimization views, configurable dashboard layouts, and export/reporting beyond the V1 Control Center baseline.

## 5. V2 - team/server and multi-provider intelligence

- Central/team deployment with authentication, tenancy, remote workers, and optional queue/Redis.
- Multi-provider routing using quality/cost/latency history.
- Organization/team memory and policy packs.
- Remote MCP server with authentication.
- GitHub App integration.
- VS Code extension backed by the same REST/MCP/event APIs.
- Browser/UI validation agents and screenshot evidence.
- Provider/skill benchmark dashboards.

## 6. V3 - adaptive and portfolio orchestration

- Learned provider/skill routing.
- Cross-repository dependencies and portfolio memory.
- Organization conventions inherited across projects with policy-controlled overrides.
- Autonomous issue-to-PR workflows under explicit governance.
- Quality benchmark suite and pluggable marketplace for skills/providers.
- Advanced project knowledge-graph exploration.

## 7. Deliberately deferred complexity

Do not begin with Kubernetes, distributed queues, a custom vector database, full IDE replacement, autonomous protected-branch merges, or a full advanced dashboard before core telemetry/workflow exists. V1 intentionally builds a **thin** Mission Control early because observability is needed while the runtime is built, then completes the full signed-off Control Center before the V1 release gate. V1.5 adds richer orchestration and analytics beyond that baseline.


---

<!-- SOURCE: docs/09-implementation-plan.md -->

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
- Fixed Pitch-dark theme, responsive/a11y, developer mode.

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


---

<!-- SOURCE: docs/10-local-control-center.md -->

# Local Control Center and Runtime Visualization

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10).

## 1. Purpose and design principle

The Orqalis Local Control Center is the browser-based operating surface for active and historical runs. Its main job is to answer, at a glance: **What is Orqalis doing? Which sub-agents are running? What task is each agent working on? How long has each item taken? What is blocked? Why did review fail? What happens next?**

It is a client of the same Orqalis Core used by CLI, MCP, REST, and CI. It never owns canonical workflow state, runs its own orchestration logic, fabricates timers, or exposes private model chain-of-thought.

## 2. Launch experience

Default bind/URL: `127.0.0.1:7842` / `http://127.0.0.1:7842` (configurable).

```text
orqalis ui
orqalis ui --open
orqalis run "Implement offline sync" --open
orqalis serve
```

A run prints its run ID and browser URL. `--open` starts/reuses the local service and opens the run route. Headless/CI execution can disable UI hosting without changing workflow behavior.

## 3. Information architecture

```text
Orqalis
├── Home
│   ├── Projects
│   ├── Active Runs
│   └── Historical Metrics
├── Project
│   ├── Overview
│   ├── Project Brain
│   ├── Architecture / Decisions
│   └── Run History
└── Run
    ├── Mission Control        [primary]
    ├── Orchestrator
    ├── Agents
    ├── Tasks / DAG
    ├── Timeline / Gantt
    ├── Acceptance
    ├── Activity
    ├── Changes / Diff
    ├── Tests / Tools
    └── Delivery
```

## 4. Mission Control

The primary live-run screen includes:
- project, run ID, branch, base commit, goal, lifecycle state, plan version, repair iteration/max;
- authoritative wall-clock elapsed time and plan-completion percentage;
- user-facing phase projection: `CONTEXT -> GOAL -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> REPAIR -> DOCS -> DELIVER`;
- visible **Orchestrator** card with current state/phase, execution wave, task counts, active branches, policy gates, structured next transition, and timer;
- one card per sub-agent with role, provider/model when available, status, current task, loaded skills, working/waiting/blocked timer, and concise structured activity;
- task DAG/parallel branches and active blockers;
- task counts by state;
- acceptance pass/fail/testing/pending summary with repair linkage;
- repair-loop count/time;
- recent structured events and major tool/test activity.

The screen must remain useful without opening raw logs.

## 5. Orchestrator view

The Orchestrator is a first-class runtime actor, not an invisible header. Show:
- lifecycle state and user-facing phase;
- current execution wave/scheduler action;
- ready/running/waiting/blocked/succeeded/failed task counts;
- active/peak parallel branches;
- repair iteration/max;
- approval/policy/delivery gates;
- wall/active/waiting/blocked time;
- last structured coordination decision or state-transition reason;
- next expected transitions/tasks.

Do not show hidden reasoning. Any displayed decision is a deliberate structured runtime record suitable for audit.

## 6. Sub-agent roster and detail

Each agent card/detail shows:
- stable actor/session ID and role;
- provider/model if the adapter supplies it;
- `STARTING`, `WORKING`, `WAITING_FOR_DEPENDENCY`, `IDLE`, `BLOCKED`, `FAILED`, `COMPLETE`, or `CANCELLED`;
- current task ID/name and attempt;
- session/task elapsed time plus working/waiting/blocked breakdown;
- loaded skills and allowed tool classes;
- Context Pack summary: memory items, source files, ADRs/decisions, previous runs;
- files read/modified, artifacts/evidence produced;
- tool/test/LLM invocation counts;
- input/output/cached tokens and reliable cost when supplied by provider;
- completed/failed task history, dependencies, blockers;
- privacy-safe structured activity summary.

Provider cost must display `unavailable` rather than an estimate when the provider does not expose reliable usage/pricing inputs.

## 7. Tasks, DAG, and parallel execution

Task nodes show ID, outcome, owner, state, dependencies, attempt count, risk, elapsed time, and affected acceptance criteria. Selecting a node reveals task contract, expected artifacts, context, tools, timestamps, evidence, findings, changed files, and repair history.

The DAG shows dependency-ready work, parallel branches, blocked downstream nodes, and repair-generated tasks. V1 may render a simpler graph; V1.5 adds interactive layout and filters.

## 8. Timeline / Gantt

The timeline visualizes actual persisted intervals by agent/task over wall-clock time. It shows parallelism, waits, retries, repair branches, critical path, and handoffs. Every bar is derived from `TaskExecution`/`ActorSession` timestamps, not frontend timers.

Selecting a bar shows start/end/elapsed, active/waiting/blocked breakdown, dependency waits, owner, attempt, and evidence/artifacts.

## 9. Acceptance and evidence

Every criterion displays key, description, status, validator, responsible task/agent, attempt count, validation duration, evidence, failure reason, and linked repair task. PASS requires evidence.

A failed criterion should visually connect:

```text
REVIEW -> CRITERION FAILED -> DIAGNOSE -> TARGETED REPAIR -> RETEST -> REVIEW
```

The user can inspect why the criterion failed and what work was created to address it.

## 10. Time tracking definitions

Run: wall-clock, active orchestration, waiting, blocked, and optionally nested provider/tool/test durations.

Phase: wall/active/waiting/blocked duration for Context, Goal, Plan, Implement, Test, Review, Repair, Docs, and Deliver.

Task: `created_at`, `ready_at`, `started_at`, `completed_at`, queue time, active time, waiting time, blocked time, total wall time, attempts.

Actor/agent: session wall time, working, waiting, blocked, idle, and utilization.

LLM/tool/test durations can overlap with actor/task active time and are presented as breakdowns, not additive wall-clock components.

## 11. Progress semantics

The UI must not use model-written percentages. Plan completion is calculated from persisted task states and `work_weight` in the current plan version. Default is equal task weight. Repair may revise the plan and denominator; the UI shows the plan revision and may legitimately reduce completion percentage.

Do not label plan completion as ETA. ETA may be added later only from an explicit statistical estimator with uncertainty.

## 12. Operational statistics

Live/run statistics include:
- tasks succeeded/running/ready/waiting/blocked/failed;
- average/longest/shortest task duration and queue time;
- first-attempt acceptance/task success and reworked tasks;
- repair-loop count, criteria resolved, and time in rework;
- current/peak/average concurrency, critical-path duration, and parallel efficiency;
- per-agent utilization and task throughput;
- provider/model task counts, latency, tokens, errors, reliable cost, and later outcome quality;
- tool invocation counts/errors/duration;
- test suites/cases pass/fail/skip/duration;
- files changed, insertions/deletions, artifacts/evidence counts;
- Project Memory hits, retrieval latency, indexed commit freshness, invalidations, and promotions.

Historical project dashboards use the same metrics across runs to show whether memory, routing, and orchestration efficiency improve over time.

## 13. Live activity stream

Stream privacy-safe structured events with filters: Orchestrator, Agents, Tasks, Memory, Provider, Tools, Tests, Review, Repair, Security, Git/Delivery. Example rows are status transitions and observed actions such as `TASK_STARTED`, `TEST_COMPLETED`, `CRITERION_FAILED`, or a safe command summary.

The stream is not a chain-of-thought viewer.

## 14. Project Brain

Show the persistent project context used by agents:
- indexed commit and memory freshness;
- architecture facts/entities/relations;
- conventions and domain/business rules;
- ADRs/decisions and known issues;
- related prior runs/tasks;
- Context Pack items and source provenance;
- memory invalidation/promotion history;
- searchable knowledge graph in the full UI.

This view should make it easy to answer **why this context was supplied to the agent** using source references, not hidden reasoning.

## 15. Changes, tests, and delivery

Changes view: file tree/diff stats, scope labels, Change Guardian findings, safe diff rendering, documentation changes.

Tests/tools view: current/recent tool invocations, safe command summaries, status, duration, output/evidence references, test pass/fail/skip.

Delivery view: acceptance summary, final validation, Change Guardian, docs status, branch/base/head, changed files/diff, commit SHA/message, push state, memory-finalization commit, and any approval gate.

## 16. Developer mode

Optional local developer mode can reveal typed request/result payloads, Context Packs, selected memory IDs, event payloads, traces, provider/model IDs, token/latency stats, safe tool/Git command summaries, and test stdout/stderr. All data passes through redaction and chain-of-thought exclusion policies.

## 17. Frontend architecture and UX

Recommended: React + TypeScript + Vite, Tailwind CSS, accessible headless primitives, TanStack Query, a small local UI-state store, React Flow, Recharts, and Monaco where code/diff viewing is needed.

Visual direction: professional engineering mission control; dense but calm; restrained accents; clear semantic states; fixed Pitch-dark theme; keyboard navigation; responsive desktop/tablet layouts; reduced-motion support; subtle live transitions only where useful.

The frontend loads an authoritative snapshot then streams incremental events. UI-only state is limited to filters, panel selection, layout, and other presentation preferences.

## 18. Backend/event architecture

```text
Orqalis command/state transaction
          |
          +--> durable workflow state/projection
          +--> append Event(sequence=N)
                       |
                       +--> REST snapshot/projections
                       +--> WebSocket/SSE broadcast
                                      |
                               Local Control Center
```

Reconnect flow: fetch/reconcile snapshot, read `last_event_sequence`, subscribe with `after=<sequence>`, apply newer events idempotently.

## 19. Security and privacy

- Bind loopback by default.
- Remote access requires explicit enablement, authentication, and authorization.
- UI commands use the same Policy Engine and audit trail as CLI/MCP.
- Never emit secrets, credentials, sensitive raw command arguments, private chain-of-thought, or unredacted provider data.
- Do not make push/destructive controls available when policy denies them.

## 20. Delivery stages

**Early V1 thin Mission Control:** run header, phases, Orchestrator, sub-agent cards, current tasks/timers, task counts, acceptance summary, repair indicator, live events, refresh/reconnect correctness.

**V1 final Control Center:** before the V1 release gate, add interactive DAG/Gantt, agent/task detail analytics, critical path, Project Brain, diffs, tests/tools, delivery, historical/project metrics, run history/comparison, developer mode, and polished responsive theming. V1.5 adds deeper configurable analytics and richer orchestration controls rather than defining the first complete UI.

## 21. Acceptance criteria

- Orchestrator and every active sub-agent are identifiable without reading logs.
- Every running agent shows current task and authoritative elapsed/working/waiting/blocked time.
- Task dependencies, parallel work, blockers, attempts, and repairs are understandable.
- Refresh/reconnect reconstructs the same state/timers from persisted data.
- Progress is deterministic plan completion, not model-estimated or browser-faked.
- Acceptance failures show evidence, reason, and repair linkage.
- Historical runs reconstruct from persisted state/events.
- Headless CLI/MCP execution is independent of the UI.
- No private chain-of-thought or secrets are exposed.
- UI actions cannot bypass the Orqalis Policy Engine or Git delivery gates.


---

<!-- SOURCE: CODEX_HANDOFF.md -->

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


---

<!-- SOURCE: CONSOLIDATION_NOTES.md -->

# Orqalis Consolidation Notes

This v1.2 package reconciles every Orqalis design/handoff artifact created earlier in this session: the original modular bundle, original consolidated DOCX, enhanced modular bundle, enhanced DOCX, Local Control Center additions, sign-off, and Codex handoff.

## Reconciled differences

- The enhanced package added Local Control Center and runtime telemetry requirements; v1.2 integrates them across product, architecture, agents, memory, workflow, interfaces, security, data model, roadmap, implementation plan, sign-off, and Codex handoff rather than leaving them as an addendum.
- Implementation sequencing is normalized. Durable events/timing/projections are Phase 4, thin Mission Control is Phase 5, agent runtime follows, and the full Control Center is Phase 13.
- The previous PR list accidentally placed observability after MCP even though the phase plan required it earlier. v1.2 moves the canonical event/timing foundation before the thin UI and agent execution.
- Duplicate entity terminology is removed: `Event` replaces `Event` + `RunEvent`; `ActorSession` replaces competing `AgentExecution` + `AgentSession`; `TaskExecution` represents attempts while `Task` remains the plan definition.
- The Orchestrator is explicitly modeled/visualized as a first-class runtime actor while remaining the deterministic workflow owner, not an unconstrained coding agent.
- Time semantics are defined for wall/active/waiting/blocked/queue time; nested LLM/tool/test durations are not incorrectly summed as wall time.
- UI progress is explicitly deterministic plan completion, not a model estimate, ETA, or browser simulation. Repair can revise the plan denominator.
- Project Memory now has explicit Project Brain visibility and metrics so the system can measure whether repository re-analysis decreases over time.
- UI security is integrated with the same Policy Engine, loopback-by-default networking, redaction, audit, and chain-of-thought exclusion requirements.

## Supersession rule

Only the files in this v1.2 consolidated package should be handed to Codex as active requirements. Earlier session ZIP/DOCX files are historical inputs and should not be placed beside the canonical package in the implementation repository.


# Owner-approved distribution amendment - 2026-09-10

Global npm installation is the single V1 application distribution channel.
This amendment is also recorded in SIGNOFF.md and CODEX_HANDOFF.md.

## 7. Application distribution - npm amendment

The supported V1 installation is npm install -g orqalis. Node.js 22+ launches the
same Python 3.12+ Core through an isolated per-user runtime. The npm package carries
the compiled Local Control Center, migrations, skills, usage docs and local Compose
configuration. First launch verifies and installs pinned Python dependencies; database
migration and provider setup remain explicit operator actions.

The wheel is an internal build artifact, not a separate application installer. No
standalone executable, Python source release or Orqalis PyPI channel is maintained.
Contributor source setup and the Python SDK remain available for development.
See [ADR 0002](docs/adr/0002-npm-distribution.md). This does not change Core boundaries.

## Distribution and process entry points - npm amendment

All end-user interfaces are reached through the globally installed npm package.
The orqalis command delegates to Python Core; it owns no separate workflow state.
Interactive Windows users can invoke orqalis.cmd. MCP process hosts use an absolute
Node executable plus <global npm root>/orqalis/bin/orqalis.js and the usual MCP arguments;
no standalone executable or checkout-specific virtual environment path is required.

Complete first-launch setup with orqalis version before starting an MCP client.
SDK source development remains documented separately. See [MCP setup](docs/MCP.md) and
[ADR 0002](docs/adr/0002-npm-distribution.md) for the current install/launch contract.

## Distribution release gate - npm amendment

Phase 14 publishes a single reviewed npm tarball. Build the compiled UI and an internal
Python wheel, stage hash-locked dependencies and bundled Compose/docs, then npm pack.
Do not produce a separate executable installer, source archive or Orqalis PyPI release.

Validate global installation without npm lifecycle scripts, initial/cached startup,
command/MCP stdio forwarding, packaged UI/migrations/skills, source-free database setup,
upgrade behavior and retained user data. CI must exercise the same tarball on the
supported Windows/Linux/macOS matrix. Publication requires registry ownership and a
release-owner action. Contributor setup remains part of development, not another
application distribution channel. See [Publishing](docs/PUBLISHING.md).

## Installation and launch - npm amendment

The Local Control Center ships inside the global npm package. Users run
npm install -g orqalis, configure the database/provider, then orqalis ui --open or
orqalis run <request> --open. They do not build React or install a separate executable.
Node.js 22+ and Python 3.12+ remain prerequisites. Database Compose configuration is
included in the package; an existing PostgreSQL/pgvector service can also be configured.

npm installation never starts services or runs migrations automatically. The launcher
reuses an isolated Python runtime; the browser remains a projection of Core APIs/events.
See [README.md](README.md) and [ADR 0002](docs/adr/0002-npm-distribution.md).
