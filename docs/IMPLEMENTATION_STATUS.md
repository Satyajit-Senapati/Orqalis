# Implementation status

Canonical baseline: v1.2. This tracks delivery evidence; `09-implementation-plan.md`
remains the authoritative plan. Initial inspection: 2026-09-10.

## Repository baseline

The supplied directory contained only canonical documentation, with no Git metadata,
source, tests, frontend, database, or CI. Initialized Git on `main`; no existing
user branch or implementation was changed. Node 24 is available. Python 3.12.14 is installed locally. PostgreSQL 17/pgvector is healthy in Docker.

## Phase matrix

| Phase | Status | Completed capabilities | Remaining / validation |
| --- | --- | --- | --- |
| 0 Foundation | Complete | Typed foundational contracts, env settings, trace logging, PostgreSQL repository/migration, CLI, CI, lockfile | 11 tests passed including PostgreSQL; Ruff and strict mypy passed |
| 1 Project/Git | Complete | Safe Git discovery/status/diff/log, idempotent init, stack profile, owned worktrees | 27 tests passed; Ruff and strict mypy passed |
| 2 Memory MVP | Complete | Snapshots, source-backed index, provenance/supersession, incremental refresh, pgvector/structured search, Context Packs, CLI, directory graph | 43 tests passed including rollback/concurrency; Ruff and strict mypy passed |
| 3 Goal/acceptance | Complete | Immutable goal versions, explicit revisions, typed validators, persisted evidence and CLI | 50 tests passed; Ruff/format/strict mypy and PostgreSQL migration round-trip passed |
| 4 DAG/telemetry | Complete | DAG/scheduler, Orchestrator, durable attempts/actors/phases/events, idempotency, pause/resume/cancel, timing/snapshot projections, CLI | 55 tests passed; concurrent sequence and append-only tests; migration round-trip and strict checks passed |
| 5 Thin Mission Control | Complete | Shared SDK, loopback REST/WebSocket host, React Mission Control, durable reconnect, CLI launch, packaged frontend | 57 backend tests, 3 frontend tests, browser desktop/mobile check, Ruff/mypy/build passed |
| 6 Agents/skills/providers | Complete | — | Role/project permission intersection, versioned capability-selected skills, typed provider protocol, OpenAI transport, fixture and Anthropic skeleton, durable usage/outcomes; 66 tests plus interrupted-call regression passed |
| 7 Vertical execution | Complete | Isolated developer/test/reviewer execution, tool permissions and durable recovery receipts | 71 tests passed; PostgreSQL and Docker sandbox included |
| 8 Repair | Complete | Targeted additive repair DAG, stable task IDs, bounded escalation | 74 tests passed including convergence and zero/exhausted repair budgets |
| 9 Guardian/delivery | Complete | Independent scope checks, docs, final validation, gated Git commit/push | 81 tests passed; crash recovery and disposable local-remote push |
| 10 Memory curation | Complete | Accepted source-backed promotion, provenance, branch freshness and replay | 81 tests passed; crash after indexing covered |
| 11 MCP | Complete | Project-scoped tools/resources, assistant-native work, independent review and gated delivery | 83 tests passed; protocol continuity and real stdio startup |
| 12 Integrations | Complete | Anthropic adapter, Codex/Claude/Copilot MCP templates, external CLI host contract | 21 focused provider tests passed; live credentials unconfigured |
| 13 Full Control Center | Complete | DAG/Gantt, Project Brain, acceptance/delivery inspection, analytics, comparison and responsive dark UI | 96 backend tests, 3 frontend tests, active/completed browser checks, strict checks passed |
| 14 Hardening/release | Complete | Sandbox limits, process cleanup, failure/recovery/concurrency, strict browser preflight and npm release artifact | Public npm release 1.0.0 verified on 2026-09-14; published integrity matches the audited tarball |

## Decisions and deviations

- No unresolved canonical contradiction found. Detailed lifecycle names in document
  04 take precedence over the abbreviated illustrative workflow in the task prompt.
- PostgreSQL is the runtime store. No SQLite substitution is planned.
- Contracts and schemas are introduced with their phase, avoiding unused speculative
  infrastructure. Canonical entity names remain unchanged.
