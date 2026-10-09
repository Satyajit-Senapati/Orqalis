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
below `runtime/locks/`. Within one process, queued threads receive FIFO handoff;
same-thread reentrancy and the existing acquisition deadlines remain. The bookkeeping
queue adds per-lock memory and contention work; it does not guarantee storage latency.
A transaction marker lets interrupted Task Capsule commits roll
forward before readers observe state.

## Root resolution and isolation

The resolver uses explicit root, `ORQALIS_PROJECT_ROOT`, Git root, then current directory.
Explicit/configured roots fail closed when unavailable. Every store path is checked to
remain under the selected `.orqalis/`; linked stores and path traversal are rejected. Each
path component, including parents of missing descendants, is checked with one non-following
metadata read for symlink and junction identity. Missing/non-directory entries permit
parent traversal; other filesystem errors propagate before storage access. No metadata
cache replaces these checks.

CLI uses `--repo`, MCP uses `--root`, and API/SDK composition receives a root. One server
started for project B cannot silently use project A. Concurrent assistants may operate on
different roots, while per-project locks serialize shared mutable documents.

## Canonical versus derived data

Canonical data:

- project manifest/configuration and durable project documents;
- curated memory records, decisions, provenance, reviewed proposals, and `memory/lifecycle.json`;
- Task Capsules, acceptance/evidence, operational events, delivery and final summaries.

Derived data:

- repository graph representations and reports;
- search/term/task indexes;
- parser, graph, ranking, and search caches;
- generated HTML and reproducible context views.

Derived data may be deleted and rebuilt. No project history may exist only in an index or
cache.

## Graph and context

`ProjectGraphEngine` is Orqalis-owned; Graphify is a research reference. Python uses the
standard AST parser, while JavaScript, TypeScript and TSX use pinned MIT Tree-sitter binding
and grammar wheels. Other supported source/config/document formats have typed file nodes.
Extracted expressions and inferred Python binding candidates remain distinct. JS/TS calls
and inheritance are syntax occurrences, not guessed global targets. Exact byte spans enable
hash-checked symbolic reads; file-level diagnostics expose incomplete extraction.

Memory successors activate through atomic canonical lifecycle transitions. Discovery previews,
explicit reference/body reads and integrity reports preserve historical knowledge without
injecting every record. Output budgets do not imply zero backend graph or memory scans.

The graph manifest records branch, HEAD, file hashes, parser version, graph schema, and
index time. Git state plus content hashes identify changed, new, deleted, renamed, dirty,
and untracked relevant files. Parser output is cached by content SHA-256. Incremental
refresh avoids reparsing unchanged files.

A retained graph engine remembers only one immutable pair of the actual graph-file SHA-256
and its previously verified canonical model digest. Every load still strictly decodes the
same bytes hashed, validates fresh objects and checks the current manifest/schema/parser.
Only explicit timestamps qualify; changed bytes and failed validation invalidate the proof.
No graph model is retained, so returned metadata mutations cannot poison later loads. This
avoids repeated serialization on retained engines/builders; SDK/MCP calls constructing fresh
instances do not reuse the proof across requests. There is no persisted cache or extra database.

`ProjectContextBuilder` ranks a bounded selection from graph nodes, curated memory,
historical Task Capsules, dirty Git paths, and relevant source files. The persisted Context
Pack is a stage in the current Task Capsule, not a global conversation transcript.
The builder delegates source-root normalization and common Git-directory validation to
its graph engine using the same injected Git service, then uses the engine's normalized
source for status and memory freshness. This removes duplicate Git subprocesses while
keeping canonical storage and workspace inspection separate.


Git status validates the repository root and reads branch, HEAD and all tracked/untracked
changes in one NUL-delimited porcelain-v2 call, with ahead/behind computation disabled.
Graph refresh captures this status inside its existing lock; context uses that same result.
Neither operation caches status across requests. Parsing temporarily holds the richer Git
metadata, so fewer subprocesses do not establish a universal memory or latency improvement.
A custom graph engine overriding only `refresh` must also customize `refresh_with_status`
for the context path. A `LocalGitService` subclass overriding `resolve_commit` must customize
`status` if it expects that override to determine status HEAD; other Git injection remains.

