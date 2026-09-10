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