- The implementation repository uses
  https://github.com/Satyajit-Senapati/Orqalis.git as origin; local main tracks
  origin/main. Product delivery behavior is also tested against disposable local bare
  repositories.

## Migrations and checks

0001: projects with UUID identity and unique repository root. Clean PostgreSQL upgrade/downgrade/re-upgrade, metadata comparison, persistence roundtrip and rollback passed. Phase 0: 11 tests passed, no skips with the database configured; Ruff and strict mypy pass. CLI help works. The sandbox launcher encountered a setup error; approved commands remain usable.

Phase 2 migration: 9be36332f594 (pgvector and memory/source/snapshot/file/graph tables). Full suite: 43 passed against PostgreSQL, including schema round-trip, refresh rollback and concurrent refresh. Graph currently expresses file-to-directory membership; richer semantic relationships remain later work. External embeddings are optional and unconfigured.

Phase 3 migration: 9d45acc139d7 (runs, goal versions, acceptance and evidence). Run/current-goal circular foreign key explicitly created/dropped in dependency order. Full suite: 50 passed. RequirementsAgent is provider-neutral; CLI accepts an explicit contract until Phase 6. Manual/review validation remains pending. Lifecycle, durable events and timers are Phase 4; delivery gates remain Phase 9.

Phase 4 migration: 77fd51b32c12. Runtime event sequence and idempotency have distinct unique constraints; events have an append-only trigger. New run columns use a migration default for existing rows. Full suite: 55 passed. Quiescent pause is supported; process/worker interruption hooks and plan revision/repair remain their later-phase slices. Provider/delivery gates are not bypassable from the runtime foundation.

Phase 5: no schema migration. API tests cover contracts, same-origin policy, validation privacy and event cursor replay. Browser E2E covers persisted actor/progress/evidence, reload and mobile overflow. UI assets are included in built wheels. No live provider is connected yet; run preparation currently stops at GOAL_DEFINED. Two upstream TestClient deprecation warnings remain for hardening.

Phase 6 migration: 485d249a316d adds provider invocation records without introducing another actor/session concept. Full suite: 66 passed; focused recovery test also passes. OpenAI adapter tested at HTTP boundary; no live credentials configured. Interrupted calls fail closed rather than repeat a potentially billable request. Real tool execution and structured acceptance review are Phase 7.

Phase 7 migration: d4cac67f91e7 adds workspace, tool invocation and review records. Provider outputs are proposals bound to exact tool calls; reviewer outcomes require actual evidence/source checks. Validation marks TESTING and releases DB locks during execution. Initial execution stops at REVIEWING; no delivery gate is bypassed. Tool results and review survive restart; uncertain operations require explicit recovery. Trusted-local commands remain an explicitly configured fallback. Full suite: 71 passed, no skips with PostgreSQL/Docker configured.

Phase 8 migration: 29e512365451 adds plan/task membership and backfills existing plans. Task.plan_version means its introduction version, while membership preserves stable IDs across revised plans. Convergence, non-convergence and zero-repair fixtures pass without goal mutation. Full suite: 74 passed. Intermittent CPython Windows WMI startup diagnostics appeared, but the test process completed successfully; two upstream TestClient deprecation warnings remain.

Phase 9 migration: c13fa8e92cce adds Guardian reports, canonical findings/artifacts, final validation and Git delivery intent. The intent records tree, message and timestamp before commit creation; branch attachment uses compare-and-swap. Final Guardian rejects non-documentation changes after acceptance. CLI finalize requires an explicit immutable delivery policy. Full suite: 81 passed, no skips; Ruff/format/strict mypy passed (158 files); schema round-trip included. Delivery currently stops at MEMORY_FINALIZATION pending Phase 10.

Phase 10: no migration. Memory Curator indexes the accepted commit and records only committed source summaries plus a goal/validation outcome. Facts carry originating run and exact commit; changed sources supersede previous facts. Retrieval refreshes the inspected branch, including when it differs from the delivered worktree. A crash after indexing reuses existing facts and records promotion once. COMPLETED requires promotion evidence and successful plan tasks. Full suite: 81 passed; strict checks passed (159 files).

