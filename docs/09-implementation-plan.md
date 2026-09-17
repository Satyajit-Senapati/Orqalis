# Local-first persistence implementation plan

Status: canonical migration sequence, revised 2026-09-16.

This plan supersedes the earlier database-first delivery sequence. Historical release
evidence remains valid for the versions it describes, but PostgreSQL, pgvector, Alembic,
Docker and `DATABASE_URL` are not prerequisites for standard Orqalis operation.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

## Delivery rules

- Preserve goal generation, acceptance criteria, DAG planning, agents, skills, providers,
  parallel work, review, repair, Change Guardian, documentation, Git delivery, MCP, CLI,
  Control Center and timing semantics.
- Move persistence behind storage-neutral application ports before removing a legacy
  implementation.
- Treat the resolved repository root as the isolation boundary for every operation.
- Make canonical files human-readable, schema-versioned, atomic and recoverable.
- Keep caches, indexes and rendered graph presentations rebuildable.
- Run focused tests after each coherent slice, followed by the full release gates.

## Required migration order

| Phase | Scope | Exit condition |
|---|---|---|
| A | Audit | Database dependencies, repositories, task/memory/event flows, API and UI consumers are mapped. |
| B | Filesystem domain contracts | Domain/application code depends on project, memory, graph, task, event and artifact store protocols rather than SQL sessions. |
| C | Root and bootstrap | Root resolution, `.orqalis/`, manifest/config, atomic I/O, locks and filesystem schema migrations are working. |
| D | Task Store | A request immediately creates a durable, resumable Task Capsule. |
| E | Event Store | Structured JSONL events and authoritative snapshots replace database event persistence; live broadcast remains available. |
| F | Project Memory | Curated Markdown/YAML memory supports provenance, freshness, secret rejection and staged updates. |
| G | Repository Graph | Deterministic bootstrap, typed provenance, content-hash cache and incremental refresh work for committed and dirty files. |
| H | Context Builder | Ranked graph, memory, related tasks, Git state and selected source become a bounded Context Pack. |
| I | Historical retrieval | The task/search indexes rebuild from canonical repository, memory, graph and capsule data. |
| J | CLI, MCP, API and UI | All standard interfaces bind to one filesystem-backed project service; React accesses it only through APIs. |
| K | PostgreSQL removal | Standard dependencies, startup, health checks, CI and package contents require no database or database environment variables. |
| L | Legacy import | Deliberately not shipped. No exporter command is implemented; version-specific external tooling may be used without restoring a database runtime authority. |
| M | Documentation and release validation | Canonical and shipped docs match implementation; isolation, recovery, package and regression gates pass. |

Implementation progress and dated evidence live in
[`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md). This file defines order and exit
conditions, not a substitute for test evidence.

## Filesystem foundation

`orqalis init` resolves an explicit root first, then `ORQALIS_PROJECT_ROOT`, then a Git
root, and finally the current working directory. It creates a schema-v2 manifest and only
the useful portions of this repository-relative layout:

```text
.orqalis/
|-- manifest.yaml
|-- config.yaml
|-- project/
|-- memory/
|   |-- modules/
|   |-- decisions/
|   |-- graph/
|   `-- staging/
|-- tasks/
|-- index/
|-- runtime/
`-- cache/
```

Mutable YAML/JSON is written through a validated temporary file, flushed, and atomically
renamed. JSONL event appends and shared projections use project-local locks. Filesystem
migrations validate the old schema, back up affected files, transform them, validate the
new schema and update the manifest last.

## Canonical and derived records

Canonical records are the manifest/configuration, curated memory, Task Capsules, durable
decisions, acceptance evidence and delivery outcome. Derived records are graph/search
indexes, parser and ranking caches, generated graph HTML and reproducible context
  projections. Deleting `cache/` or `index/` must not remove project history. Initialization
and the indexing service regenerate missing derived data; `orqalis rebuild-index` exposes a
full regeneration through the CLI.

## Task and event migration

Every request receives `ORQ-YYYYMMDD-NNNN` and a directory under `.orqalis/tasks/`.
`task.yaml` plus `execution/state.yaml` are current snapshots. `execution/events.jsonl` is
the structured operational audit stream; it never contains hidden reasoning. Goal, plan,
phase, agent, subtask, review, evidence, changes, delivery and final files are materialized
when their stage exists and remain projections of the authoritative snapshot.

Restart reads the capsule snapshot, event stream, plan DAG and review state. Suspended
states remain resumable; terminal results receive `final/result.yaml` and `final/summary.md`.

## Memory, graph and retrieval migration

Curated memory uses Markdown/YAML records with source paths, commit, introducing task,
confidence and verification time. Changed provenance marks a record stale until selective
revalidation. Durable changes follow `auto`, `review` or `manual` policy; review creates a
proposal under `memory/staging/`. Candidate content is secret-scanned before persistence.

The graph engine hashes repository files, reuses parser results by content hash, compares
branch/HEAD plus dirty content, reparses changed/new files, and removes deleted/renamed
nodes. Deterministically observed edges are `EXTRACTED`; secondary reasoning is
`INFERRED`. Ranking combines lexical, symbol, path, graph, recency, memory and task signals
so agents receive a bounded Context Pack rather than a repository dump.

## Interface migration

- CLI and SDK construct one root-bound filesystem service graph.
- MCP is launched with an explicit project root or a project-root environment binding.
- FastAPI exposes project, memory, graph, task and run views through application services.
- The Control Center never reads `.orqalis` directly. It loads a snapshot and persisted
  timeline before subscribing to live WebSocket events.
- Two assistants operating on different roots must never share memory, task or lock state.

## Git policy

The default `.orqalis/.gitignore` keeps caches, indexes, runtime files, locks, raw event
streams and generated graph HTML local. Manifest, project documents, curated memory and
configured durable task summaries may be tracked. Policy is explicit in `config.yaml`;
all data still remains physically below the owning repository root.

## Release gates

1. A clean machine can clone, install, initialize, run and resume without a database.
2. Project A and Project B remain isolated under simultaneous CLI/MCP use.
3. Atomic-write, interruption, invalid-data, lock and read-only cases are covered.
4. Dirty files, branch switches, renames, deletions, cache hits and incremental graph
   refresh are covered.
5. Memory freshness, staging, approval/rejection and secret detection are covered.
6. Task lifecycle, event replay, restart, historical retrieval and cross-assistant
   continuation are covered.
7. Deleting derived cache/index content is recoverable without loss of canonical history.
8. CLI, MCP, API, WebSocket and Control Center regressions pass.
9. Python lint, format, strict typing, tests, web lint/build/test and npm pack/install
   verification pass with no standard database configuration.

Docker may still be used as an optional command sandbox. Historical database releases and
their evidence remain archived, but no SQL compatibility extra belongs to the current
runtime.