For the built-in memory service, a Brain request with matching canonical and inspected
roots builds context once and projects its freshly validated graph into architecture
entities and relations. A fresh canonical-project read, exact roots and project IDs guard
this sharing. Worktrees, custom memory subclasses and instance graph/context overrides
retain separate reads. There is no externally supplied graph tuple or retained query cache.
Class-level monkeypatch equivalence is not promised. The fast context span starts after
its canonical-project lookup; projection remains outside that span.

Ordinary descendant storage paths on the base `ProjectLayout` use one fresh complete
ancestry check covering target, store and parents. Absolute escapes, traversal and subclasses
retain the original separate store check. Both resolves, containment checks and independent
atomic-write guards remain. Error precedence and transient metadata observations can differ;
this does not add an atomic filesystem snapshot or remove existing filesystem race limits.

## Task lifecycle and live events

Every request allocates `ORQ-YYYYMMDD-NNNN` before work proceeds. The capsule contains the
request, goal and acceptance, plan/DAG, actors, attempts, phases, review, evidence, changes,
delivery, and final result as those stages occur. `execution/state.yaml` is the current
authoritative snapshot; `execution/events.jsonl` preserves structured history. Readable
stage files are regenerable projections of the snapshot.

Task Capsule persistence commits durable events; the process-local EventBus broadcasts
after commit. A late UI
connection subscribes before loading the snapshot and replaying durable events so a commit
cannot fall between replay and subscription. Trace ancestry and provider measurements are
derived from persisted identities and observations. React never reads `.orqalis/` directly.

The local WebSocket stream pairs durable snapshot/event delivery with a dedicated inbound
disconnect receiver. Completion or failure of either cancels and joins both coroutines and
releases its process-local event subscription. Already-running filesystem worker I/O finishes
under the usual locks; it is not force-killed. Subscribing before durable replay and checking
snapshot/event cursors still prevent replay gaps, while the original one-second fallback
observes external-process changes. Peer closure therefore stops obsolete stream polling.

The controls projection reads policy and approval requests through one injected unit of
work, keeping them on the same loaded run snapshot. Existing individual policy/list APIs
and all approval mutation/checkpoint guards remain. Custom service subclasses that override
only those individual read methods must override `control_state` to customize the combined
API view; factory/repository injection stays intact.

## Deployment and optional components

Standard deployment is one local process plus files in the selected repository. Required
infrastructure is Git and the packaged Python runtime. A provider credential is required
only for provider-backed work.

Docker remains an optional command sandbox selected by execution policy. Application-owned
containers have durable machine-local receipts under `runtime/sandboxes/`, outside writable
worktrees; exact ownership and cleanup are reconciled before recovery/reuse. It is not a
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

## Memory loading in a project transaction

A project unit of work loads source memory on its first actual memory access. Task-only
commit, rollback and close do not construct that repository or load its derived graph.
The memory snapshot therefore begins at first access, rather than at project UoW creation.
First access retains the coherence lock and canonical validation; writes reload under
the original write lease. Corrupt memory still fails closed when memory is used.

## Auxiliary identity transaction ordering

Provider, tool, review and delivery entities remain inside their owning Task Capsule.
Run-owned reads use that owner directly. Global auxiliary identity checks share a
project-local lease through the filesystem transaction, preserving full recovery,
canonical validation and duplicate rejection. Before waiting for that lease, the
session releases every held run-state lock; it reacquires them in stable order and
checks each persisted generation before continuing staged work. Concurrent changes
cause a conflict requiring rollback rather than permitting stale authorization.

Auxiliary identity work must precede a retained source-memory write lease. Same-thread
nested transactions cannot reuse another session's auxiliary lease. Both cases fail
fast. Acquisition failures release partial locks and invalidate the transaction until
rollback. No derived ownership index or external database was introduced. This lease
serializes auxiliary identity mutation transactions within one project; network provider
work takes place after those transactions close.