Phase 11: MCP SDK 2.2 added with major-version bound. Native implementation assignments/report receipts and artifacts use existing Core runtime records. Client-supplied reports cannot approve acceptance or expand execution permissions. Cross-client completion and real stdio startup pass. Full suite: 83 passed; strict checks passed (165 files). The MCP dependency supplies httpx2, resolving one upstream TestClient warning; the anyio alias warning remains. Project allow_push is enforced in addition to delivery policy.

Phase 12: no migration. Anthropic adapter normalizes public JSON/tool calls and reported cache usage, enforces local original-schema constraints, and discards private thinking/signatures. Both providers require explicit model/key. External CLI integration is an adapter/launcher contract for future hosts; no arbitrary CLI launcher is enabled. Codex/Claude/Copilot use native MCP today. 21 provider boundary/recovery tests passed; strict checks passed (168 files). No live provider credentials were used.

Phase 13: no migration. API projections expose persisted intervals, aggregate attempts, critical path, actual usage with coverage, artifacts, findings and delivery. React Flow graphs, timeline inspection, evidence, searchable Project Brain, diffs, actor metrics, run comparison and dark-theme presentation pass browser checks against active and fully delivered fixtures. Provider and external artifacts share bounded hash capture. Full backend suite: 96 passed; strict checks and frontend build/lint passed. Phase 14 subsequently addressed execution interruption, descendant cleanup and recovery.


Initial Phase 14 release verification (2026-09-10): 117 tests passed without skips against PostgreSQL/Docker
(84% coverage). Windows process-tree cleanup, read-only reviewer sandbox, persisted
cancellation, explicit attempt recovery, requirements restart, revised-goal history, parallel
context tasks, commit-object/attachment crashes and multi-destination push denial are covered.
New React, Android/Gradle and mixed-repository fixtures complete source-contract delivery;
full Python tests and acceptance failure/repair are separate end-to-end fixtures.

A 504-source bootstrap measured 134.14 seconds with coverage on this Windows machine;
unchanged HEAD took 0.063 seconds and read no sources; a one-file refresh took 0.578 seconds
and read only that file. These are measurements, not portable performance guarantees.

Both browser tests passed against the current local backend. Frontend lint/build and three
unit tests passed. Wheel/source builds include UI, migrations and skills without local caches.
Packaged standalone migration/doctor/UI and both browser scenarios also passed outside the
checkout. Final regressions passed for worktree-bound context, stable invocation replay and
DAG ordering independent of database row order.
No new Phase 14 schema revision: new settings and event payload fields are additive JSON,
and preparation uses existing Task/TaskExecution/ActorSession records.

Canonical numbered documents, handoff and sign-off were preserved exactly at this checkpoint.
The current Ruff version formats Markdown Python blocks, so signed-off inputs are excluded
from formatting; README only adds links to implementation documentation. The extraction
manifest remained historical input metadata until the later canonical-document cleanup.


## V1 release checkpoint

Version 1.0.0 is locally runnable. All 15 canonical implementation phases have a coherent
working implementation and recorded validation. The final tree retains the signed-off
architecture and adds no competing runtime/session models.

Final local release-candidate checks: 122 Python tests passed at 85% coverage against
PostgreSQL/pgvector and the Docker sandbox; 26 frontend tests, lint and production build
passed; and the strict Playwright suite passed 7 tests with 0 skipped. All 12 npm launcher
tests passed. The prepared npm artifact contained 56 entries, no forbidden files, and
passed fresh global-prefix version, cold/cached launch, JSON, invalid-exit and
working-directory isolation checks. The npm publish dry run passed without upload. Evidence:
[verification/v1.0.0.json](verification/v1.0.0.json) and
[dashboard-visual-refresh.json](verification/dashboard-visual-refresh.json).

Known operational boundaries are in [RELEASE_NOTES.md](RELEASE_NOTES.md): live provider
credentials were unavailable; embedding adapters are optional; remote hosting is disabled;
manual criteria do not auto-pass; external CLI hosts use a contract while native assistants
use MCP. Linux runtime CI is configured but has not been run on a hosted CI service.
There are no remaining implementation blockers for the locally validated V1 scope.

## Usage guide

Added the detailed usage guide (now merged into [README.md](../README.md)) with Windows/source/wheel setup, provider configuration,
a complete goal-to-delivery walkthrough, matching policy examples, UI/Memory usage,
MCP/SDK/API integration, recovery, revisions, backups and troubleshooting. Validated its
four JSON examples against current domain schemas, parsed both Python examples, checked
local links/anchors and 19 CLI help paths. Documentation-only change; no migration or
runtime behavior change.

