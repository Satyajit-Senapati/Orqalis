# Orqalis source of truth

Revised 2026-09-16 for the local-first persistence architecture.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

## Authority order

When documents conflict, use this order:

1. `SIGNOFF.md` and accepted ADRs;
2. this file;
3. `docs/01-system-architecture.md` and `docs/07-data-model-and-observability.md`;
4. `docs/09-implementation-plan.md` and `CODEX_HANDOFF.md`;
5. interface and operation guides;
6. dated implementation/release evidence for the version it records.

ADR 0003 supersedes the persistence portion of ADR 0001. Database-first statements in
1.0.0/1.0.1 release records and historical readiness matrices describe those releases;
they do not define current standard setup.

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
