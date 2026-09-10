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

Visual direction: professional engineering mission control; dense but calm; restrained accents; clear semantic states; dark/light/system themes; keyboard navigation; responsive desktop/tablet layouts; reduced-motion support; subtle live transitions only where useful.

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

## Installation and launch - npm amendment

The Local Control Center ships inside the global npm package. Users run
npm install -g orqalis, configure the database/provider, then orqalis ui --open or
orqalis run <request> --open. They do not build React or install a separate executable.
Node.js 22+ and Python 3.12+ remain prerequisites. Database Compose configuration is
included in the package; an existing PostgreSQL/pgvector service can also be configured.

npm installation never starts services or runs migrations automatically. The launcher
reuses an isolated Python runtime; the browser remains a projection of Core APIs/events.
See [README.md](../README.md) and [ADR 0002](adr/0002-npm-distribution.md).
