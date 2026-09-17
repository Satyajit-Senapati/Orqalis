# Developer setup

Orqalis standard development requires Git, Python 3.12+, `uv`, Node.js 22+ and npm. It
does not require PostgreSQL, pgvector, Docker or `DATABASE_URL`.

## Install

```bash
uv sync --group dev
npm ci --prefix web
npm ci --prefix packages/npm
```

Initialize a disposable fixture repository or this checkout:

```bash
uv run orqalis init
uv run orqalis status
uv run orqalis doctor
```

The active root owns `.orqalis/`. Use `--root` where supported or set
`ORQALIS_PROJECT_ROOT` when a process cannot inherit the intended working directory. Never
point two unrelated fixtures at the same store.

Provider credentials are optional for storage and retrieval tests. When needed, configure
them through environment variables, user-level configuration, keychain or the provider
adapter. Do not put credentials in `.orqalis/` memory or fixtures.

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
npm run lint --prefix web
npm run test --prefix web
npm run build --prefix web
npm run check --prefix packages/npm
npm test --prefix packages/npm
```

Use focused tests while developing, then run the full standard gates. Filesystem tests use
temporary Git repositories and must cover root isolation, atomic writes, locks, restart,
schema errors, cache/index deletion, dirty state, branch changes, rename/delete and secret
rejection. Tests must not inspect or mutate the developer's real `.orqalis/` directory.

## Store and schema development

The domain and application layers depend on storage-neutral protocols. Standard adapters
live under `orqalis.persistence.filesystem`; graph, indexing, memory and context services
are root-bound. Keep SQLAlchemy sessions, database IDs and PostgreSQL types out of domain
models.

Filesystem schema changes require:

1. old-schema validation;
2. backup of affected files;
3. deterministic transformation;
4. new-schema validation;
5. atomic file replacement; and
6. manifest version update last.

Add migration tests for success, interruption, malformed input and unsupported future
versions. Index/cache format changes should prefer deletion and regeneration; never migrate
derived content as if it were canonical.

## Optional sandbox suite

Docker is optional for the isolated-command sandbox integration test. It is not used as a
storage prerequisite. The default suite collects this test and reports it as skipped when
`ORQALIS_TEST_SANDBOX_IMAGE` is unset. Set that variable to an already-pulled image when
validating the container boundary explicitly:

```bash
python -m pytest tests/integration/test_sandbox.py
```

The current source has no SQL compatibility suite or database exporter. Use historical
tags only when inspecting legacy schemas; do not reintroduce database imports into the
normal runtime.

## Control Center development

FastAPI is the only browser gateway to project state. The web application must not read
`.orqalis` directly. Exercise initial snapshot loading, persisted-event replay, live
WebSocket subscription, reconnection and historical Task Capsule rendering.

Screenshots and other visual evidence belong in the documented evidence location, not in
curated memory. Keep generated web assets and parser/index caches out of canonical data.

To regenerate the documented dashboard screenshots, create the active, completed and repair
fixtures against the same disposable repository, then run the UI bound to the repository
recorded in `.tools/ui-fixture.json`:

```bash
uv run python -m tests.e2e.seed_runtime
uv run python -m tests.e2e.seed_execution
ORQALIS_QA_REPAIR=1 uv run python -m tests.e2e.seed_execution
# In another terminal, set ORQALIS_PROJECT_ROOT to the `repo` value in
# .tools/ui-fixture.json and run: uv run orqalis ui
npm run capture:docs --prefix web
```

The capture command stages and validates all nine images before atomically replacing
`docs/assets/`; a failed capture leaves the prior image set intact.

## Pull-request checklist

- Behavior is covered at the service boundary and through the relevant interface.
- Project-relative paths and explicit root checks prevent cross-project access.
- Structured writes are atomic and secret-safe.
- Canonical versus derived ownership is unambiguous.
- New CLI/MCP/API surfaces are documented only after they exist.
- Shipped npm documentation is regenerated or patched with the canonical source.
- Standard checks pass without database or Docker services.
