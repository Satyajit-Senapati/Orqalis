# ADR 0003: Local-first project store

- Status: Accepted
- Date: 2026-09-16
- Supersedes: the persistence portion of ADR 0001

## Context

The released Orqalis 1.0 architecture used PostgreSQL, SQLAlchemy, Alembic and pgvector as
the canonical store for projects, memory and orchestration records. That made a local
engineering assistant depend on infrastructure outside the repository, made project-root
isolation indirect, and prevented a cloned repository from carrying its durable Orqalis
knowledge and task history by itself.

Orqalis already separates storage-neutral domain models and application services from
repository protocols. The persistence implementation can therefore change without changing
the authority of the Orchestrator, acceptance review, repair loop, Change Guardian or Git
delivery.

## Decision

Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project
owns its project intelligence and execution history through a structured `.orqalis/`
directory located in the repository root. External database infrastructure is not required
for standard operation.

The resolved repository root is an application security boundary. CLI, MCP and web-service
composition bind to one root; no project operation may discover or mutate another root's
store. Project manifests contain portable repository-relative data and an explicit
filesystem schema version.

The store separates three concerns:

1. Repository Graph: deterministic, typed, source-derived nodes and relationships with
   `EXTRACTED` or `INFERRED` provenance. Graph and parser/search indexes are rebuildable.
2. Curated Project Memory: durable Markdown/YAML knowledge with source provenance,
   freshness, secret rejection and reviewable proposals.
3. Task History: one authoritative Task Capsule per user request, retaining the internal
   Run UUID and adding a human `ORQ-YYYYMMDD-NNNN` identity.

Task Capsules persist current YAML/JSON snapshots and append-only structured JSONL events.
They never persist hidden reasoning. Important mutations use a temporary file, validation,
flush/fsync and atomic rename. Short state locks and long controller leases are distinct so
nested application transactions cannot deadlock. Indexes and caches are never the only copy
of canonical history.

The application uses filesystem implementations of `ProjectStore`, `TaskStore`,
`EventStore`, `MemoryStore`, `GraphStore` and `ArtifactStore`. The former SQL adapters are
removed. A future standalone one-time exporter may read PostgreSQL, but no exporter command
is implemented today and a legacy database is never a parallel runtime authority.
Optional semantic embeddings may augment local retrieval; lexical, path, symbol, graph and
historical-task retrieval remain sufficient for normal operation.

## Canonical and derived data

Canonical data includes the project manifest/configuration, curated memory, Task Capsules,
acceptance evidence and durable decisions. Derived data includes parser caches, search
indexes, ranking caches and generated graph presentation. Deleting `.orqalis/cache/` or
`.orqalis/index/` must not delete project history; bootstrap/index services and
`orqalis rebuild-index` reconstruct them from canonical files plus the repository.

Git tracking is policy-driven. Durable project/memory/task summaries are tracked by default;
runtime locks, caches, indexes, raw tool output and configured execution event streams are
ignored while remaining physically inside the repository.

## Compatibility and migration

Filesystem layout migrations validate the old schema, back up affected files, transform
them, validate the new schema and update `manifest.yaml`. The active migration first moves
task and event persistence behind existing domain ports, then memory, graph, context,
interfaces and packaging. Required PostgreSQL dependencies and configuration are removed
only after filesystem parity tests pass.

Existing Run UUIDs and API shapes remain compatibility identifiers. Historical PostgreSQL
release evidence remains accurate for versions that used it. Future work may add a
one-time exporter for useful legacy records into the owning repository's `.orqalis/` tree;
the current product does not expose that command.

## Consequences

- `git clone`, `orqalis init` and normal Orqalis use require no database server.
- Copying the configured repository carries its tracked project intelligence.
- Filesystem correctness, atomicity, locking, schema migration and root isolation become
  release gates.
- React remains an application-API client and never reads `.orqalis/` directly.
- Live UI delivery combines the current snapshot, persisted event replay and in-process
  event broadcast.
- Large-team or hosted storage can be implemented later as an explicit adapter without
  weakening the project-local default or changing domain semantics.

## Research influences

The design was informed by, but does not vendor or copy, established open-source patterns:

- [Aider repository maps](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/repomap.md)
  for compact symbol-oriented repository context;
- [Serena project memories](https://github.com/oraios/serena/blob/main/docs/02-usage/045_memories.md)
  for focused, human-readable, Git-versionable durable memory; and
- repo-local MCP memory projects such as
  [coding-agent-memory-mcp](https://github.com/nova-land/coding-agent-memory-mcp) and
  [agent-memory](https://github.com/xChuCx/agent-memory) for rebuildable indexes,
  cross-assistant continuity and the importance of explicit project-root isolation.

Orqalis owns its contracts and implementation, adds typed graph provenance, memory
freshness/staging and Task Capsules, and remains subject to each reference project's
license rather than importing its code.
