# Orqalis 1.0.0

This local V1 implementation follows the canonical v1.2 architecture and phase plan.
The architecture version and software release version are separate identifiers.

## Delivered

- Shared Python SDK, CLI, loopback REST/WebSocket API, project-scoped stdio MCP and React Control Center.
- PostgreSQL migrations, deterministic workflow/DAG scheduling, durable events, actor sessions, timing and explicit recovery.
- Versioned requirements and evidence-backed acceptance, scoped execution, targeted repair, independent Change Guardian, documentation and gated Git delivery.
- Git-aware Project Memory, source provenance, selective refresh and accepted-run curation.
- OpenAI and Anthropic adapters, dynamic skills and Codex/Claude/Copilot MCP configuration.
- DAG, timeline, acceptance, Project Brain, diffs, delivery receipts, actor metrics and historical comparison.
- Docker limits, process-tree cleanup, cancellation, redaction and optional OpenTelemetry export.

See [implementation status](IMPLEMENTATION_STATUS.md) for phase evidence and
[operation instructions](OPERATIONS.md) for execution policies and recovery.

## Validation scope

Release verification uses deterministic worker fixtures and mocked provider HTTP boundaries;
no live OpenAI or Anthropic credentials were supplied. The Python fixture runs actual tests,
review, failure/repair, documentation, Git commit and local-remote push. React, Android/Gradle
and mixed-repository fixtures exercise language-neutral source contracts and delivery;
they do not substitute for each platform's real build pipeline.

The full suite ran on Windows with PostgreSQL 17/pgvector and Docker. Strict type checks
cover Windows and Linux branches. Linux CI is configured, but a hosted CI run is not claimed.
Browser tests cover active and completed persisted runs, responsive layout and reload.

## Operational limits

- V1 is local only. Remote UI/MCP hosting and authentication are not enabled.
- Embeddings are optional through an adapter; structured search works without credentials.
- External CLI execution is a host transport contract. Native coding assistants use MCP.
- Unknown provider token/cost values remain unreported; the UI does not estimate them.
- Manual criteria never receive automatic PASS. Unverifiable criteria require explicit human
  handling or an authorized goal revision to a verifiable contract.
- Workspace writers are serialized. Independent context tasks can run concurrently under
  the configured capacity; the default planner generates a developer/test/reviewer slice.
- Interrupted operations with uncertain side effects need explicit recovery acknowledgment.
- One upstream Starlette/AnyIO deprecation warning remains; no application failure is hidden.

The supplied signed-off documents remain the source of truth. Future work should extend
these services and contracts rather than create another workflow engine.
