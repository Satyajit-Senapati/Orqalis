# Interfaces and ecosystem integrations

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

Both local host commands select a Windows socket-only Selector loop to avoid reset-related
Proactor shutdown stalls. The process-wide loop policy and independent SDK/harness worker
loops are unchanged; other platforms retain automatic loop selection. The Windows UI loop
supports at most512 sockets and no asynchronous pipe/subprocess operations on that loop.
Current API handlers use sockets and synchronous workers. Uvicorn0.36 or newer supports
the shared custom-loop factory.

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

---

## Ecosystem integrations

Orqalis uses portable formats and small adapters around its existing application services.
The repository-local `.orqalis/` store, acceptance gates, and execution policies remain the
runtime authority. See the [open-source comparison](OPEN_SOURCE_REVIEW.md) for the research
and the remaining integration work.

### Portable Agent Skills

The skill registry accepts either the existing `skill.toml` + `instructions.md` format or
an [Agent Skills](https://agentskills.io/specification) `SKILL.md` in each immediate child
of an explicitly configured skill root. A directory must use exactly one manifest format.
No skills are downloaded or enabled by repository discovery.

Example directory:

```text
trusted-skills/
  code-review/
    SKILL.md
    references/
      checklist.md
```

Example `SKILL.md`:

```markdown
---
name: code-review
description: Review implementation changes against acceptance evidence.
license: MIT
allowed-tools: Read
metadata:
  orqalis-version: "1.0.0"
  orqalis-capabilities: "evidence_review"
  orqalis-applicable-when: "python, typescript"
---

Inspect the relevant changes and criterion-linked evidence.
Use references/checklist.md when reviewing a change.
Return specific findings and identify missing evidence.
```

Configure the **parent directory**, after reviewing the skills and their licenses:

```sh
export ORQALIS_SKILL_ROOTS='["/absolute/path/to/trusted-skills"]'
orqalis skills --json
```

```powershell
$env:ORQALIS_SKILL_ROOTS = '["C:/path/to/trusted-skills"]'
orqalis skills --json
```

The adapter validates required names/descriptions and the standard optional `license`,
`compatibility`, `metadata`, and `allowed-tools` fields. Metadata values must be strings.
Its deliberately strict profile rejects duplicate keys, YAML aliases/anchors, unsafe tags,
over-deep mappings, unknown top-level extensions, ambiguous formats, and oversized files.
Names use the ASCII subset supported by Orqalis's existing skill IDs and must match their
folder. General YAML frontmatter extensions used by some hosts are not silently accepted.

Orqalis-specific metadata is optional:

| Key | Behavior |
| --- | --- |
| `orqalis-version` | Semantic version; defaults to `0.0.0` for an unversioned imported skill. |
| `orqalis-capabilities` | Comma-separated capability names; defaults to the skill name. |
| `orqalis-applicable-when` | Optional comma-separated selection tags. |
| `orqalis-required-tools` | Comma- or space-separated Orqalis tool names. |

Tool declarations are **requirements, never grants**. The adapter understands Orqalis's
tool names and the bare aliases `Read`, `Write`, `Edit`, and `Bash`. Scoped expressions such
as `Bash(git:*)` and unknown host tools are rejected because their semantics cannot safely
be assumed. Role permissions and exact command/write policies still govern execution.
A skill that requires an unavailable tool cannot be selected.

Discovery exposes metadata. Activation exposes instructions and a content hash. Changes
to a `SKILL.md` after discovery require a new registry; legacy instruction changes after
activation also fail closed. Every read rejects symlink/junction traversal, limits content
to 100 KB, and checks exposed content for sensitive material.

MCP clients use `list_skills`, `get_skill`, and `get_skill_resource` to load referenced
UTF-8 text on demand. Resources remain inside the trusted skill directory and include a
hash. The resource reader does not execute scripts, fetch remote links, or expose binary
assets. Built-in provider workers receive selected instruction bodies; this change does
not grant them filesystem access to external skill resources. Review resource-dependent
skills for the client that will use them.

### Explainable graph queries

The graph now supports two bounded, deterministic operations:

```sh
orqalis memory impact src/service.py --repo . --depth 3 --limit 100
orqalis memory graph --repo . --json
orqalis memory path SOURCE_NODE_ID TARGET_NODE_ID --repo . --extracted-only
```

`impact` accepts an exact node ID or an exact repository-relative file path. A file query
starts with its graph nodes and walks **incoming** relationships to identify dependents.
The result is a candidate inspection set; it does not prove that a change breaks callers.

`path` accepts exact IDs from the graph and finds a shortest directed hop path. SDK and MCP
callers can also select incoming or bidirectional traversal and a minimum edge confidence.
Results retain source evidence, confidence, and `EXTRACTED`/`INFERRED` labels. Bidirectional
search preserves original edge direction in its evidence.

Queries allow depths 1..20 and node budgets 1..1000. A `truncated` flag distinguishes a
budget-limited search from an exhaustive negative result. Impact edges form a discovery
forest rather than returning every edge in a potentially dense induced subgraph. Graph
timestamps and parser versions identify the projection used.

| Interface | Impact | Path |
| --- | --- | --- |
| Python SDK | `sdk.graph_impact(node_or_path, ...)` | `sdk.graph_path(source_id, target_id, ...)` |
| MCP | `get_change_impact` | `find_graph_path` |
| CLI | `orqalis memory impact` | `orqalis memory path` |

Queries refresh the existing root-bound graph. Python uses AST extraction; JavaScript,
TypeScript and TSX use pinned Tree-sitter grammars. These are syntax facts, not full semantic
bindings. Calls and inheritance in JS/TS remain source-scoped expression references.
Python lexical/import/class candidates are labeled inferred; truncated extraction disables
candidate binding. Escaped module specifiers and quoted aliases are omitted with diagnostics
rather than guessed. Other supported languages contribute typed file nodes.

Traversal limits per source are 50,000 node visits, depth 64, 2,000 symbols, 5,000 calls,
1,000 import statements, 5,000 collected bindings, 300-character names, and 512-character
qualified names. File nodes expose `extraction_truncated` and diagnostic codes. Source
files are already bounded to 1 MB. Parser identity includes grammar versions and dialect;
unchanged content reuses its matching cache. Graphify is a design reference, not an installed
runtime dependency or a replacement store.

The read-only SDK/MCP tools `find_project_symbols`, `get_module_symbols`, `get_symbol_body`,
and `get_symbol_references` return bounded results with source coverage. Body reads require
the discovered source hash and exact byte spans; stale or oversized bodies fail explicitly.
See [symbolic read contracts](03-project-memory.md#bounded-symbolic-reads).

### Consistent retrieval

Context assembly, curated memory search, and the derived project index now share identifier
terms. `retry_offline`, `retryOffline`, and `retry offline` can match their constituent
words; acronyms such as `HTTPRequest` contribute `http` and `request`. Matching whole terms
avoids unrelated substring matches such as `cat` in `notification`.

The derived index version is `lexical-v3`; old indexes rebuild automatically when searched.
No canonical memory or Task Capsule migration is needed. These are lexical improvements,
not semantic embeddings or claims of a measured LLM-quality gain.

### Provider measurements

Control Center's Metrics view now groups persisted provider invocations by provider and
model. The same aggregates are available in `RunSnapshot.statistics.providers`:

- Counts for succeeded, failed, cancelled, interrupted, and running calls.
- p50/p95 observed call latency using the nearest-rank method, with sample coverage.
- Reported input/output tokens and cost, with usage/cost coverage.
- Counts by recorded provider error code.

Missing values remain unknown, while a reported zero remains zero. Latencies exclude
running calls, missing completion timestamps, and invalid negative durations. A small
sample's p95 is descriptive, not a performance guarantee. Provider execution success is
not evidence that acceptance criteria passed. No prices, tokens, or correctness scores
are inferred, and no telemetry leaves the machine.

Historical snapshots without a provider breakdown display an empty state. React continues
to consume API projections rather than reading the project store directly.

### Assistant harness boundary

The supported continuity path for Codex and Claude remains the project-bound MCP server.
See [Codex configuration](examples/codex-mcp.toml),
[Claude configuration](examples/claude-mcp.json), and [MCP policy](MCP.md).
The new graph and skill tools are available through this same transport.

`ExternalCLIProvider` remains a host transport contract. This change does not claim a
production Codex/Claude subprocess worker. Such a worker must translate host-specific
outputs, isolate its working directory and tools, map approvals, stop owned descendants,
redact event streams, and avoid replaying uncertain writes after a crash. Those conditions
are acceptance requirements in the research roadmap.


### Memory continuity, lifecycle controls, and local traces

Reviewed memory replacements retain their predecessor and use an atomic canonical
`memory/lifecycle.json` transition. Discovery, body paging, explicit references, and integrity
checks expose freshness and lifecycle separately. See [project memory](03-project-memory.md).
MCP permits bounded memory reads and proposals under project policy; operator review remains
in the CLI/service rather than becoming an unrestricted assistant approval tool.

MCP run pause/resume/cancel/recovery operations use existing application policies and
leases. Task-history pages have root/revision-bound cursors; response size is bounded,
while rebuilding the compact history index still scans local task metadata.

Control Center derives run/phase/attempt/agent/model/tool ancestry and critical paths from
persisted evidence. Stable local trace IDs support inspection and safe OpenTelemetry
correlation. No network telemetry exporter is enabled. See [MCP](MCP.md) and
[observability](07-data-model-and-observability.md) for contracts and limitations.


#### Definitions and occurrence evidence

Lexical search identifies call occurrences as `repository_reference` rather than symbol
definitions. An equally scoring definition precedes an occurrence. External-only calls
remain searchable. Standard Context Packs select file/declaration/documentation nodes;
REFERENCE occurrences remain in the graph for relationship evidence and explicit reference
reads but do not create extra primary context entries or lexical seeds. This prevents
repeated unresolved call sites from displacing the definition the caller wants to inspect.
