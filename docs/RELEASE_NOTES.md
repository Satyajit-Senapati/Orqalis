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

## Dashboard visual refresh - 2026-09-11

The approved 1.0.0 dashboard refresh gives Mission Control a Pitch-inspired primary dark
identity: deep navy/purple surfaces, layered magenta/violet/cyan light, semantic status
colors and distinct Orchestrator/agent/task accents. Text, icons and shapes preserve
meaning without color. Subtle live motion may emphasize persisted state transitions and
active work; reduced-motion preferences remove nonessential movement.

This is a presentation change. Progress, timing, task state, acceptance and activity still
come from persisted Core telemetry, and the browser does not gain orchestration logic.
Pitch-dark is the only available UI theme. The local Home dashboard now exposes registered
projects, project-filtered run history, an overflow-safe desktop sidebar, and a complete
mobile navigation drawer. The root README presents nine real application
views captured from deterministic persisted integration runs.

Verification passed: 127 Python tests at 85% coverage against PostgreSQL and the Docker
sandbox, with one upstream Starlette/AnyIO deprecation warning; 28 frontend tests plus
lint and production build; and 11 strict Playwright tests with 0 skipped across the
documented responsive and reduced-motion coverage. The build emits four JavaScript chunks
of 221.85, 173.14, 75.13 and 54.98 kB.

All nine 1600 x 1180 JPEGs were captured from persisted fixtures with zero browser
diagnostics. Capture publication is atomic, and a forced failed capture preserved every
existing asset hash. No migration was added.

The first hosted Ubuntu check exposed an owner-only workspace permissions failure in the
hardened Docker sandbox. POSIX launches now use the Orqalis process's effective user and
group IDs, preserving dropped capabilities while keeping bind mounts accessible and output
owned by the caller. The exact Ubuntu reproduction and complete suite pass 123 tests at
84% coverage against PostgreSQL/pgvector and Docker.

All 13 npm launcher tests and package checks passed. The prepared tarball contained
58 entries and no forbidden files. Fresh global-prefix version, cold/cached launch,
JSON, invalid-exit and working-directory isolation checks passed. npm publish --dry-run
passed without upload. Release preparation now rejects stale generated documentation,
skills, wheel source or frontend assets and removes obsolete generated skills.

See [UI behavior hardening evidence](verification/ui-behavior-hardening.json) and the
[original visual refresh evidence](verification/dashboard-visual-refresh.json).

See [implementation status](IMPLEMENTATION_STATUS.md) for phase evidence and
[operation instructions](OPERATIONS.md) for execution policies and recovery.

## Validation scope

Release verification uses deterministic worker fixtures and mocked provider HTTP boundaries;
no live OpenAI or Anthropic credentials were supplied. The Python fixture runs actual tests,
review, failure/repair, documentation, Git commit and local-remote push. React, Android/Gradle
and mixed-repository fixtures exercise language-neutral source contracts and delivery;
they do not substitute for each platform's real build pipeline.

The full suite ran on Windows and Ubuntu with PostgreSQL 17/pgvector and Docker. Strict type
checks cover Windows and Linux branches. GitHub checks on the release commit remain the
authoritative hosted result. Browser tests cover active and completed persisted runs,
responsive layout and reload.

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


## Distribution

Global npm installation is the supported application channel. The npm tarball includes
the existing Python Core/UI, migrations, skills, Compose configuration and documentation.
Node.js 22+ and Python 3.12+ remain required; initial setup uses an isolated runtime.
The wheel is internal to npm. Standalone executable, separate wheel/source and Orqalis
PyPI releases are not maintained. Source development remains available to contributors.
The public registry lookup returned E404, while npm whoami returned ENEEDAUTH. No package
was uploaded; actual publication requires release-owner authentication. See
[ADR 0002](adr/0002-npm-distribution.md).
