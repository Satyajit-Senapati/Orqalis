# ADR 0002: npm is the Orqalis V1 distribution channel

Status: accepted by the release owner, 2026-09-10; local-first packaging amendment
accepted 2026-09-16.

## Decision

Users install and upgrade Orqalis with `npm install -g orqalis` and
`npm install -g orqalis@latest`. The reviewed npm tarball is the supported public
application artifact. `orqalis update` delegates to npm in the existing global prefix.
Registry publication remains an explicit release-owner action.

The npm launcher invokes the bundled Python Core. Node.js 22+ and Python 3.12+ remain
prerequisites. First launch creates a hash-verified isolated per-user Python environment;
the CLI then uses the current repository's `.orqalis/` store. Installation starts no
database, daemon or autostart service. Local UI/API hosting is terminal-owned and stops with
its command.

The package contains the compiled UI, filesystem runtime, bundled skills and usage
documents. It does not ship a database Compose stack and standard operation needs no
PostgreSQL/pgvector dependency or database environment variable.

The Python wheel is an internal npm payload built under `.tools/release` and copied into
`packages/npm/vendor`. It is not a separate supported publication channel. Contributor
source setup and Python SDK development remain supported.

## Windows and interoperability

npm supplies the global command and platform shims. MCP hosts that spawn directly use Node
plus the installed `bin/orqalis.js` path rather than assuming shell-specific shims. Warm-up
may populate the per-user runtime cache, but project intelligence always belongs to the
selected repository, not the launcher cache.

## Release and cleanup

CI builds and tests the same tarball on Windows, Linux and macOS. Checks verify the bundled
UI/runtime/skills/docs, integrity, cold and cached startup, JSON/stdout separation, root
isolation and exit status without a database service.

`npm uninstall` removes the launcher but deliberately does not delete repositories or
their `.orqalis/` directories. Runtime download/build caches are non-canonical and may be
removed explicitly after stopping processes. Never perform broad recursive cleanup.

The Python and npm distributions contain no PostgreSQL compatibility extra or migration
modules. No legacy exporter command is implemented.

## Consequences

Users have one public installation path and need no frontend build, source checkout or
database container. The Python prerequisite remains explicit; this is distribution
consolidation, not a native executable. Future channels require an ADR and equivalent
filesystem/root-isolation validation.
