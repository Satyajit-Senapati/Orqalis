# Assistant interoperability through MCP

Orqalis MCP exposes high-level, policy-checked application services over stdio. It uses the
same repository-local `.orqalis/` authority as CLI, SDK and API; it does not expose arbitrary
filesystem mutation and does not require PostgreSQL or `DATABASE_URL`.

## Launch and root isolation

Create a policy for the initialized project, then launch with an explicit root:

```bash
orqalis mcp --policy /path/to/mcp-policy.json --root /path/to/repository
```

The process resolves and binds that root once. The policy `project_id` must match the
project identity in the bound root's manifest. A mismatch fails closed. Tool calls cannot
select another path or project after startup.

When a host supplies environment variables instead of CLI arguments, use
`ORQALIS_PROJECT_ROOT`. Resolution priority is explicit `--root`, project-root environment,
Git root, then current directory. Explicit root is strongly preferred for assistant hosts.
See [`examples/codex-mcp.toml`](examples/codex-mcp.toml), `claude-mcp.json` and
`vscode-mcp.json` for launcher shapes; keep provider credentials outside project memory.

Run separate MCP processes for simultaneous Project A and Project B sessions. A single
hardcoded user-level server must never silently redirect both assistants to one project.

## Policy

The server is read-only unless `allow_work` and a server-owned execution policy are present.
Delivery additionally requires `allow_delivery` and an explicit delivery policy. Control
mode and approval gates apply exactly as they do through CLI. The server enforces project ID
scope for every run and task lookup.

Policy supplies:

- `project_id`;
- `workspaces_root`;
- work/delivery permission flags;
- optional execution and delivery policies;
- reviewer provider; and
- autonomous or supervised control mode and gates.

MCP stdout is reserved for protocol frames. Logs and optional console telemetry go to
stderr. Tool errors cross a typed boundary and must not leak credentials or local absolute
paths unnecessarily.

## Project, graph and memory tools

- `get_project`
- `get_project_context`
- `search_project_memory`
- `discover_project_memory` (bounded summaries and stable record/reference IDs)
- `get_project_memory` (bounded record-body pages and explicit lifecycle)
- `check_project_memory` (read-only reference/lifecycle integrity)
- `get_architecture`
- `get_decisions`
- `get_related_files`
- `get_project_graph`
- `get_related_symbols`
- `find_project_symbols` (bounded symbol discovery)
- `get_module_symbols` (bounded outline)
- `get_symbol_body` (exact symbol ID plus required discovered source hash)
- `get_symbol_references` (bounded static-graph candidates)
- `get_change_impact` (bounded incoming dependencies, with edge evidence)
- `find_graph_path` (bounded shortest paths between graph node IDs)
- `propose_memory_update`
- `refresh_project_memory`

Context retrieval combines ranked graph, curated memory, related task history, current Git
state and selected source within a caller-provided budget. Graph responses preserve
`EXTRACTED` versus `INFERRED` provenance. Memory proposals are secret-scanned and staged for
review; assistants do not write memory files directly. Proposals can supply an optional
`summary`, stable memory-ID `references`, and `supersedes` predecessor. Supersession
uses the configured review policy and retains historical records; it is not a destructive
replacement. Discovery precedes explicit body reads, so long records do not need to
enter every task context.

Symbol bodies require the source SHA256 returned by discovery and reject stale files.
Reference results retain extracted/inferred provenance and report static graph coverage;
they do not claim complete language-server reference resolution. All four tools bind to
the configured root and enforce their serialized response budgets.

## Task and run tools

- `list_tasks`
- `list_task_page` (bounded compact summaries and continuation cursor)
- `get_task`
- `get_task_context`
- `start_task`
- `get_run`
- `pause_run`
- `resume_run`
- `cancel_run`
- `recover_task`
- `get_goal`
- `get_plan`
- `get_next_work`
- `report_result`
- `report_finding`
- `review_run`
- `finalize_run`

`start_task` creates the Task Capsule before execution. Read tools return validated capsule
or snapshot models rather than raw paths. Reporting and finalization update authoritative
state/events through application services and normal evidence, review, approval and Git
gates.

## Bounded history discovery

`list_task_page(limit=50, cursor=null)` returns compact task-index `items`, `total`,
`revision`, and `next_cursor`. Limits are 1..100. Follow `next_cursor` until it is null;
pass cursor strings unchanged. Results sort newest first by creation time and capsule ID,
including a deterministic tie-breaker for identical timestamps. Page summaries contain
index metadata; use `get_task` for acceptance, agents, final delivery, and stage details.

A cursor is bound to the resolved project root and exact compact-index revision. If tasks
are added or their indexed metadata changes, pagination fails with a typed conflict and
the client must restart without a cursor. A cursor cannot select another project/path.
It is a read position, not an authentication credential. Existing `list_tasks` remains
compatible; the new tool avoids enriching every capsule merely to return one page.
The current implementation validates all canonical task summaries and repairs the compact
index only when changed, missing or corrupt; response pagination
does not claim constant-time backend access for arbitrarily large histories.

## Lifecycle controls

`pause_run`, `resume_run`, and `cancel_run` require `run_id` and an explicit
`idempotency_key` (1..120 non-blank characters). They call the same Core services as CLI
and HTTP and require the server's work permission. Repeating a successful request with
its original key does not create another transition; reusing a transition key for a
conflicting action fails. Responses describe current authoritative state.

Pause requires workers to have reached waiting checkpoints and preserves the suspended
state; it rejects a run with a running attempt. Resume restores
that state without bypassing approval, acceptance, or delivery gates. Cancel is terminal.
An MCP host owns its external worker processes: it must stop its own work when pausing,
cancelling, or disconnecting. A transport cancellation alone is not a durable run control.

For interrupted work, inspect the retained workspace and stop previous workers first.
`recover_task` takes `run_id`, `execution_id`, `reason`, `idempotency_key`, and
`acknowledge_uncertainty` (default `false`). It rejects recovery without acknowledgement,
while another worker holds the run lease, for unrelated/stale attempts, or when Core's
attempt/goal/state checks fail. Recovery records an audited replacement authorization;
it never replays an uncertain tool call or resumes a suspended run automatically. Call
`resume_run` separately when appropriate, then `get_next_work` for the new attempt.

These controls are verified through generic MCP clients and durable replacement-client
integration tests. They do not assert that native Codex, Claude, or Copilot processes were
launched or that host-specific interruption hooks were qualified.

## Capability discovery

- `list_capabilities`
- `list_agents`
- `list_skills`
- `get_skill`
- `get_skill_resource` (bounded UTF-8 resources inside trusted skill roots)

Skill content and provider capability are descriptive inputs, not persistence authority.

## Cross-assistant continuity

An assistant can create a task, persist goal/plan/context/progress, and stop. Another MCP
client launched against the same explicit root can inspect the Task Capsule and continue
without receiving the first client's conversation history. Structured events and snapshots
contain operational state and evidence, never private chain-of-thought.

## Host example

Conceptually configure an assistant host to spawn:

```text
command: orqalis
args: [mcp, --policy, /absolute/path/to/policy.json, --root, /absolute/path/to/repo]
```

On npm installations a host may invoke Node with the installed `bin/orqalis.js` path when
shell shims are unreliable. The root and policy are still explicit. Do not add database
variables to new host configuration.

## Compatibility

The current package contains no PostgreSQL extra, database migration command or
database-to-filesystem exporter. MCP always resolves a repository-local store and cannot
select a database-backed memory authority.
