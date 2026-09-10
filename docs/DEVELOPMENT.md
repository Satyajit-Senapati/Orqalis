# Developer setup

Orqalis requires Git, Python 3.12+, PostgreSQL with pgvector, and Docker for isolated
commands. Node 24 is needed to build the React Control Center. End users install through
npm as described in [GUIDE.md](../GUIDE.md); this source setup is for contributors and SDK
development. The internal Python wheel is bundled into npm with UI, migrations and skills.

## Contributor environment

~~~sh
npm ci --prefix web
npm run build --prefix web
uv sync --frozen
docker compose up -d --wait
uv run orqalis migrate
uv run orqalis doctor
uv run orqalis ui --open
~~~

On Windows, use npm.cmd if PowerShell blocks npm.ps1. This checkout also contains an
ignored local uv/Python installation under .tools and .venv/Scripts. Normal installations
can use uv on PATH. See [OPERATIONS.md](OPERATIONS.md) for task execution and recovery.

Compose binds PostgreSQL to loopback. Its development credentials are orqalis/orqalis.
Override ORQALIS_POSTGRES_PASSWORD and ORQALIS_DATABASE_URL together if changing them.
The database URL uses postgresql+psycopg://user:password@host:port/database.
Settings read ORQALIS_ environment variables; repository .env files are not loaded.

## Configure a provider and permissions

Set ORQALIS_OPENAI_MODEL and ORQALIS_OPENAI_API_KEY for OpenAI, or
ORQALIS_ANTHROPIC_MODEL and ORQALIS_ANTHROPIC_API_KEY for Anthropic. Models are explicit;
Orqalis does not assume current model names or prices. No credentials are required for
the local UI, structured memory, supplied contracts, or deterministic test providers.

Execution requires an explicit [execution policy](examples/execution-policy.json):
allowed write paths, exact command argv, timeout and an already-built sandbox image.
Include the documentation destination in allowed write paths when using repository docs.
The [delivery policy](examples/delivery-policy.json) controls documentation, sensitive
configuration approvals and optional push. ProjectSettings.allow_push must also be true;
SDK initialization accepts ProjectSettings. The default project prohibits push.

Docker uses a read-only root, no network, dropped capabilities and CPU/memory/process
limits. Build a project-specific image with its test dependencies in advance. Images are
never pulled automatically. Reviewer commands also mount the workspace read-only.
trusted_local is an explicit host-command fallback; it does not isolate executed code.

Skills are discovered from packaged and explicitly configured ORQALIS_SKILL_ROOTS
(JSON array of trusted directories). Metadata declares capabilities and permitted tools;
instructions load on selection, with versions/content hashes pinned in invocation records.
Project/role/skill/tool permissions intersect. Provider responses cannot expand them.

## Quality checks

~~~sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
npm run lint --prefix web
npm test --prefix web
npm run build --prefix web
uv build --wheel --out-dir .tools/release
~~~

Build the UI before the internal wheel. The wheel under .tools/release is consumed by
[the npm packaging workflow](PUBLISHING.md), not published separately. The npm workflow
owns artifact building and platform installation checks; Core CI focuses on runtime/UI
regressions. No standalone executable, source archive or PyPI release is maintained.

For integration tests, create a disposable database:

~~~sh
docker compose exec -T postgres createdb -U orqalis orqalis_test
~~~

Set ORQALIS_TEST_DATABASE_URL to
postgresql+psycopg://orqalis:orqalis@127.0.0.1:5432/orqalis_test, and
ORQALIS_TEST_SANDBOX_IMAGE to pgvector/pgvector:pg17 (already pulled by Compose).
Run uv run pytest --cov=orqalis. On PowerShell use $env:VARIABLE='value'.

The suite downgrades/rebuilds the disposable database. Never use a database containing
retained work, or run concurrent pytest processes against that database. Without configured
services, the corresponding tests explicitly skip. CI provisions both and runs all tests.

Fixtures cover Python execution/repair, React source changes, Android/Gradle source
changes, mixed repositories, independent scope rejection, safe local-remote push,
cross-client MCP continuation, failure injection and incremental memory. React/Gradle
fixtures validate source contracts; they do not claim a full platform SDK build.
The 500-file performance fixture verifies zero source reads on unchanged HEAD and exactly
one changed-source read for an incremental update.

## Browser verification

~~~sh
uv run python -m tests.e2e.seed_runtime
uv run python -m tests.e2e.seed_execution
uv run orqalis ui
~~~

