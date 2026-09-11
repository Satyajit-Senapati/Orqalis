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
orqalis version
orqalis --help
```

Requirements: Node.js 22+, Python 3.12+ with venv/pip, and internet for first-launch
dependency installation. Git, PostgreSQL/pgvector, Docker and provider configuration
are required for the corresponding application features; see [README.md](../README.md).

The tarball contains a version-matched wheel (including UI, migrations and skills),
hash-locked requirements exported from uv.lock, MIT license, guide, supporting docs and
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
The npm prepack check rejects changed hashes, missing files and stale vendor artifacts.
Preparation also creates the ignored dist output directory, so npm pack works from a
clean checkout.

Public application artifact: dist/orqalis-1.0.0.tgz.

The internal .tools/release/orqalis-1.0.0-py3-none-any.whl is copied to vendor/ during
preparation. It is not a separate install/release channel. No source archive, native
installer or Orqalis PyPI publication is part of this workflow.

Verified local release candidate (2026-09-11):

- All package checks and 12 npm launcher tests passed.
- Package inventory: 56 entries and 0 forbidden entries.
- Fresh global-prefix version, cold/cached launch, JSON output, invalid-exit behavior and
  working-directory isolation checks passed.
- npm publish --dry-run passed without uploading.

At the 2026-09-11 release rehearsal, the registry lookup returned E404, so no published
package occupied the public orqalis entry. npm whoami returned ENEEDAUTH. Actual publication
and ownership verification require release-owner authentication and were not performed.

Generated npm vendor/docs/README/sign-off/skill copies and dist artifacts are ignored by Git.
The root README is the single product/usage source; preparation copies it into npm.
Edit source files, then regenerate. Never edit generated copies to fix a release.

## Test the actual npm tarball

Install into an isolated prefix so an existing global installation is unaffected.

PowerShell:

```powershell
$prefix = Join-Path $PWD '.tools/npm-release-check'
$runtime = Join-Path $PWD '.tools/npm-release-runtime'
$env:ORQALIS_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
$env:ORQALIS_RUNTIME_HOME = $runtime
npm.cmd install -g --prefix $prefix ./dist/orqalis-1.0.0.tgz --ignore-scripts --no-audit --no-fund
uv run python scripts/smoke_npm.py --prefix $prefix --runtime $runtime
& (Join-Path $prefix 'orqalis.cmd') version
```

Linux/macOS:

```sh
export ORQALIS_PYTHON="$(pwd)/.venv/bin/python"
export ORQALIS_RUNTIME_HOME="$(pwd)/.tools/npm-release-runtime"
npm install -g --prefix "$(pwd)/.tools/npm-release-check" ./dist/orqalis-1.0.0.tgz --ignore-scripts --no-audit --no-fund
uv run python scripts/smoke_npm.py --prefix "$(pwd)/.tools/npm-release-check" --runtime "$ORQALIS_RUNTIME_HOME"
./.tools/npm-release-check/bin/orqalis version
```

Use a new runtime directory to exercise cold setup. The smoke script verifies version,
cached startup, parseable JSON, invalid-command exit status and working-directory
module isolation. It does not need a database or provider credentials.
The package workflow builds once and tests that tarball on Windows, Linux and macOS.
Hosted CI results must be checked before claiming those platforms are release validated.

Run the normal PostgreSQL/Docker backend and browser suites from
[DEVELOPMENT.md](DEVELOPMENT.md) when Core/UI changes; packaging tests do not replace them.

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
