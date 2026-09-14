# Publishing Orqalis

Orqalis 1.0.0 is MIT licensed. The Python Core remains authoritative; the npm package
is a distribution launcher for that same Core. The private package in web/ is only the UI.

This repository prepares release artifacts locally and is connected to
[Satyajit-Senapati/Orqalis](https://github.com/Satyajit-Senapati/Orqalis). It has not
published Orqalis to npm, and no npm publishing identity or package-name ownership has
been verified. npm is the sole application release channel; see
[ADR 0002](adr/0002-npm-distribution.md).

## What users install

After the first npm release:

```sh
npm install -g orqalis
orqalis --version
orqalis --help
```

Requirements: Node.js 22+, Python 3.12+ with venv/pip, and internet for first-launch
dependency installation. Git, PostgreSQL/pgvector, Docker and provider configuration
are required for the corresponding application features; see [README.md](../README.md).

The tarball contains a version-matched wheel (including UI, migrations and skills),
hash-locked requirements exported from uv.lock, MIT license, combined README usage guide, supporting docs and
compose.yaml for source-free local PostgreSQL setup.
It does not depend on a separately published Python package named orqalis. There are
no production npm dependencies or install lifecycle scripts.

The launcher verifies bundled hashes and sets up a per-user virtual environment.
Python dependencies use exact versions, SHA-256 hashes and binary wheels. No source
build tools run during installation. A platform without compatible dependency wheels
fails setup with diagnostics; test supported platforms before release.
First setup uses PyPI with pip's isolated configuration; project pip settings and
PIP_* overrides are intentionally ignored.

Commands use the existing Python CLI with isolated module imports. Arguments, working
directory, environment, stdin/stdout and exit codes are forwarded. Setup uses stderr.
Concurrent first launches share a setup lock; failed setup cannot mark the runtime ready.
A terminated setup may leave a lock, with manual recovery described in the npm README.

## Prepare artifacts

Use Node.js 24, Python 3.12+ and uv in the repository root. Windows PowerShell users
should use npm.cmd where npm.ps1 is blocked.

```sh
uv sync --frozen
npm ci --prefix web
npm ci --prefix packages/npm
npm run lint --prefix web
npm test --prefix web
npm run build --prefix web
npm run check --prefix packages/npm
npm run lint --prefix packages/npm
npm run format:check --prefix packages/npm
npm test --prefix packages/npm
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy --strict scripts
uv build --wheel --out-dir .tools/release
uv run python scripts/prepare_npm.py
npm pack ./packages/npm --pack-destination dist
```

Use --uv /absolute/path/to/uv if it is not on PATH. Build the UI before the wheel;
the UI build also collects production dependency license notices. The preparation
script rejects mismatched versions/licenses and missing UI, migrations or license files.
The npm prepack check rejects source/generated inventory or byte mismatches, stale wheel or UI assets, symlinks, missing files and unexpected vendor artifacts.
Preparation also creates the ignored dist output directory, so npm pack works from a
clean checkout.

Public application artifact: dist/orqalis-1.0.0.tgz.

The internal .tools/release/orqalis-1.0.0-py3-none-any.whl is copied to vendor/ during
preparation. It is not a separate install/release channel. No source archive, native
installer or Orqalis PyPI publication is part of this workflow.

The prepack manifest binds the exact Python source inventory, build inputs and UI hashes.
Changes after preparation require rebuilding and preparing again. Maintainer-only
`NPM_RELEASE_READINESS.md` and its JSON verification record stay in Git and are excluded
from npm. Current results and the exact reviewed artifact digest are recorded in the
[release audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/NPM_RELEASE_READINESS.md).

## Test a clean installation outside the repository

Use a fresh OS temporary directory and an isolated global prefix; this leaves your
existing global installation untouched. Run these commands from the repository root.

PowerShell:

```powershell
$auditRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('orqalis-release-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $auditRoot | Out-Null
$prefix = Join-Path $auditRoot 'prefix'
$runtime = Join-Path $auditRoot 'runtime'
$env:ORQALIS_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
$env:ORQALIS_RUNTIME_HOME = $runtime
npm.cmd install -g --prefix $prefix ./dist/orqalis-1.0.0.tgz --ignore-scripts --no-audit --no-fund
uv run python scripts/smoke_npm.py --prefix $prefix --runtime $runtime
& (Join-Path $prefix 'orqalis.cmd') --version
```

Linux/macOS:

```sh
audit_root="$(mktemp -d -t orqalis-release.XXXXXX)"
export ORQALIS_PYTHON="$(pwd)/.venv/bin/python"
export ORQALIS_RUNTIME_HOME="$audit_root/runtime"
npm install -g --prefix "$audit_root/prefix" ./dist/orqalis-1.0.0.tgz --ignore-scripts --no-audit --no-fund
uv run python scripts/smoke_npm.py --prefix "$audit_root/prefix" --runtime "$ORQALIS_RUNTIME_HOME"
"$audit_root/prefix/bin/orqalis" --version
```

The smoke script executes the global shim from an unrelated directory. It checks cold
and cached launch, version/help, parseable JSON, invalid-command status and hostile
current-directory module isolation. It needs no database or provider credentials.

For packaged Core, MCP, API and UI verification, configure `ORQALIS_TEST_DATABASE_URL`
to a **disposable** PostgreSQL/pgvector database. Then run:

```powershell
uv run python scripts/verify_installed.py --prefix $prefix --runtime $runtime --workspace $auditRoot --output .tools/installed-release.json
```

On Linux/macOS use `$audit_root/prefix`, `$ORQALIS_RUNTIME_HOME` and `$audit_root` for those
three paths and install `lsof`. This harness migrates the disposable database, creates
its own committed project, exercises init/status/memory/context/goals/catalogs and actual
MCP stdio, cold-starts the packaged UI from a hostile current directory, verifies assets,
direct routes, API and WebSocket reconnection, and stops only its verified UI listener.
It removes its project fixture; the caller owns the database, prefix and runtime cleanup.
Verify each absolute temporary target before deleting it.

The package workflow builds once and tests the same tarball on Windows, Linux and macOS.
Its Linux installed-integration job exercises Core/MCP/UI against PostgreSQL. Hosted
results must pass before claiming those platforms are validated; the smoke report records
actual Node platform and architecture. No separate native binaries are shipped. Runtime
support also requires compatible binary Python dependency wheels.

Run the full PostgreSQL/Docker backend and persisted browser suites described in
[DEVELOPMENT.md](DEVELOPMENT.md). Basic packaging checks do not replace them.

## Release review and first publication

1. Inspect the source diff, test evidence and tarball file list. Check versions in
   pyproject.toml, src/orqalis/__init__.py, web/package.json and packages/npm/package.json.
   Refresh lockfiles when changing version or dependencies.
2. Confirm the MIT copyright attribution. Frontend third-party notices are included
   in the wheel; installed Python dependencies retain their own distribution licenses.
3. Confirm the repository, homepage and issue URLs in package metadata still point to
   the intended release repository.
4. Confirm registry ownership and availability using npm whoami and npm view orqalis.
   An E404 availability check does not reserve the name. If unavailable, use a scoped
   package such as @your-org/orqalis; its bin command can still be orqalis.
5. Commit the reviewed source and record its commit ID with release validation.
6. Inspect the exact prepared tarball with a dry run:

```sh
npm publish ./dist/orqalis-1.0.0.tgz --dry-run --access public --registry=https://registry.npmjs.org/
```

After the release owner approves public publication and signs into the intended account:

```sh
npm login --registry=https://registry.npmjs.org/
npm whoami --registry=https://registry.npmjs.org/
npm publish ./dist/orqalis-1.0.0.tgz --access public --registry=https://registry.npmjs.org/
npm view orqalis@1.0.0 version dist.integrity --registry=https://registry.npmjs.org/
```

Publish the reviewed tarball, not an unreviewed rebuild. Public publication distributes
that version permanently; use a new version for corrections. Follow npm's current
account and two-factor authentication requirements. No token belongs in this repository.
For subsequent automation, configure npm trusted publishing against the actual repository
and approved release workflow. The included workflow only builds/tests/uploads artifacts;
it never publishes.

Python SDK development uses the contributor environment. Do not add a second public
installer or publish the internal wheel independently; changes to this distribution
decision require an explicit design amendment.

## Upgrade, rollback and provenance

Keep a release record containing source commit, tool versions, test results and SHA-256
digest of the reviewed npm tarball. npm also records tarball integrity. The embedded manifest
binds the npm runtime to its wheel and dependency lock.

Each bundle uses a distinct cache directory. Updating npm does not migrate PostgreSQL.
Back up the database and run the new release's migrations explicitly. Installing an older
npm version selects its runtime but does not reverse database schema changes; follow the
documented database restore/compatibility procedure before rollback.

The canonical distribution amendment records npm as the installation channel. Runtime
architecture and phase order are unchanged; no migration accompanies this consolidation.

References: [npm package metadata](https://docs.npmjs.com/cli/v12/configuring-npm/package-json/),
[publishing public packages](https://docs.npmjs.com/creating-and-publishing-unscoped-public-packages/),
[trusted publishing](https://docs.npmjs.com/trusted-publishers/).