## npm distribution and publishing readiness

Added a separate MIT-licensed npm package in packages/npm, retaining the Python Core
and private React frontend. The launcher bundles the wheel/UI, verifies hashes, creates
an isolated per-user Python runtime, installs exact hashed binary dependencies from
uv.lock, serializes concurrent setup and forwards CLI/MCP streams and exit status.
Node.js 22+ and an existing Python 3.12+ with venv/pip are prerequisites. No install
lifecycle script, database migration or global Python mutation is performed.

Release preparation checks npm/Python/UI/runtime version agreement, license metadata,
UI assets and migrations. UI builds collect production dependency license notices.
README.md covers npm setup; docs/PUBLISHING.md covers tarball checks and publication.
Python package metadata now uses a product README instead of the canonical handoff README.

Validation: launcher unit/contract tests, real Windows npm tarball installation with
--ignore-scripts, isolated runtime setup, version/JSON/error-code/module-isolation smoke,
frontend tests/build/lint, ESLint/Prettier, Ruff and strict typing for release scripts.
The package CI workflow builds one tarball and installs it on Windows/Linux/macOS.
Hosted cross-platform CI has not run in this workspace. The previous full backend
validation remains applicable; this slice changes distribution, not Core behavior.

No architectural deviation or migration. MIT was selected by the release owner.
The 2026-09-11 registry lookup returned E404 and found no published orqalis package; npm whoami
returned ENEEDAUTH. Actual publication requires release-owner authentication and has not
occurred. The implementation repository origin is
https://github.com/Satyajit-Senapati/Orqalis.git.


## Mission Control and README enhancement

Brownfield enhancement of the completed V1, audited from main at 2451063. The detailed
[gap analysis and dashboard tour](DASHBOARD.md) records what was reused and exposed.
The attachment supplies the UX brief; no separate accompanying design document was available.

| Enhancement phase | Status | Delivered capability |
| --- | --- | --- |
| 1 Audit | Complete | Existing Core, APIs, UI, telemetry, tests and documentation mapped |
| 2 UX foundation | Complete | Compact dark Mission Control, operational summary, responsive navigation and sheets |
| 3 Observability | Complete | Read-only skill catalog; event-backed skill loads and provider context references |
| 4 Mission Control | Complete | Combined orchestration graph, actor/task inspectors, current-work checkpoint |
| 5 Operational views | Complete | Tasks, Agents, Skills, filtered Activity; existing Brain, Delivery, Acceptance and Timeline integrated |
| 6 Polish | Complete | Keyboard alternatives, focus restoration, non-color status, reduced motion, bounded event buffers and graph layout |
| 7 README | Complete | Product landing page, updated usage guide, eight real optimized captures and source-of-truth index retained |
| 8 Validation | Complete | Backend regression, frontend/browser checks, command and link verification |

No new orchestration service, workflow transition, configuration key, table or migration.
The shared SDK exposes additive projections; the browser remains a Core client.
Provider request bodies and private reasoning remain unpersisted/unexposed. Skill metadata
is checked by the existing redaction policy before catalog exposure. Historical calls
without context telemetry are explicitly unavailable. File attribution requires evidence
or artifacts; no tool-path ownership is inferred.

Validation: full backend pytest with coverage passed 119 tests (85%, no skips) against
PostgreSQL/pgvector and Docker. After adding the catalog privacy regression, 16 focused
foundation/activity tests and six API/provider/activity tests passed; the suite now has
120 tests. Ruff lint/format and strict mypy passed (193 source files). Frontend lint,
TypeScript/build and ten unit tests passed. Seven real browser tests cover active/completed
runs, graph and inspector interaction, 390/768/1024/1440 widths, dark theme/reduced motion,
empty/error states and forced WebSocket disconnect/reconnect. Deterministic execution
fixtures also exercised actual review failure, targeted repair, final delivery and memory.

README checks: fresh npm ci/build, frozen uv sync, Compose health, migration and doctor
passed. CLI init, ui --open, status JSON, memory status, capabilities and runs help passed
against the local database. Run preparation passed with an explicit goal contract; only
OS browser opening was mocked. Provider-free invocation without a contract correctly
returned provider_error, so README now places provider setup before that command.
83 local links/anchors, including every screenshot path, resolved.

