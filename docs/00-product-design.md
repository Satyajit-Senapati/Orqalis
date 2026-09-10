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
