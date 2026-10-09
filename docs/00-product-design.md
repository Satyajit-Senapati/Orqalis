# Orqalis product design and roadmap

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

## Features and Roadmap

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10).

### 1. V1 foundation and end-to-end features

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

### 2. V1 CLI experience

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

### 3. V1 MCP experience

A connected coding assistant can retrieve project context, create/join a run, receive next work, report structured results/findings/evidence, request review, inspect status, and finalize a run. A run created by one compatible client can be continued by another because project/run state belongs to Orqalis.

### 4. V1.5 - richer execution and advanced operating features

- Parallel read/review agents and safe parallel implementation with per-task patch/worktree isolation plus Integrator.
- PR creation and GitHub issue ingestion.
- Rich human approval workflows in UI.
- Richer ADR generation and architecture visualization.
- Advanced run comparison, provider/skill quality benchmarking, cost optimization views, configurable dashboard layouts, and export/reporting beyond the V1 Control Center baseline.

### 5. V2 - team/server and multi-provider intelligence

- Central/team deployment with authentication, tenancy, remote workers, and optional queue/Redis.
- Multi-provider routing using quality/cost/latency history.
- Organization/team memory and policy packs.
- Remote MCP server with authentication.
- GitHub App integration.
- VS Code extension backed by the same REST/MCP/event APIs.
- Browser/UI validation agents and screenshot evidence.
- Provider/skill benchmark dashboards.

### 6. V3 - adaptive and portfolio orchestration

- Learned provider/skill routing.
- Cross-repository dependencies and portfolio memory.
- Organization conventions inherited across projects with policy-controlled overrides.
- Autonomous issue-to-PR workflows under explicit governance.
- Quality benchmark suite and pluggable marketplace for skills/providers.
- Advanced project knowledge-graph exploration.

### 7. Deliberately deferred complexity

Do not begin with Kubernetes, distributed queues, a custom vector database, full IDE replacement, autonomous protected-branch merges, or a full advanced dashboard before core telemetry/workflow exists. V1 intentionally builds a **thin** Mission Control early because observability is needed while the runtime is built, then completes the full signed-off Control Center before the V1 release gate. V1.5 adds richer orchestration and analytics beyond that baseline.