Eight JPEGs in docs/assets total approximately 1 MB. They are browser captures from
persisted local test-provider runs, not production placeholder data. The capture script
and regeneration instructions are checked in. No animation or copied third-party visual
assets were introduced.

Remaining boundaries: activity retains 200 visible events; timeline pages at 50 tracks;
graphs show up to 150 nodes with list alternatives. Core snapshot reconstruction still
scales with persisted history; large-run server profiling/caching is follow-up work.
The production JS bundle is approximately 512 kB minified / 162 kB gzip and emits Vite's
500 kB advisory. One upstream Starlette/AnyIO deprecation warning remains. Live provider
and hosted cross-platform CI checks still require the corresponding external environment.
The signed-off numbered documents, SIGNOFF and CODEX_HANDOFF are unchanged.

Release checks: rebuilt wheel/source/npm tarball include current UI and all screenshot
assets, with no local caches. All 11 launcher tests and package lint/format/hash checks
passed. The isolated Windows npm install passed cold/cached launch, JSON stdout, invalid
command status and working-directory module isolation. Publication remains pending.
Verification record: [dashboard-enhancement.json](verification/dashboard-enhancement.json).


## npm-only application distribution - owner-approved amendment

The current installation contract is global npm. Earlier wheel/source installation
records above describe historical validation; those channels are no longer offered.
ADR 0002 and the canonical design/sign-off/handoff now record this release-owner choice.
Python Core, SDK contributor setup, providers, interfaces and database schemas are unchanged.

- Product and usage documentation lead with npm; checkout-specific executable and wheel-install examples
  are removed. MCP examples spawn Node with the globally installed JavaScript entry point.
- The npm package includes compose.yaml so local database setup requires no checkout.
- The wheel builds under .tools/release as an internal npm payload. The public application
  artifact is dist/orqalis-1.0.0.tgz. Separate source archive/PyPI instructions are removed.
- Core CI no longer duplicates artifact builds; npm CI owns bundle and platform smoke checks.
- Duplicate Python package README is removed; internal metadata uses the npm README.
- Cleanup removes obsolete public wheel/source archives and the unused standalone wheel
  smoke environment. Development Python/tools and persisted application data are retained.

Validation: 12 npm tests passed, including missing-Compose rejection. ESLint/Prettier,
Node syntax checks, Ruff/format and strict release-script typing passed. Frozen source
sync, internal wheel build, prepack hash checks and isolated Windows global-prefix install
passed. Cold/cached startup, JSON output, invalid exit code and module isolation passed.
The installed Compose config validates; installed CLI doctor/migrate succeeds; real MCP
get_project succeeds through Node plus the installed JavaScript launcher from outside
the checkout root. 117 local documentation links/anchors and JSON/TOML examples validate.

Removed both old public wheel/source versions, stale multi-artifact checksums and the
unused .tools/release-env after path/process checks. Python development tooling, active
runtime environments, worktrees, PostgreSQL data and evidence remain intact. Generated
npm docs now rebuild from source, preventing removed installer guides from being shipped.
The runtime/Core/frontend implementation did not change, so their preceding regression
baseline remains applicable. Hosted platform CI and actual publication remain pending.


## Single README usage reference

Merged the complete usage guide into the root README, preserving all 15 sections,
policy/SDK examples, product overview and real screenshots. A contents list and
collapsible detailed navigation keep the quick start easy to reach. The separate
root guide and independently maintained npm README are retired; packaging generates
its README from the root source. Documentation/design links and package checks now
use that single usage reference. No runtime or CLI behavior change.

Validation: all 15 usage sections match the former guide verbatim. 125 repository
links/anchors and 117 local references inside the npm tarball resolve. All 12 launcher
tests, Node syntax/lint/format, Ruff/format and strict release-script typing pass.
The internal wheel and npm tarball build successfully; the packaged README matches
the root source byte-for-byte and no separate guide ships. Python package metadata
also reads the root README. Runtime regressions retain their previous baseline.


## Pitch-dark dashboard visual refresh - 2026-09-11

Status: complete for source, browser behavior and product media.

