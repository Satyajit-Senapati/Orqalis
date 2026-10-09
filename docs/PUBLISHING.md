# Publishing Orqalis

This guide describes the current local-first npm release. PostgreSQL/pgvector, Docker and
database environment variables are not standard build, installation or verification
requirements.

**`orqalis@2.1.0` was published as npm's `latest` on 2026-10-09.**
[GitHub v2.1.0](https://github.com/Satyajit-Senapati/Orqalis/releases/tag/v2.1.0) points to
`19865786a0280e6875902fe2d4dbe9d02975cc23`. Exact-source quality, three-platform package smoke, Linux installed
integration, release-owner review, OIDC provenance and public artifact identity are
recorded in the [publication receipt](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/evidence/release-publication-closeout-2.1.0-20261009-v1.json).
The cold graph-rebuild tradeoff was explicitly accepted for this release.
Published versions, tags and artifacts are immutable. The gates below apply to future
releases; recheck version availability immediately before publication. This guide
does not itself authorize a release. Public 1.0.x remains historical database-backed
software; earlier registry observations retain their original dates.

## Public artifact

The supported public artifact is the `orqalis` npm tarball. It contains the Node launcher,
hash-verified bundled Python application and bootstrap-pip wheels, compiled web assets, skills, license and user
documentation. It does not ship a database Compose stack. The Python wheel is an internal
npm payload, not a separately supported PyPI release.

Node.js 22+ and Python 3.12+ remain prerequisites. At first use the launcher builds an
isolated per-user runtime. Each working repository owns its durable `.orqalis/` data; the
runtime cache is never project history. Before contacting a package index, the launcher
installs the exact locked pip 26.2.1 wheel from the verified tarball with `--no-index`
and `--no-deps`. Pip configuration files are disabled with Python's null-device sentinel.
It then installs hash-locked binary dependencies and the application wheel. The bootstrap
pin is an installer dependency group, not a new application dependency or service.
Installed-runtime advisory checks include pip; auditing only the development environment
does not cover this bootstrap boundary.

## Prepare the artifact

From a clean reviewed checkout:

```bash
uv sync --group dev
npm ci --prefix web
npm ci --prefix packages/npm
npm run build --prefix web
uv build --wheel --out-dir .tools/release
uv run python scripts/prepare_npm.py
```

`prepare_npm.py` refreshes npm-shipped documentation and assets from the canonical tree and
copies the reviewed wheel. Maintainer-only `docs/quality/` research, audit captures and
release-readiness files stay in the repository; user guides link to their repository
locations. This prevents local machine paths and growing audit data entering installs.
Review its diff. In particular, confirm that no database
Compose/config file, credential, `.orqalis/` project data, local evidence or transient
cache entered the package.

## Standard release gates

The commands below are the standard checks. The 2.1.0 qualification is recorded in the
[acceptance checklist](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/NPM_RELEASE_READINESS.md#candidate-210---local-preparation-on-2026-10-03),
including comparative contracts, installed verification, benchmarks, two complete rounds
and independent review.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy --strict scripts
uv run pytest
npm run lint --prefix web
npm run test --prefix web
npm run build --prefix web
npm run check --prefix packages/npm
npm run lint --prefix packages/npm
npm run format:check --prefix packages/npm
npm test --prefix packages/npm
```

These commands run without `DATABASE_URL`, a PostgreSQL service or Docker. The Docker
sandbox integration test is a separate opt-in check and does not gate standard startup.

## Pack and inspect

```bash
npm pack ./packages/npm --dry-run
npm pack ./packages/npm --pack-destination dist
```

Inspect the exact tarball contents and hashes before publishing. Verify at least:

- launcher/runtime code and supported platform shims;
- bundled wheel and its integrity metadata;
- compiled Control Center assets;
- bundled skills, current docs, ADR 0003 and sign-off amendment;
- absence of source-checkout paths, secrets, project `.orqalis/` directories, database
  credentials and Compose/database bootstrap artifacts.

Run the repository's npm smoke/install scripts against the tarball in a temporary directory.
The installed verification must initialize an independent temporary Git repository, create
its `.orqalis/`, run status/doctor and exercise CLI/MCP/API/UI surfaces supported by the
release. Test two roots where practical. Do not point artifact tests at the Orqalis checkout.

## Trusted Publishing setup

Publication uses the existing `npm-package.yml` GitHub Actions workflow and npm Trusted
Publishing. It does not use a repository npm token. Before the first release, the package
owner must create these two matching external controls:

1. Create the protected GitHub environment `npm-release` and require release-owner review.
2. Configure the `orqalis` npm Trusted Publisher for GitHub repository
   `Satyajit-Senapati/Orqalis`, workflow filename `npm-package.yml`, environment
   `npm-release`, and direct publish permission.

With npm 12, the package owner can inspect or create that relationship after interactive
login and two-factor authentication:

```bash
npm whoami
npm trust list orqalis
npm trust github orqalis \
  --file npm-package.yml \
  --repository Satyajit-Senapati/Orqalis \
  --environment npm-release \
  --allow-publish
```

The expected npm owner is `satyajit-pro`. The workflow grants `id-token: write` only to the
publish job, uses a GitHub-hosted runner and pins npm 12.0.2. The environment name and
workflow filename are security identities and must match npm exactly.

## Publication

Publishing is a separate, explicit release-owner action. A branch push, pull request, tag
push or ordinary manual package run cannot publish. The publish job runs only when all of
the following are true:

- the workflow was started with `workflow_dispatch`;
- the `publish` boolean input is `true`;
- the selected ref is a `v` tag;
- package construction, all platform smokes and installed integration passed; and
- the protected `npm-release` environment was approved.

Require the separate `ci.yml` quality workflow to pass on the exact committed LF revision
before tagging or publication. The package publish job depends on smoke and installed
integration; it does not automatically wait for that separate quality workflow.

After the selected release version and commit have passed hosted CI, create its new annotated
version tag. Never move or recreate `v2.0.0`. Confirm the selected version is still unused,
then run `npm-package.yml` from GitHub Actions against that exact new tag, with the publish
input enabled. GitHub CLI is optional; the repository's Actions interface supports this
workflow without it.

Review and approve the `npm-release` environment deployment. The workflow rebuilds the npm
artifact from the tag, runs its complete package, platform and installed-application gates,
verifies that exactly one tarball exists and its embedded name/version match `orqalis` and
the selected tag, then publishes that exact tested tarball through OIDC with provenance.
There is no local `npm publish` fallback in the standard release path.

Do not republish or replace any existing version, including 1.0.1 and 2.0.0, and do not dispatch `publish=true` as part of a
verification or cleanup task.

Record registry version/integrity, source commit, wheel and tarball hashes, platform jobs,
test totals and any permitted limitations. A local build alone is not proof of publication.

## Updates and rollback

`orqalis update` uses npm in the existing global prefix. Updating the launcher/runtime does
not silently migrate or delete repository `.orqalis/` data. On first open, supported
filesystem migrations back up affected canonical files, validate old/new schemas and update
the manifest last.

Rollback the launcher with npm only to a version that supports the project's filesystem
schema. Never solve a package rollback by deleting Task Capsules or memory. Cache/index may
be regenerated; canonical project data must be backed up before a schema-changing release.

Uninstall removes the launcher, not repositories. Per-user runtime caches may be removed
explicitly after stopping processes; avoid broad recursive cleanup.

## Historical database compatibility

The current wheel must not contain SQLAlchemy, Alembic, psycopg, pgvector, legacy migration
modules or database environment settings. No PostgreSQL-to-filesystem exporter command is
implemented. Historical data work must use a matching archived release or external tooling,
never dependencies smuggled back into the current package.

Historical readiness matrices and 1.0.x release reports remain valid evidence for those
artifacts. They are not the current local-first release gate.
