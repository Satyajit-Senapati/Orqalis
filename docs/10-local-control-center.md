# Local Control Center and runtime visualization

Status: canonical UI contract, revised 2026-09-16. The former database-query architecture
is superseded.

## Purpose

The Local Control Center is a project-scoped view of the same Orqalis application services
used by CLI and MCP. It visualizes orchestration without becoming a second source of truth.

```text
React UI
   |
FastAPI + WebSocket
   |
Orqalis application services and EventBus
   |
filesystem stores
   |
<repository>/.orqalis/
```

React must never open, watch or mutate `.orqalis` files directly. No PostgreSQL service,
database URL or Docker installation is required to launch the Control Center. Docker may
remain an optional execution sandbox.

## Launch and root binding

`orqalis ui` and `orqalis serve` bind the API host to the resolved project root. Root
resolution follows explicit root, `ORQALIS_PROJECT_ROOT`, Git root and current directory.
The selected root is visible in project/status responses. Starting a server for Project B
must not reuse Project A's manifest, memory, capsules, indexes, runtime locks or event bus.

## Information architecture

The existing product surfaces remain:

- Mission Control: goal, current phase, overall status, next action and blockers.
- Orchestrator: immutable goal versions, plan versions, repair iteration and approvals.
- Agents: actor sessions, provider/model, skills, task assignment, state and timing.
- Tasks/DAG: dependencies, readiness, retries, results and evidence links.
- Timeline: persisted phase/actor/tool/provider activity with active and waiting time.
- Acceptance: criteria, reviewer results, findings, evidence and validation status.
- Changes and delivery: file changes, Change Guardian, tests, documentation and Git result.
- Project Brain: graph, curated memory, decisions, related tasks and freshness.
- Historical tasks: reopen any retained Task Capsule after a restart.

Views distinguish running, waiting, blocked, human-review, failed, cancelled and completed
states. A progress bar never implies acceptance: completion means the required evidence and
review gates passed.

## Snapshot, replay and live delivery

The Orchestrator publishes each structured event to a project-local EventBus. The event
store appends it to the active capsule's `execution/events.jsonl`; the WebSocket broadcaster
sends the same operational event to connected clients.

A late or reconnecting client:

1. loads the current run/task snapshot;
2. loads relevant persisted historical events using its cursor;
3. applies them idempotently;
4. subscribes to live events; and
5. detects gaps or resets and rehydrates from a fresh snapshot.

`execution/state.yaml` and other capsule snapshots provide current state without replaying
an unbounded log. JSONL provides the audit trail. UI projections never contain hidden
chain-of-thought or unredacted provider/tool payloads.

## Project Brain

Project Brain reads through services backed by:

```text
.orqalis/project/
.orqalis/memory/
.orqalis/memory/graph/
.orqalis/index/
.orqalis/tasks/
```

It can show files, symbols, modules, extracted/inferred dependencies, decisions,
conventions, related historical tasks and stale memory. Derived indexes and graph
presentations are explicitly marked rebuildable; curated memory and task history remain
canonical.

## Historical inspection

The API reconstructs a historical task from its capsule: request, context, goal,
acceptance, plan/DAG, phases, agents, timing, attempts, reviews, repair loops, evidence,
changes, delivery and final result. Missing optional stage files mean that stage did not
occur; the frontend must not fabricate it.

## Security and privacy

- All routes and subscriptions are scoped to the server's bound project root.
- Mutating operations enforce the same permission and approval policy as CLI/MCP.
- Durable memory and summaries pass secret scanning and redaction.
- Provider credentials come from environment, user configuration, keychain or provider
  configuration, never Project Memory.
- File paths exposed to the browser are repository-relative.
- Raw tool output is not copied into human-readable projections by default.

## Performance

The browser requests bounded pages and graph neighborhoods. Backend services use the local
task index, search index and graph ranking rather than loading every task or graph node.
Initial bootstrap may be deeper; one-file changes should normally reprocess only affected
files and relationships.

## Acceptance criteria

- The UI works after `orqalis init` on a clean machine with no database server.
- Refreshing or restarting preserves historical tasks from `.orqalis/tasks/`.
- Reconnect produces a consistent snapshot plus event timeline with no duplicate state.
- Live agent, phase, review, repair, evidence, change and delivery updates remain visible.
- Project Brain reports graph provenance and memory freshness.
- Project A and Project B cannot retrieve each other's state.
- The packaged web assets are served through FastAPI; no frontend filesystem access exists.