Approved scope:

- Adopt a Pitch-inspired primary dark visual system with deep navy/purple surfaces and
  layered magenta, violet and cyan accents.
- Apply stable semantic status colors and recognizable role accents across the shell,
  cards, graph, timeline, activity and inspector surfaces.
- Keep state understandable through text, icons and shape as well as color.
- Use subtle state-aware motion without deriving or fabricating workflow progress in the
  browser; honor reduced-motion preferences.
- Preserve the existing light/system options, responsive navigation and Core-owned
  orchestration contracts. The light/system portion of this historical visual-refresh
  scope was superseded by the dark-only UI decision recorded below.
- Regenerate the eight checked-in screenshots from newly seeded persisted integration
  runs and expose them in the root README gallery.

Architecture impact: presentation and documentation only. No workflow transition,
runtime record, API contract, provider abstraction, database table or migration is
introduced by this visual refresh. Mission Control continues to load authoritative
snapshots and persisted events from Orqalis Core.

Verification:

- Python: 122 passed with 85% coverage against PostgreSQL/pgvector and the Docker sandbox.
  One upstream Starlette/AnyIO deprecation warning remains; no application test failed
  because of it.
- Frontend: 26 unit tests passed; lint and the TypeScript/Vite production build were clean.
  The four JavaScript chunks are 221.85, 173.14, 63.37 and 54.98 kB, removing the earlier
  single-chunk advisory.
- Browser: the strict npm run test:e2e preflight and Playwright suite passed 7 tests with
  0 skipped. Coverage includes 390/768/1024/1440 responsive widths, dark-theme enforcement,
  reduced motion, reconnect/error states, graphs, inspectors and operational views.
- Media: eight validated 1600 x 1180 JPEGs were captured from newly seeded persisted
  runs with zero browser diagnostics. Capture writes to staging and publishes atomically;
  a forced failed capture left every previously published asset hash unchanged.
- Data: no migration or schema change.
- Distribution: all 12 npm launcher tests and package checks passed. The prepared tarball
  contained 56 entries and 0 forbidden entries. Fresh global-prefix version, cold/cached
  launch, JSON, invalid-exit and working-directory isolation checks passed. npm publish
  --dry-run passed without upload.

Registry lookup returned E404 and npm whoami returned ENEEDAUTH. No public registry
publication was performed.
Detailed evidence: [dashboard-visual-refresh.json](verification/dashboard-visual-refresh.json).

Post-push hosted verification exposed that npm pack does not create an absent
--pack-destination directory. The release preparation script now creates and validates
the ignored dist directory, preserving the same package command on clean checkouts.

The same hosted run exposed a POSIX permissions defect in the Docker sandbox: the
capability-free container could not traverse pytest's owner-only workspace as a different
user. Docker launches now map the caller's effective user/group IDs on POSIX and the
sandbox test verifies readable output with matching ownership. An exact Ubuntu reproduction
passed the targeted test and the complete 123-test suite at 84% coverage against a
disposable PostgreSQL/pgvector service and the Docker sandbox. Ruff, format and strict mypy
checks pass; the release commit's GitHub checks are the authoritative hosted result.

Dark-only UI slice: removed the light/system selector, saved-theme handling, prepaint script,
React Flow theme observer and light-specific styles. The HTML and graph renderer now declare
dark mode directly. Browser coverage deliberately emulates a light operating-system theme
and seeds a stale saved light preference, then verifies Pitch-dark remains fixed and no theme
selector is exposed. No API, workflow, telemetry, database or migration change is required.

Dark-only validation: 25 frontend unit tests passed; ESLint and the TypeScript/Vite
production build passed. The strict persisted-fixture Playwright suite passed all 7 tests
with 0 skipped, including an emulated light operating system, stale saved light preference
and reload. Eight 1600 x 1180 README JPEGs were regenerated atomically with zero browser
diagnostics, and visual inspection confirmed the top-bar layout remains balanced after
removing the selector. The build emits no theme bootstrap asset. The JavaScript chunks are
221.85, 173.14, 62.11 and 54.98 kB. Project Brain browser coverage allows up
to 15 seconds for its Git-aware API under parallel local test load; this changes only
the test harness wait and no product timeout, workflow or UI behavior.

