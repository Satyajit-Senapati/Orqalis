# CODEX HANDOFF - Orqalis local-first persistence

Status: canonical implementation handoff, revised 2026-09-16.

## Mission

Preserve Orqalis's provider-neutral orchestration workflow while making the repository-local
filesystem its standard persistence authority.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

## Read order

1. `SIGNOFF.md`
2. `docs/SOURCE_OF_TRUTH.md`
3. ADR 0003, then ADR 0001 and ADR 0002 for unaffected decisions
4. `docs/01-system-architecture.md`
5. `docs/07-data-model-and-observability.md`
6. `docs/09-implementation-plan.md`
7. interface, memory, security and Control Center chapters
8. `docs/IMPLEMENTATION_STATUS.md` for dated evidence

Database-first text in old releases and readiness evidence is historical. ADR 0003
supersedes ADR 0001's persistence selection.

## Required execution order

Audit first; then storage-neutral contracts; root/bootstrap; Task Capsules; events;
curated memory; repository graph; Context Builder; historical retrieval; interfaces;
database implementation removal; documentation and release validation. Do not keep
PostgreSQL as a hidden authority or add a parallel database.

After each coherent slice, run focused tests and the relevant lint/type checks. Preserve
user changes in a dirty worktree. The SQL implementation was removed only after filesystem
parity tests passed; do not recreate it as a compatibility shortcut.

## Storage contract

- Resolve explicit root, `ORQALIS_PROJECT_ROOT`, Git root, then current directory.
- Bind each SDK/CLI/MCP/API service graph to one resolved root for its lifetime.
- Keep project-relative paths in manifests and public records.
- Use schema-versioned YAML/JSON/Markdown/JSONL under `.orqalis/`.
- Use validated temporary writes, flush/fsync where appropriate, atomic rename and
  platform-safe locks.
- Fail closed for missing, corrupt, read-only or unsupported-schema stores.
- Keep cache/index/presentation derived and reconstructable.

Canonical data is manifest/configuration, curated memory, Task Capsules, evidence, durable
decisions and delivery results. Derived data is parser/search/ranking cache, indexes,
generated graph presentation and reproducible Context Pack projections.

## Knowledge separation

Repository Graph contains source-observable structure and typed relationships. Mark direct
deterministic analysis `EXTRACTED`; mark secondary reasoning `INFERRED`, with confidence
and evidence.

Curated Project Memory contains durable product, architecture, technology, convention,
domain, workflow, testing, pitfall, module and ADR knowledge. Record source paths, commit,
introducing task, confidence and verification time. Changed provenance marks an item stale.
Secret-scan proposals and never persist credential values.

Task History contains one self-contained capsule for each request: request, context, goal,
acceptance, plan/DAG, assignments, execution, review, evidence, changes, delivery and final
outcome. Persist structured operational events, never chain-of-thought.

## Task/runtime invariants

- The Orchestrator owns state transitions.
- Goal versions are immutable once execution depends on them.
- PASS requires criterion-linked evidence.
- Repair is targeted, bounded and auditable.
- Task snapshots provide current authority; JSONL provides history.
- Unknown side effects are not blindly replayed after restart.
- Change Guardian and Git policy gate delivery.
- Provider conversations, UI state and indexes are never sources of truth.

## Graph, index and context

Initial bootstrap may scan deeply. Later refresh compares branch/HEAD, tracked and
untracked relevant files, stored hashes and dirty content. Reparse only changed/new files,
remove deleted/renamed files and reuse parser output by content hash. Record duration,
processed count and cache hits/misses.

Rank lexical/path/symbol matches, graph neighborhood/centrality, Git recency, memory and
related tasks into a configured budget. Agents receive the Context Pack rather than an
unconditional repository rescan. Indexes must rebuild from repository, memory, graph and
Task Capsule summaries.

## Interfaces

CLI, MCP, SDK, REST/WebSocket and the Control Center use the same application services.
MCP exposes high-level project/context/memory/graph/task/run operations, not arbitrary file
mutation. FastAPI is the browser gateway. A late UI client loads a snapshot and persisted
events, then subscribes live.

Only document commands/tools that exist in the checked-in implementation. The current
source contains no PostgreSQL adapter, schema command or database exporter.

## Security and configuration

Provider credentials stay in environment variables, OS keychain, user configuration or
provider configuration. Project Memory stores only the requirement for a credential, not
its value. Default tracked/ignored policy is explicit and reviewable.

Docker may be used for optional command isolation. Historical PostgreSQL data must be
handled outside the current runtime with an appropriate archived release or bespoke export;
database compatibility code is not shipped by the current package.

## Definition of done

- Clean clone/init/run/resume works with no database server or `DATABASE_URL`.
- Every request creates a durable Task Capsule immediately.
- Cross-assistant continuation needs no private conversation history.
- Project A and Project B cannot retrieve or mutate each other's knowledge.
- One-file changes avoid full graph reparsing.
- Deleted cache/index is recoverable without canonical loss.
- Atomicity, locking, schema migration, branch/dirty/rename/delete, secret and read-only
  tests pass.
- CLI, MCP, API, WebSocket, Control Center, Python, web and npm release gates pass.
- Canonical and npm-shipped documentation matches actual behavior.
