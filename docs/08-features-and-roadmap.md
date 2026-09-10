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
