# Release notes

<a id="orqalis-210-local-candidate-unpublished"></a>

## Orqalis 2.1.0

This version adds portable Agent Skills, bounded repository graph queries and exact
symbol reads, conservative JavaScript/TypeScript/TSX extraction, identifier retrieval,
reviewed memory supersession and discovery, MCP lifecycle/history tools, local traces
and provider metrics, durable sandbox ownership and stronger test-integrity checks.
Graph facts, reviewed project memory and Task Capsules remain separate project-owned
systems; normal operation requires no external database.

Optimization shares fresh Git/graph work within validated requests, avoids foreign
capsule scans for known owners, loads source memory on demand and keeps history scans
outside the allocation lock. FIFO writer handoff retains reentrancy, original deadlines
and OS locks. PLAN approval persists atomically with its transition. Auxiliary identity
leases reject duplicates and revalidate run generations. Fresh containment,
symlink/junction checks, cancellation ownership and canonical recovery remain enforced.

Windows canonical readers now permit shared snapshot access while one atomic rename
publishes the next generation. Open readers retain their prior bytes. The native rename
requests replacement and POSIX semantics without bypassing ACLs or read-only permissions.
Unsupported API/filesystem cases close the handle before using the prior atomic operation.
Storage formats, fsync, journal/recovery and the five bounded retry attempts are preserved.
Wrong-thread lock release rejects before changing counters or the native handle.
Atomic writes also verify flushed temporary bytes through their owned descriptor, avoiding
a second file open. Fresh identity checks precede replacement; failed ownership checks
preserve the original error and leave the unverified path untouched during cleanup.
The public memory benchmark counts canonical native reads once; workloads, gold and
budgets are preserved, and the original script is archived. The controlled collision
is fixed; the holder responsible for historical round22 remains unknown.

WebSocket teardown shields child cancellation/join from framework cancellation while
native cancellation propagates. Temporary cleanup clears READONLY only on a guarded,
regular owned temporary. State bytes already checked for secrets are reused, lock gates
are allocated only when absent, and diagnostics are lowercased once per call.

Python, frontend and launcher versions are synchronized at 2.1.0. Advisory repairs
include PyJWT, brace-expansion and source-map-js1.2.2. The last patch changes one
dev-only frontend lock entry and reproduces the tested production bytes. The launcher installs verified bundled pip offline
before index access and disables inherited pip configuration. Windows serve/UI uses a
Selector loop with at most 512 sockets and no asynchronous pipes/subprocesses;
SDK/harness workers use separate loops. The Uvicorn minimum is 0.36; the lockfile uses 0.52.4.

**Current local verification, 2026-10-09:** current focused133, immutable86
compatibility,13 static gates, clean dependency audits, installed wheel/npm17/MCP41,
exact installed51-package audits, fixed263-file heldout and1,001-row/33-page history
checks pass. Both whole qualifications completed: each collected935 Python tests,
with933 PASS, two explicit optional skips and zero failures/errors. Both original
browser suites passed all14 checks. Source/test/helper/environment guards remained
stable; owned processes were closed and reaped.

Execution medians25.810 and20.452seconds compare with the pooled all-nine55.870-second
reference. Paired quality retains all30 reviewed case/metric tradeoffs as raw REVIEW;
memory, UI and constrained checks pass. Richer graph facts cost more storage and Python
allocation, and progressive complete memory answers cost more than full rediscovery.
The larger263-file graph has11,505nodes/13,575edges; its store uses39,782,462bytes and
query Python peak allocation is56,666,577bytes, excluding native allocation/RSS.
The original8,011.435ms rebuild crossed the6,505.331ms investigation threshold.
A fixed baseline/current/current/baseline SDK study confirmed the cold degradation:
current8,470.894/4,672.093ms versus baseline1,596.899/1,504.215ms. Warm refresh,
one-file delta and context comparisons stayed below the lines in that current-source
study. Reader/publication controls did not support a safe fallback. A bounded cache-read
experiment passed123 focused tests but failed its fixed performance screen and was
reverted exactly; it is excluded from this version. The user explicitly accepted this measured cold-rebuild cost for2.1.0 on2026-10-09
and deferred cache optimization to the next release. This is a known release
tradeoff, not a speed fix; its cause remains unknown. All original measurements
and safeguards remain. The recorded local package checks validate their captured documentation snapshot.
After documentation consolidation, hosted CI must rebuild and test the current committed
package; the earlier local tarball is historical evidence. No universal speed,
RAM or portable latency guarantee is claimed.
Historical failures and all nine reference timings remain retained; current passing
checks do not establish the historical failures' causes.

