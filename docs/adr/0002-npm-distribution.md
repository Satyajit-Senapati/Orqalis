# ADR 0002: npm is the Orqalis V1 distribution channel

Status: accepted by the release owner, 2026-09-10.

## Decision

Users install and upgrade Orqalis with npm install -g orqalis and npm install -g
orqalis@latest. The reviewed npm tarball is the single public application artifact.
Starting with version 1.0.1, `orqalis update` invokes npm to check or install the
public `latest` release into its existing global prefix. Database migration remains
an explicit operator command, and the npm package remains the sole public installer.
Registry publication is a release-owner action, separate from building and testing.
The release owner published [orqalis@1.0.0](https://www.npmjs.com/package/orqalis/v/1.0.0)
on September 14, 2026; the public registry integrity matches the reviewed artifact.
This publication fulfills the accepted distribution decision without changing it.

The npm launcher invokes the existing Python Core. Node.js 22+ and Python 3.12+
with venv/pip remain prerequisites. First launch creates a hash-verified, isolated
per-user Python environment; it does not run migrations or start PostgreSQL.
The package contains the compiled UI, migrations, skills, usage documents and a
loopback Compose configuration for optional local database setup.

The Python wheel is an internal npm payload built under .tools/release and copied
into packages/npm/vendor. It is not a separate supported installation channel.
Do not maintain a standalone executable installer, Python source release or Orqalis
PyPI publication workflow. Python dependencies still come from PyPI with pinned hashes.

Source checkout setup remains for contributors and Python SDK development. The SDK,
CLI, MCP, REST/WebSocket and browser still invoke the same application services.
No provider, database, workflow, acceptance, Git-safety or telemetry contract changes.

## Windows and interoperability

npm supplies the global orqalis command and platform shims (orqalis.cmd on Windows).
Python's generated executables and native dependency binaries are runtime components,
not separate installers; deleting them would break the npm application. MCP hosts
that spawn processes directly use Node plus the installed bin/orqalis.js path to
avoid depending on shell-specific shims. Warm up with orqalis version before MCP startup.

## Release and cleanup

CI builds and tests the same npm tarball on Windows, Linux and macOS. Release checks
verify packaged UI, migrations, skills, Compose/docs, integrity, cold/cached startup,
JSON/stdout separation and exit status. Hosted CI validation must be recorded when run.

Remove obsolete public wheel/source archives and stale checksum manifests. Preserve
working development environments, active runtime caches, repositories, worktrees,
PostgreSQL volumes, evidence and memory. npm uninstall removes the launcher but retains
runtime caches and application data. Stop their processes before explicitly removing
unused runtime directories. Never use broad recursive executable deletion.

## Consequences

Users have one installation path and need no frontend build or source checkout.
The Python dependency remains explicit; this is distribution consolidation, not a
backend rewrite or a self-contained native executable. Future distribution channels
require an explicit update to this decision and their own validation.
