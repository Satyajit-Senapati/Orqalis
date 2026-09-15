# Publishing Orqalis

Orqalis is MIT licensed. The Python Core remains authoritative; the npm package
is a distribution launcher for that same Core. The private package in web/ is only the UI.

[Orqalis 1.0.1](https://www.npmjs.com/package/orqalis/v/1.0.1) is the current public
npm release. Published versions are immutable and their registry integrity is recorded
with the corresponding reviewed artifact. Source and current documentation are maintained in
[Satyajit-Senapati/Orqalis](https://github.com/Satyajit-Senapati/Orqalis). npm is the
sole application release channel; see [ADR 0002](adr/0002-npm-distribution.md).

The 1.0.1 release source is commit `dfd8e31f2d6c84b2df9565bff8f3c1d03cd30c9f`. Its public npm tarball
contains 69 files and has SHA-256 `b0bf31832c40d59c5b03b4e6cfed7f15f6ec9f47983e736b8a008867500c9011`, npm shasum `10d66da1c2a47b4aabcf9be4bad7cc7f7021705e`,
and integrity `sha512-3TNPpq3Eskq6eVsl0BFxYG4Ch5d8bq1wIfEtAApSO6CNLe8YuYEQR0depln7v2Y0mO9hz68A6JcTQ1HX4M/nSA==`. npm published it at `2026-09-15T05:33:58.810Z` and
assigned `latest` to 1.0.1. See [RELEASE_NOTES.md](RELEASE_NOTES.md#publication-record)
for installation and CI verification.

## What users install

Install the public package from any directory:

```sh
npm install -g orqalis
orqalis --version
orqalis --help
```

No npm account, login or manual virtual-environment activation is needed to install
the public package. Installation registers no Windows service, scheduled task or autostart
entry. `orqalis ui --open` hosts in its terminal until Ctrl+C, and `run --open` keeps
any UI host it starts in the invoking CLI session. On Windows PowerShell, use
`npm.cmd` for installation and the
[session-local alias](../README.md#install-globally) to type `orqalis` when script
execution policy blocks its `.ps1` shim. `orqalis.cmd` remains a fallback. The combined [README usage guide](../README.md#usage-guide)
covers database setup, project initialization, the dashboard and assistant configuration.

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

## Prepare artifacts for the next release

Versions 1.0.0 and 1.0.1 are public and cannot be overwritten. Version 1.0.1 adds the
built-in updater; users on 1.0.0 need one npm upgrade to gain that command. Each
subsequent publication must use an unused version and pass its release checks. For each
new release, update
`pyproject.toml`, `src/orqalis/__init__.py`, `web/package.json` and `packages/npm/package.json` together.
Refresh their lockfiles and verify version consistency. Rebuilding an existing version
for investigation is separate from publishing a new release.

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

Public application artifact: `dist/orqalis-<version>.tgz`, using the selected release version.

The internal `.tools/release/orqalis-<version>-py3-none-any.whl` is copied to `vendor/` during
preparation. It is not a separate install/release channel. No source archive, native
installer or Orqalis PyPI publication is part of this workflow.

The prepack manifest binds the exact Python source inventory, build inputs and UI hashes.
Changes after preparation require rebuilding and preparing again. Maintainer-only
`NPM_RELEASE_READINESS.md` and its JSON verification record stay in Git and are excluded
from npm. Current results and the exact reviewed artifact digest are recorded in the
[release audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/NPM_RELEASE_READINESS.md).

## Test a clean installation outside the repository

Use a fresh OS temporary directory and an isolated global prefix; this leaves your
existing global installation untouched. Run these commands from the repository root
after preparing the selected version. The commands read its version from package metadata.

PowerShell:

```powershell
$releaseVersion = node -p "require('./packages/npm/package.json').version"
$tarball = Join-Path (Resolve-Path './dist').Path "orqalis-$releaseVersion.tgz"
$auditRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('orqalis-release-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $auditRoot | Out-Null
$prefix = Join-Path $auditRoot 'prefix'
$runtime = Join-Path $auditRoot 'runtime'
$env:ORQALIS_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
$env:ORQALIS_RUNTIME_HOME = $runtime
npm.cmd install -g --prefix $prefix $tarball --ignore-scripts --no-audit --no-fund
uv run python scripts/smoke_npm.py --prefix $prefix --runtime $runtime
& (Join-Path $prefix 'orqalis.cmd') --version
```

Linux/macOS:

```sh
release_version="$(node -p "require('./packages/npm/package.json').version")"
release_tarball="$(pwd)/dist/orqalis-$release_version.tgz"
audit_root="$(mktemp -d -t orqalis-release.XXXXXX)"
export ORQALIS_PYTHON="$(pwd)/.venv/bin/python"
export ORQALIS_RUNTIME_HOME="$audit_root/runtime"
npm install -g --prefix "$audit_root/prefix" "$release_tarball" --ignore-scripts --no-audit --no-fund
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

## Review and publish a new version

1. Inspect the source diff, test evidence and tarball file list. Check versions in
   pyproject.toml, src/orqalis/__init__.py, web/package.json and packages/npm/package.json.
   Refresh lockfiles when changing version or dependencies.
2. Confirm the MIT copyright attribution. Frontend third-party notices are included
   in the wheel; installed Python dependencies retain their own distribution licenses.
3. Confirm the repository, homepage and issue URLs in package metadata still point to
   the intended release repository.
4. Confirm `npm whoami` identifies the intended maintainer and `npm owner ls orqalis`
   lists an account authorized to publish this package. Check
   `npm view orqalis versions --json` and choose a version that has not been published.
   An authentication, registry or network error is not evidence that a version is available.
5. Commit the reviewed source and record its commit ID with release validation.
6. Inspect the exact prepared tarball with a dry run. The following examples assume
   the selected version has been updated, built and reviewed as described above.

PowerShell, from the repository root:

```powershell
$releaseVersion = node -p "require('./packages/npm/package.json').version"
$tarball = Join-Path (Resolve-Path './dist').Path "orqalis-$releaseVersion.tgz"
npm.cmd publish $tarball --dry-run --access public --registry=https://registry.npmjs.org/
```

After the release owner approves that artifact, authenticate and publish it:

```powershell
npm.cmd login --registry=https://registry.npmjs.org/
npm.cmd whoami --registry=https://registry.npmjs.org/
npm.cmd publish $tarball --access public --registry=https://registry.npmjs.org/
npm.cmd view "orqalis@$releaseVersion" version dist.integrity --registry=https://registry.npmjs.org/
```

Linux/macOS use the same reviewed artifact:

```sh
release_version="$(node -p "require('./packages/npm/package.json').version")"
release_tarball="$(pwd)/dist/orqalis-$release_version.tgz"
npm publish "$release_tarball" --dry-run --access public --registry=https://registry.npmjs.org/
```

After release-owner approval:

```sh
npm login --registry=https://registry.npmjs.org/
npm whoami --registry=https://registry.npmjs.org/
npm publish "$release_tarball" --access public --registry=https://registry.npmjs.org/
npm view "orqalis@$release_version" version dist.integrity --registry=https://registry.npmjs.org/
```

Publish the reviewed tarball. A published version cannot be replaced; corrections use
another version. Compare the registry integrity with the reviewed artifact and repeat
an isolated install using `orqalis@<version>` in place of the local tarball path.

Direct publishing requires npm account two-factor authentication or a granular access
token configured to bypass 2FA. A successful `npm whoami` alone does not satisfy that
publishing requirement. An E403 mentioning 2FA must be resolved in the publisher's npm
account; it is unrelated to the active Python virtual environment. Follow npm's
[2FA configuration](https://docs.npmjs.com/configuring-two-factor-authentication/) and
[publishing requirements](https://docs.npmjs.com/requiring-2fa-for-package-publishing-and-settings-modification/).
Keep credentials outside the repository.

For automation, configure npm trusted publishing against the actual repository and
approved release workflow. The included workflow only builds/tests/uploads artifacts;
it never publishes.

The root README is the combined usage guide. Edit that source, then rebuild the wheel
and run `scripts/prepare_npm.py` to copy it into the next release. Documentation commits
update GitHub immediately; READMEs bundled with already-published versions stay unchanged.
Updating the README displayed on npm requires publishing a new version, following npm's
[README update instructions](https://docs.npmjs.com/about-package-readme-files/).

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
architecture and phase order are unchanged, and that distribution consolidation did not
require a migration. Orqalis 1.0.1 separately includes migration `6b93c20e21af` for
persisted run-control policies and operator approvals.

References: [npm package metadata](https://docs.npmjs.com/cli/v12/configuring-npm/package-json/),
[publishing public packages](https://docs.npmjs.com/creating-and-publishing-unscoped-public-packages/),
[trusted publishing](https://docs.npmjs.com/trusted-publishers/).
