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

## 7. Application distribution - npm amendment

The supported V1 installation is npm install -g orqalis. Node.js 22+ launches the
same Python 3.12+ Core through an isolated per-user runtime. The npm package carries
the compiled Local Control Center, migrations, skills, usage docs and local Compose
configuration. First launch verifies and installs pinned Python dependencies; database
migration and provider setup remain explicit operator actions.

The wheel is an internal build artifact, not a separate application installer. No
standalone executable, Python source release or Orqalis PyPI channel is maintained.
Contributor source setup and the Python SDK remain available for development.
See [ADR 0002](adr/0002-npm-distribution.md). This does not change Core boundaries.