The [engineering status](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md)
owns exact identities, retained failures and acceptance dispositions; the
[worklist](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/NEXT_SESSION.md)
owns the remaining steps. Hosted platform gates are required before publication.
Native Linux/macOS execution, live Docker, direct symlink creation and paid assistant
harnesses remain unqualified by these local Windows checks. Cleanup, commit and push
were authorized on 2026-10-09; tagging and publication remain pending release-owner gates.

## Release status checked 2026-09-26

The public npm registry now reports `orqalis@2.0.0` as `latest`. This supersedes the dated
pre-publication statements below. The registry package does not include the post-release
working-tree enhancements. [Registry metadata](https://registry.npmjs.org/orqalis/latest).

## Local-first architecture notice - 2026-09-16

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

The active development architecture uses `.orqalis/` filesystem stores and requires no
PostgreSQL, pgvector, Docker or database environment variable for standard usage. The
published 1.0.0/1.0.1 notes below are preserved as historical statements about those exact
artifacts; their database-backed validation is not current setup guidance. Docker remains
optional sandbox infrastructure. The 2.0.0 candidate contains no SQL compatibility extra,
database migration command or legacy exporter.

## Orqalis 2.0.0 (historical pre-publication validation)

Orqalis 2.0.0 makes the repository-local `.orqalis/` filesystem store authoritative for
project intelligence, curated memory, repository graph/index data, Task Capsules, events,
execution state, evidence and delivery history. Standard CLI, MCP, API and Control Center
operation requires no external database or database environment variable.

The major version records the incompatible retirement of the 1.0.x SQL storage runtime.
There is no bundled PostgreSQL exporter; preserve legacy data and use the matching archived
release when bespoke export work is required. The repository-controlled suite and the exact
2.0.0 wheel/tarball pass isolated no-database installation and application verification;
commands and hashes are recorded in the maintainer cleanup audit. The candidate has not
been published. Public npm `latest` remains the historical 1.0.1 artifact until an
authorized release owner publishes 2.0.0.

## Orqalis 1.0.1 (historical published artifact)

Orqalis 1.0.1 is publicly available on npm. It adds
`orqalis update --check` and `orqalis update` to the npm launcher so users can check
and install the latest public Orqalis version from within Orqalis. The updater runs
before Python runtime setup and leaves database migration and process restarts explicit.
It checks that the invoking launcher belongs to a global npm installation and updates
that same global prefix. It does not introduce another distribution channel.

Windows examples can use `orqalis` directly after a session-local PowerShell alias
when the generated npm `.ps1` shim is blocked; `orqalis.cmd` remains available as a
fallback. The updater cannot be retrofitted into already-published 1.0.0. Users first
install 1.0.1 once through npm, then use `orqalis update` for later releases.

Release validation passed 312 PostgreSQL-backed Python tests, the isolated Docker
sandbox test, 33 frontend unit tests, 12 browser end-to-end tests, 29 npm launcher
tests, Python lint/format/type checks, frontend lint and the production build.

Local UI hosting is now terminal-owned: `orqalis ui --open` stays active until
Ctrl+C, and `orqalis run --open` serves during execution and waits for Ctrl+C when
it owns the UI. A second CLI can reuse a healthy listener without stopping it. No
Windows service, scheduled task or autostart entry is registered. An installed
Windows npm CLI released its listener and child process after terminal Ctrl+C.

This release also strengthens scoped agent/skill selection and
adds SUPERVISED run mode with durable GOAL, PLAN, REPAIR and DELIVERY approval
gates (optional TASK gate), versioned goal/plan editing, CLI and local browser
decisions, and exact delivery-policy binding. The Orchestrator remains the sole
workflow authority. Browser approvals use a dedicated local token and record
the shared local UI identity; execute/finalize still resume through CLI/SDK/MCP.
The browser shows a policy summary and full digest, while the operator inspects
the exact delivery policy JSON and repository diff separately.

Migration `6b93c20e21af` adds run control policies, approval requests and
decisions. After upgrading, run `orqalis migrate` before starting Orqalis 1.0.1.
Version 1.0.0 does not contain these controls. The current filesystem release has separate
[upgrade guidance](OPERATIONS.md#data-ownership-and-backup); the historical control
surface remains described in the [dashboard guide](10-local-control-center.md#operator-control).

### Publication record

The public registry accepted version 1.0.1 at `2026-09-15T05:33:58.810Z` from source
commit `dfd8e31f2d6c84b2df9565bff8f3c1d03cd30c9f` and assigned the `latest` tag. The reviewed
69-file tarball is 1,539,392 bytes (1,968,593 bytes unpacked), with SHA-256
`b0bf31832c40d59c5b03b4e6cfed7f15f6ec9f47983e736b8a008867500c9011`, npm shasum `10d66da1c2a47b4aabcf9be4bad7cc7f7021705e`, and integrity
`sha512-3TNPpq3Eskq6eVsl0BFxYG4Ch5d8bq1wIfEtAApSO6CNLe8YuYEQR0depln7v2Y0mO9hz68A6JcTQ1HX4M/nSA==`.
A direct registry download matched the reviewed local artifact byte-for-byte by SHA-256.

Fresh disposable registry installs of both `orqalis@1.0.1` and unqualified
`orqalis` resolved to the same reviewed manifest. Cold/cached startup, version/help,
JSON output, invalid-command handling, working-directory isolation, `modes`, and
`update --check` passed on Windows x64 with Node 24 and Python 3.12. The exact
release-source GitHub `quality` and `npm package` workflows passed, including
Windows/Linux/macOS launcher smokes and Linux installed Core/MCP/UI integration.

## Orqalis 1.0.0

Orqalis 1.0.0 is publicly available on [npm](https://www.npmjs.com/package/orqalis/v/1.0.0),
published September 14, 2026 at 09:12:43 UTC. This local V1 application follows the
canonical v1.2 architecture and phase plan. The architecture version and software
release version are separate identifiers.

```sh
npm install -g orqalis
orqalis --version
```

See the current [installation guide](../README.md#quick-start) for the local-first
candidate. Database setup for this historical artifact remains available from its release
tag. Windows PowerShell users can use `npm.cmd` and `orqalis.cmd` when script execution
policy blocks the PowerShell shims.

### Delivered

- Shared Python SDK, CLI, loopback REST/WebSocket API, project-scoped stdio MCP and React Control Center.
- PostgreSQL migrations, deterministic workflow/DAG scheduling, durable events, actor sessions, timing and explicit recovery.
- Versioned requirements and evidence-backed acceptance, scoped execution, targeted repair, independent Change Guardian, documentation and gated Git delivery.
- Git-aware Project Memory, source provenance, selective refresh and accepted-run curation.
- OpenAI and Anthropic adapters, dynamic skills and Codex/Claude/Copilot MCP configuration.
- DAG, timeline, acceptance, Project Brain, diffs, delivery receipts, actor metrics and historical comparison.
- Docker limits, process-tree cleanup, cancellation, redaction and optional OpenTelemetry export.

### Dashboard visual refresh - 2026-09-11

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

### Validation scope

Release verification uses deterministic worker fixtures and mocked provider HTTP boundaries;
no live OpenAI or Anthropic credentials were supplied. The Python fixture runs actual tests,
review, failure/repair, documentation, Git commit and local-remote push. React, Android/Gradle
and mixed-repository fixtures exercise language-neutral source contracts and delivery;
they do not substitute for each platform's real build pipeline.

The full suite ran on Windows and Ubuntu with PostgreSQL 17/pgvector and Docker. Strict type
checks cover Windows and Linux branches. GitHub checks on the release commit remain the
authoritative hosted result. Browser tests cover active and completed persisted runs,
responsive layout and reload.

### Operational limits

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


### Distribution

Global npm installation is the supported application channel. The npm tarball includes
the existing Python Core/UI, migrations, skills, Compose configuration and documentation.
Node.js 22+ and Python 3.12+ remain required; initial setup uses an isolated runtime.
The wheel is internal to npm. Standalone executable, separate wheel/source and Orqalis
PyPI releases are not maintained. Source development remains available to contributors.
At the 1.0.0 publication, the registry listed `orqalis@1.0.0` under the
`latest` tag. Its SHA-1 digest
`c522b46f28ea793b914d9cc2c591f980e4d142a8` and SHA-512 integrity match the reviewed release
artifact. Earlier E404/ENEEDAUTH observations were checks made before publication;
they no longer describe package availability. Installers do not need an npm login.
See [ADR 0002](adr/0002-npm-distribution.md) and the
[release audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/NPM_RELEASE_READINESS.md).
