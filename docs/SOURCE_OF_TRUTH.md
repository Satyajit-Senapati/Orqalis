# Orqalis source of truth

Revised 2026-09-16 for the local-first persistence architecture.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

## Authority order

When documents conflict, use this order:

1. `SIGNOFF.md` and accepted ADRs;
2. this file;
3. `docs/01-system-architecture.md` and `docs/07-data-model-and-observability.md`;
4. `docs/IMPLEMENTATION_STATUS.md` for the completed migration sequence;
5. interface and operation guides;
6. dated implementation/release evidence for the version it records.

ADR 0003 supersedes the persistence portion of ADR 0001. Database-first statements in
1.0.0/1.0.1 release records and historical readiness matrices describe those releases;
they do not define current standard setup.

## Documentation map

- [Product design and roadmap](00-product-design.md) defines the product scope and
  dated roadmap; [SIGNOFF](../SIGNOFF.md) and [ADRs](adr/) record approved decisions.
- [System architecture](01-system-architecture.md), [workflow](04-workflow-and-acceptance.md),
  [memory](03-project-memory.md), [interfaces](05-interfaces-and-integrations.md),
  [security](06-security-git-and-governance.md), and the
  [Control Center](10-local-control-center.md) explain the current design.
- [Operations](OPERATIONS.md), [development](DEVELOPMENT.md), [MCP](MCP.md), and
  [publishing](PUBLISHING.md) are task guides. [Release notes](RELEASE_NOTES.md)
  distinguish shipped versions from unreleased work.
- [Open-source review](OPEN_SOURCE_REVIEW.md) summarizes choices;
  [enhancement status](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md) tracks acceptance and links
  the detailed research. [Benchmarks](https://github.com/Satyajit-Senapati/Orqalis/blob/main/benchmarks/README.md) hold the measurement
  method; raw reports remain under `quality/evidence/`.

## Product invariants

- The Orchestrator owns state transitions; providers remain replaceable workers.
- Goals are versioned and acceptance/evidence gates completion.
- Planning uses dependency-aware DAGs and bounded repair/convergence.
- Change Guardian protects validated work before delivery.
- Each project root owns an isolated `.orqalis/` store.
- Repository Graph, Curated Project Memory and Task History remain separate concepts.
- Important writes are atomic, locked where shared and schema-versioned.
- Secrets and hidden reasoning are not durable project memory.
- CLI, MCP and the Control Center use application services rather than raw file mutation.

## Data authority

Canonical data is project configuration, curated memory, Task Capsules, acceptance
evidence, durable decisions and final delivery records. Derived/rebuildable data is parser
cache, search/index material, graph presentation, ranking cache and reproducible context
projection. Deleting derived data must never erase project history.

The Task Capsule snapshot is authoritative current execution state. Its JSONL stream is
structured operational history. Human-readable stage files are projections created only
when their stage exists. No provider conversation, browser state, cache or index becomes a
competing authority.

## Interfaces and isolation

Root resolution is explicit root, `ORQALIS_PROJECT_ROOT`, Git root, then current working
directory. A service graph is bound once and cannot silently redirect to another project.
MCP uses high-level project/task/memory/graph operations. React uses FastAPI and WebSocket;
it never reads `.orqalis`.

## Distribution decision

The npm package remains a supported launcher/distribution. Its installation bundles the
Python runtime and web assets without a database container. Docker is optional sandbox
infrastructure. No database compatibility extra or exporter command is shipped.

## Success condition

A clean clone can initialize, execute, stop, resume and inspect project knowledge on a
machine with no database server. A second assistant can continue from `.orqalis` without
the first assistant's conversation. One-file changes avoid full repository reparsing,
derived data can be regenerated, and simultaneous Project A/Project B use cannot leak data.


## Post-2.0.0 lifecycle and syntax projections

`memory/lifecycle.json` is canonical reviewed supersession state and must be preserved with
memory records. Parser caches, graph/query results, source spans, ranking explanations and
trace projections are derived; rebuilding them must not create or rewrite approved facts.
`runtime/sandboxes/` holds machine-local execution ownership receipts needed for safe
recovery and is not a parser cache to purge during active work. Current enhancement decisions
and acceptance evidence are in [the quality audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md).

## Continuing development

Read SIGNOFF and accepted ADRs, this authority map, then the architecture and relevant
interface/storage chapter. The completed migration phases and historical checks live in
[implementation status](IMPLEMENTATION_STATUS.md); current work belongs in
[the release worklist](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/NEXT_SESSION.md), with acceptance criteria and findings
in its linked quality documents. The former migration plan and architecture handoff
have been consolidated into these existing documents.

Preserve user changes, resolve one project root for the lifetime of each service graph,
and keep canonical writes atomic, schema-validated and recoverable. Acceptance requires
criterion-linked evidence; repairs stay bounded; unknown side effects are not replayed
blindly. Provider conversations and projections never become data authority. Run focused
checks for a coherent change, then the applicable release gates. Preserve raw failed and
successful evidence with its original source identity and scope.
