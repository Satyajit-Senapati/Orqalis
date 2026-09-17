# Orqalis system architecture

> **Canonical local-first baseline - 2026-09-16.** This document supersedes the
> PostgreSQL-backed persistence assumptions in the 2026-09-10 v1.2 architecture. Earlier
> verification records remain historical evidence for the implementation tested then.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project
> owns its project intelligence and execution history through a structured `.orqalis/`
> directory located in the repository root. External database infrastructure is not
> required for standard operation.

## Architecture

```text
                    CLI / MCP / Web UI
                             |
                             v
                  Application Services
                             |
                             v
                       Orchestrator
                      /      |      \
                     v       v       v
                  Agents  Planner  Reviewer
                      \      |      /
                             v
                     Context Builder
                    /        |        \
                   v         v         v
        Repository Graph  Curated Memory  Task History
                    \        |        /
                             v
                        .orqalis/
                 local project filesystem
```

The CLI, Python SDK, project-scoped MCP server, loopback FastAPI/WebSocket application,
and React Control Center are adapters over the same application services. Domain models do
not depend on FastAPI, MCP, provider SDKs, SQLAlchemy sessions, table identities, database
transactions, or PostgreSQL types.

## Persistence contracts

Application code depends on storage-neutral responsibilities:

- `ProjectStore` owns project identity and configuration for one root;
- `MemoryStore` owns curated/source-backed durable knowledge;
- `GraphStore` owns typed, rebuildable repository structure;
- `TaskStore` owns Task Capsule aggregates and resume state;
- `EventStore` owns structured append-only lifecycle events;
- `ArtifactStore` resolves evidence and artifact metadata/payload locations.

The shipped adapters are filesystem-backed. PostgreSQL adapters are not present in the
current runtime, so there is no database persistence path or second source of truth.

## Project store

`.orqalis/manifest.yaml` declares filesystem backend and schema versions for the graph,
memory, and tasks. `config.yaml` holds project policy. Useful content is created lazily:

```text
.orqalis/
|-- manifest.yaml          # filesystem backend and schema versions
|-- config.yaml            # context, memory and Git tracking policy
|-- project/               # identity, stack, commands and current state
|-- memory/                # curated knowledge, proposals and graph
|-- tasks/                 # one authoritative capsule per request
|-- index/                 # rebuildable lexical/machine indexes
|-- runtime/               # locks and machine-local runtime state
`-- cache/                 # disposable parser/search cache
```

Important YAML/JSON documents use temporary-file write, flush, validation, and atomic
rename. Append-only JSONL updates use locks. Project/task locks are platform-safe and live
below `runtime/locks/`. A transaction marker lets interrupted Task Capsule commits roll
forward before readers observe state.

## Root resolution and isolation

The resolver uses explicit root, `ORQALIS_PROJECT_ROOT`, Git root, then current directory.
Explicit/configured roots fail closed when unavailable. Every store path is checked to
remain under the selected `.orqalis/`; linked stores and path traversal are rejected.

CLI uses `--repo`, MCP uses `--root`, and API/SDK composition receives a root. One server
started for project B cannot silently use project A. Concurrent assistants may operate on
different roots, while per-project locks serialize shared mutable documents.

## Canonical versus derived data

Canonical data:

- project manifest/configuration and durable project documents;
- curated memory records, decisions, provenance, and reviewed proposals;
- Task Capsules, acceptance/evidence, operational events, delivery and final summaries.

Derived data:

- repository graph representations and reports;
- search/term/task indexes;
- parser, graph, ranking, and search caches;
- generated HTML and reproducible context views.

Derived data may be deleted and rebuilt. No project history may exist only in an index or
cache.

## Graph and context

`ProjectGraphEngine` is Orqalis-owned and does not require Graphify or Tree-sitter. It uses
deterministic Python AST analysis plus generic/config/document parsing. Nodes and edges are
typed; provenance distinguishes `EXTRACTED` facts from `INFERRED` relationships.

The graph manifest records branch, HEAD, file hashes, parser version, graph schema, and
index time. Git state plus content hashes identify changed, new, deleted, renamed, dirty,
and untracked relevant files. Parser output is cached by content SHA-256. Incremental
refresh avoids reparsing unchanged files.

`ProjectContextBuilder` ranks a bounded selection from graph nodes, curated memory,
historical Task Capsules, dirty Git paths, and relevant source files. The persisted Context
Pack is a stage in the current Task Capsule, not a global conversation transcript.

## Task lifecycle and live events

Every request allocates `ORQ-YYYYMMDD-NNNN` before work proceeds. The capsule contains the
request, goal and acceptance, plan/DAG, actors, attempts, phases, review, evidence, changes,
delivery, and final result as those stages occur. `execution/state.yaml` is the current
authoritative snapshot; `execution/events.jsonl` preserves structured history. Readable
stage files are regenerable projections of the snapshot.

The EventBus appends durable events and broadcasts live WebSocket updates. A late UI
connection loads a current snapshot, reads relevant historical events, and then subscribes
to live events. React never reads `.orqalis/` directly.

## Deployment and optional components

Standard deployment is one local process plus files in the selected repository. Required
infrastructure is Git and the packaged Python runtime. A provider credential is required
only for provider-backed work.

Docker remains an optional command sandbox selected by execution policy. It is not a
persistence, initialization, MCP, API, or UI dependency. Redis, MongoDB, Neo4j, hosted
storage, and vector databases are not required. Embeddings may be added as an optional
adapter, while lexical/graph retrieval remains complete enough for standard operation.

The former PostgreSQL modules and dependency extra have been removed. No
PostgreSQL-to-filesystem exporter command is implemented; legacy data requires a matching
archived release or an external, one-time export process.

## Boundaries that remain unchanged

The storage redesign preserves goal generation, acceptance criteria, DAG planning,
dynamic agents and skills, provider abstraction, parallel work, reviewer, bounded repair,
Change Guardian, documentation updates, Git delivery, MCP, CLI, Local Control Center,
timing, telemetry, and cross-assistant continuity. Storage changes do not weaken workflow
or security gates.