## Workspace navigation and interaction hardening - 2026-09-11

Status: complete.

The Home surface now projects registered projects, per-project run counts, active work,
latest-run links and persisted workspace statistics. Project selection is URL-backed and
filters run history without adding a Workspace domain model. Mission Control resolves to
the selected project's latest run. User-home names are shortened in visible repository
paths while the local full path remains available as hover metadata.

The sidebar uses a bounded scrolling body and fixed Core status on short desktop windows.
At 900px and below it becomes a complete drawer containing workspace, project, recent-run
and Core-status controls. Escape and backdrop interaction close the drawer and restore
focus. Project cards, breadcrumbs and run rows are operable links with current-page state.

Run views retain their mounted state after first use while hidden panels use the native
hidden attribute and expose no focusable descendants. Graphs refit after topology or view
visibility changes. Inspector content resets scroll and focus when selection changes;
Delivery supports repeated inspection of the same file. Timeline intervals use native
buttons and a non-overlapping keyboard selector. Task, Activity, Project Brain and Metrics
filters recover when their available options or requests change. A missing event-history
request degrades Activity while keeping the authoritative snapshot and live stream usable.
Home project/run requests fail independently and preserve whichever persisted projection
remains available.

Git-aware memory now detects when an indexed commit disappeared because a repository was
recreated at the same path, performs a full tracked refresh and invalidates obsolete facts.
Windows command execution starts its timeout after job containment makes the child runnable;
timeout cleanup terminates the job first and preserves timeout, cancellation and output-limit
classifications when cleanup itself reports an error.

Validation: 127 Python tests passed with 85% coverage against the disposable PostgreSQL/
pgvector database and Docker sandbox; Ruff lint, Ruff format and strict mypy passed across
196 source files. The one warning is the existing upstream Starlette/AnyIO alias deprecation.
Frontend ESLint and the TypeScript/Vite production build passed; 28 Vitest tests passed.
The strict persisted-fixture Playwright suite passed 11 tests with 0 skipped, covering
project navigation, 1024x500 sidebar scrolling, the 390px drawer and focus recovery,
partial API failures, degraded history, live reconnection, graphs, timeline controls,
inspectors, retained view state, dark-only presentation and reduced motion. Local E2E uses
one worker by default to protect the single Core process; ORQALIS_E2E_WORKERS can override it.

Nine 1600 x 1180 JPEGs were regenerated from persisted runtime fixtures with zero browser
diagnostics. Capture stages the complete set before replacement; a deliberate readiness
failure left the published images intact. The new workspace overview is included in the
README and visible user-home path labels are privacy-safe.

The npm release preparation now byte-compares generated root files, exact documentation and
skill trees, the staged/built wheel, and recorded web bundle hashes. Preparation replaces
old generated trees, so removed skills cannot remain in a package. Thirteen launcher and
package-guard tests pass. The prepared artifact contains 58 entries and no forbidden files;
npm publish --dry-run performs no upload.

Architecture impact: presentation, reliability and release verification only. Existing
Core services remain authoritative. No workflow transition, canonical telemetry entity,
API schema, provider abstraction, database table or migration changed.
Verification record: [ui-behavior-hardening.json](verification/ui-behavior-hardening.json).

## Canonical-document cleanup - 2026-09-11

Status: complete.

The frozen extraction `MANIFEST.json` and generated all-in-one design export were removed.
Every recorded extraction hash had become stale after approved implementation and npm
distribution amendments, while the combined export duplicated the maintained modular
specifications. `SIGNOFF.md`, `CODEX_HANDOFF.md`, `CONSOLIDATION_NOTES.md` and the numbered
documents remain the canonical source set. `SIGNOFF.md` remains part of the npm package's
release evidence; implementation-only handoff and reconciliation files remain excluded from
the published package.

No runtime, API, schema, migration or UI behavior changed.


## V1 public npm release audit - 2026-09-14

Status: release hardening implemented. The current release decision and authoritative
requirement-by-requirement evidence are in [release audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/NPM_RELEASE_READINESS.md).