Set ORQALIS_E2E_RUN_ID from .tools/ui-fixture.json and ORQALIS_E2E_COMPLETED_RUN_ID
from .tools/ui-completed.json. Run npx playwright test in web/.
ORQALIS_UI_URL selects another loopback URL. The default browser is installed Chrome;
set ORQALIS_BROWSER_CHANNEL=chromium and install Playwright Chromium for CI.
See [Playwright CI guidance](https://playwright.dev/docs/ci).

The fixtures create real persisted active and completed runs. Browser checks inspect
actors, DAG, timeline, evidence, Project Brain, delivery diff, metrics, theme persistence,
responsive layout and reload/reconnection. The UI obtains all statistics from Core.

## Architecture and migrations

Domain contracts do not import interfaces, persistence or provider SDKs. Application
services own transactions; repository adapters flush without committing. The SDK is the
composition root shared by CLI, REST/WebSocket and project-scoped stdio MCP.

Use uv run alembic revision --autogenerate -m "description" for a schema change.
Inspect the revision and test clean upgrade/downgrade/re-upgrade before delivery. Historical
migrations contain their schema explicitly and never import live create_all models.
The append-only event stream and canonical workflow tables share transaction boundaries.

Project Memory indexes committed sources and stores provenance, confidence, freshness,
supersession and originating runs. Unchanged HEAD skips broad inspection. Changed files
are refreshed selectively. Dirty files become inspection targets, not committed facts.
The graph currently connects files and directories; richer inferred semantic edges are
future work. Optional EmbeddingProvider adapters enable model-scoped pgvector retrieval;
structured search remains usable without one.

Goal versions are immutable. Criteria require executable or verifiable source evidence.
Manual criteria are never automatically passed. Final delivery rechecks the complete
accepted tree after documentation. An independent deterministic Change Guardian evaluates
scope, secrets, sensitive configuration, test reduction and final-tree integrity.

OpenTelemetry records operation names, outcome and duration without prompts, commands,
returned content or exception text. ORQALIS_TELEMETRY_CONSOLE=true enables stderr export.
Applications may configure standard OpenTelemetry exporters instead. Runtime events include
trace IDs when available. Logs exclude private reasoning and redact credential patterns.

See [ADR 0001](adr/0001-runtime-implementation.md),
[implementation status](IMPLEMENTATION_STATUS.md), and [MCP setup](MCP.md).

## Provider interoperability

OpenAI uses the Responses API and Anthropic uses Messages. Both use the same typed
task/skill/tool/acceptance contract and validate original JSON schemas locally.
Provider output limits, timeouts, refusals, errors and usage are normalized. Private
thinking/signature blocks are discarded. Costs remain unknown without a configured source.

The Anthropic adapter adapts unsupported grammar constraints for transport while retaining
the unchanged local schema. See the [Messages API](https://platform.claude.com/docs/en/api/messages/create)
and [structured output contract](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

ExternalCLIProvider defines a bounded host-owned CLITransport contract. An arbitrary CLI
launcher is not enabled. Native Codex, Claude Code and Copilot use the tested MCP boundary.
No remote HTTP/MCP mode is enabled; authentication is required before adding one.

## Dashboard enhancement and media

See [DASHBOARD.md](DASHBOARD.md) for navigation, the brownfield audit, new read-only
contracts, attribution boundaries and display limits. The existing orchestrator and
CLI remain authoritative. No migration is required for this enhancement.

Create real persisted screenshots using deterministic providers:

~~~sh
uv run python -m tests.e2e.seed_runtime
uv run python -m tests.e2e.seed_execution
~~~

Then run the execution fixture once with ORQALIS_QA_REPAIR=1 to create a failed-review
and successful-repair history (on PowerShell: $env:ORQALIS_QA_REPAIR='1').
Clear that environment variable after the repair fixture.

~~~sh
uv run orqalis ui
node web/scripts/capture-dashboard.mjs
~~~

The capture script reads .tools/ui-fixture.json, .tools/ui-completed.json and
.tools/ui-repair.json, and writes eight optimized JPEGs to docs/assets.
ORQALIS_UI_URL can target a different loopback instance. Installed Chrome is the default;
ORQALIS_BROWSER_CHANNEL=chromium selects Playwright Chromium. These are test-provider
runs through real Core services, not mock production data.

Frontend checks now include bounded reconnect buffers, event filters, task relationships,
retry counts, graph/inspector behavior, focus restoration, four viewport widths, reduced
motion, empty/error states and a forced socket disconnect. Activity filters use explicit
accessible names. The original browser contracts continue to run.

For formatting the new UI files, the repository's npm tooling provides Prettier after
npm ci --prefix packages/npm. Runtime source remains TypeScript; release scripts remain
strictly typed Python. Keep the source files and screenshot capture script together when
updating product documentation.
