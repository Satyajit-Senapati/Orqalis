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
- `get_architecture`
- `get_decisions`
- `get_related_files`
- `get_project_graph`
- `get_related_symbols`
- `propose_memory_update`
- `refresh_project_memory`

Context retrieval combines ranked graph, curated memory, related task history, current Git
state and selected source within a caller-provided budget. Graph responses preserve
`EXTRACTED` versus `INFERRED` provenance. Memory proposals are secret-scanned and staged for
review; assistants do not write memory files directly.

## Task and run tools

- `list_tasks`
- `get_task`
- `get_task_context`
- `start_task`
- `get_run`
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

## Capability discovery

- `list_capabilities`
- `list_agents`
- `list_skills`
- `get_skill`

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