Fixed cold UI child-process import isolation; structured credential and auth-header
redaction; OpenAI strict transport schemas; Python skill selection and language matching;
independent Guardian intersection of explicit goal scope and immutable write permissions;
branch-aware memory retrieval, ranking refill, documentation categories, private-key
exclusion and indexer/model refresh fingerprints. Added CLI version/catalog commands and
typed untrusted MCP finding reports with independent evidence and final-tree checks.
Source findings can resolve through matching current file-validation evidence, including
file deletion; every relied-on criterion is checked again before delivery even when
optional. Temporary embedding outages retain structured retrieval, and later refreshes
backfill missing vectors from stored content without scanning the repository again.
Aligned REST context budgets with Core. Package prepack now binds source/build inputs;
relative OS cache roots are ignored, and internal readiness records stay out of npm.

Release verification now exercises the actual npm global shim outside the repository,
including a hostile current-directory module, and a packaged fresh-project/Core/MCP/UI
harness against a disposable PostgreSQL database. CI retains one tarball across platform
smoke jobs and adds a Linux packaged integration gate. Detailed source, dependency,
artifact and installed browser results are maintained in the release audit.

No competing orchestration/telemetry model, installer or provider-specific domain service
was introduced. No migration is required. Signed-off phase order and npm-only application
distribution remain unchanged. At the pre-publication audit, live provider account and
npm ownership/authentication checks were external, and no npm publish had been performed.
The publication update below supersedes that npm release status.


## Public npm installation documentation - 2026-09-14

Status: complete. The release owner published `orqalis@1.0.0` at 09:12:43.151 UTC.
The public registry reports 1.0.0 as `latest`; its integrity matches the reviewed
release tarball. Publication is recorded separately from the historical audit matrix.

The combined README guide now starts with `npm install -g orqalis`, includes explicit
PowerShell commands, explains prerequisites and managed Python setup, and puts backups
before upgrades. MCP setup, release notes, ADR 0002 and the maintainer publishing guide
now describe the public package. Future publishing instructions require an unused
version. Git documentation can update immediately; npm's displayed README updates with
a subsequent release. No separate GUIDE or installer was added.

Validation: installed `orqalis@1.0.0` from the public registry into a fresh temporary
global prefix outside the repository. Existing smoke checks passed cold/cached startup,
global version/help, JSON output, invalid-command exit status and CWD isolation on
Windows x64 with Node 24.16.0 and Python 3.12.14. Documentation links, section anchors,
code fences, verification JSON and diff whitespace were checked. The published 1.0.0
tarball remains byte-for-byte unchanged. Evidence is in the release audit publication
record; database and paid provider checks were not repeated for this documentation slice.

No runtime, UI, schema, migration, version or architectural changes. No new publication.


## Direct npm updater and Windows command UX - 2026-09-14

Status: implementation complete; version 1.0.1 is a prepared, unpublished patch
candidate. The already-published 1.0.0 tarball is immutable. The npm launcher now
supports `orqalis update --check` and `orqalis update` before Python startup. It checks
the public registry, compares versions without downgrading, installs the exact checked
release into the invoking global npm prefix, and reports npm failures. npm is resolved
from the Node installation rather than a project PATH entry. No Python runtime, database
or UI process is started by the update command. Backup, migration and restart remain
explicit operator steps.

The combined README uses bare `orqalis` in PowerShell examples after a session-local
alias for systems that block npm's generated `.ps1` shim. Users on 1.0.0 must run one
`npm install -g orqalis@latest` upgrade after 1.0.1 publication to gain the built-in
command. Release preparation now removes stale generated Orqalis wheels before packing
consecutive versions, while retaining path and symlink safeguards.

Validation: Python unit suite 175 passed (including 18 focused CLI/package tests);
npm launcher tests 29 passed;
Ruff, strict mypy, npm syntax/lint/Prettier, frontend lint/28 tests/build and diff
whitespace checks passed. The 1.0.1 npm tarball contains 59 intended entries and one
matching wheel. An isolated Windows x64 global install passed cold/cached CLI smoke,
help, JSON, invalid-command and working-directory isolation. Restricted PowerShell
alias plus `orqalis update --check` passed. A disposable prefix with an older fixture
version successfully self-updated through the public npm registry to 1.0.0, leaving
the user's global installation and database untouched. No schema migration is required.

No competing distribution mechanism, orchestration change or UI behavior was added.
The patch is not public until the release owner approves and publishes its reviewed
1.0.1 tarball.
