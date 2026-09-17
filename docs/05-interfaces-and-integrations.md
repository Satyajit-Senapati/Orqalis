# Interfaces and integrations

> **Canonical local-first baseline - 2026-09-16.** All interfaces bind to one repository
> and use its filesystem store. No standard interface requires `DATABASE_URL`.

## Shared boundary

CLI, SDK, MCP, REST/WebSocket, and the Control Center call the same application services.
They do not mutate `.orqalis/` paths directly. Root-bound filesystem stores enforce
identity, atomicity, locks, schema validation, and recovery.

## CLI

Implemented project and diagnostic commands include:

```text
orqalis init [--repo PATH]
orqalis status [--repo PATH]
orqalis doctor [--repo PATH]
orqalis context TASK [--repo PATH]
orqalis rebuild-index [--repo PATH]
orqalis tasks [--repo PATH]
orqalis task show TASK_ID [--repo PATH]
orqalis memory status|refresh|search|graph [--repo PATH]
```

Workflow commands include `run`, `define-goal`, `execute`, `finalize`, `runs`, `runs show`,
`runs prepare`, `runs pause`, `runs resume`, `runs cancel`, `runs recover`, goal revision,
plan controls, approvals, agents, skills, capabilities, `serve`, and `ui`.

`orqalis init` is idempotent and reruns deterministic bootstrap work. `rebuild-index`
forces regeneration of disposable graph/search artifacts. `tasks` and `task show` read the
compact local history and validated capsules. `memory graph --open` may open the generated
graph document in a local browser.

Filesystem layout migrations run through project-store services during supported opens.
There is no database migration CLI in the current product.

## Python SDK

`Orqalis(root=...)` resolves and binds a filesystem store. `ORQALIS_PROJECT_ROOT` may
provide the root when no explicit argument is supplied. A caller may still inject a unit of
work for tests or optional adapters; injected storage does not change default composition.
The SDK refuses initialization against a different root than the one to which it is bound.

## MCP

MCP is project-scoped stdio:

```sh
orqalis mcp --root /absolute/project --policy /absolute/mcp-policy.json
```

The policy identifies the project and controls work/delivery permissions. MCP stdout is
reserved for protocol framing; setup, logging, and telemetry use stderr. Current high-level
tools include:

```text
get_project
get_project_context
search_project_memory
get_architecture
get_decisions
get_related_files
get_project_graph
get_related_symbols
list_tasks
get_task
get_task_context
propose_memory_update
refresh_project_memory
start_task
get_run
get_goal
get_plan
get_next_work
report_result
report_finding
review_run
finalize_run
list_capabilities
list_agents
list_skills
get_skill
```

MCP exposes project/run/architecture/decision resources but no general filesystem write
tool. A client cannot widen policy, approve its own supervised gate, fabricate acceptance
evidence, or select another repository through a tool argument.

Codex, Claude Code, Copilot, and other MCP clients can continue the same Task Capsule
because continuity comes from `.orqalis/`, not model conversation history. Start a separate
root-bound process for each repository.

## REST and WebSocket

The loopback FastAPI app exposes project initialization/context/memory/brain, run creation
and snapshots, plan/goal controls, approvals, events, agents, tasks, acceptance, metrics,
recovery, cancellation, pause/resume, timeline, and diff endpoints. The run WebSocket emits
live EventBus records after a persisted snapshot/history handshake.

FastAPI calls application services and filesystem repositories. It never makes the React
client parse local files, and it does not use database queries in the standard runtime.
Remote hosting is not enabled; adding it requires authentication, authorization, tenancy,
and root-scoping design.

## Local Control Center

`orqalis ui [--open]` and `orqalis serve` host the packaged UI on loopback. The process is
terminal-owned and stops with `Ctrl+C`; no system service is installed. The UI is a
projection of canonical snapshots/events and cannot own workflow transitions, timers, or
persistence.

## Provider and credential configuration

Provider selection is independent of storage. OpenAI and Anthropic credentials/models use
environment or user/provider configuration. `ORQALIS_OPERATOR_TOKEN` protects browser
approval actions. None belongs in project memory, config, Task Capsule projections, or MCP
policy committed to Git.

Optional command isolation uses an execution policy with exact argv and write scopes.
Docker policy is separate from persistence and is not needed for read-only MCP, context,
memory, API, or UI use.

## Compatibility and future interfaces

No PostgreSQL compatibility adapter or exporter CLI is shipped. New interface aliases must
call existing root-bound services rather than introduce a parallel store. Historical
database exports, if needed, belong to version-specific external tooling.
