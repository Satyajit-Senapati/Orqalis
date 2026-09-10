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
| 13 Full Control Center | Complete | DAG/Gantt, Project Brain, acceptance/delivery inspection, analytics, comparison and themes | 96 backend tests, 3 frontend tests, active/completed browser checks, strict checks passed |
| 14 Hardening/release | In progress | — | Sandbox, failure/recovery/concurrency and V1 release gates |

## Decisions and deviations

- No unresolved canonical contradiction found. Detailed lifecycle names in document
  04 take precedence over the abbreviated illustrative workflow in the task prompt.
- PostgreSQL is the runtime store. No SQLite substitution is planned.
- Contracts and schemas are introduced with their phase, avoiding unused speculative
  infrastructure. Canonical entity names remain unchanged.
- The implementation release is recorded locally on main. No remote is configured and no implementation-repository push is performed. Product push behavior is tested against disposable local bare repositories.

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

Phase 13: no migration. API projections expose persisted intervals, aggregate attempts, critical path, actual usage with coverage, artifacts, findings and delivery. React Flow graphs, timeline inspection, evidence, searchable Project Brain, diffs, actor metrics, run comparison and themes pass browser checks against active and fully delivered fixtures. Provider and external artifacts share bounded hash capture. Full backend suite: 96 passed; strict checks and frontend build/lint passed. Phase 14 now addresses execution interruption, descendant cleanup and recovery.


Phase 14 release verification: 117 tests passed without skips against PostgreSQL/Docker
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

Canonical numbered documents, handoff and sign-off are preserved exactly. The current Ruff
version formats Markdown Python blocks, so signed-off inputs are excluded from formatting;
README only adds links to implementation documentation. MANIFEST.json remains the original
input manifest, not a release artifact manifest.


## V1 release checkpoint

Version 1.0.0 is locally runnable. All 15 canonical implementation phases have a coherent
working implementation and recorded validation. The final tree retains the signed-off
architecture and adds no competing runtime/session models.

Final checks: Ruff lint/format, strict mypy (Windows and Linux), staged diff/whitespace
review, migration compatibility, packaged wheel/source contents, standalone installation,
database upgrade/doctor, three frontend unit tests and two real browser scenarios.
The full backend baseline passed 117 tests with no skips; subsequent focused runs verified
the final migration, worktree-context, provider replay and task-order changes. The suite now
contains 118 tests. Evidence summary: [verification/v1.0.0.json](verification/v1.0.0.json).

Known operational boundaries are in [RELEASE_NOTES.md](RELEASE_NOTES.md): live provider
credentials were unavailable; embedding adapters are optional; remote hosting is disabled;
manual criteria do not auto-pass; external CLI hosts use a contract while native assistants
use MCP. Linux runtime CI is configured but has not been run on a hosted CI service.
There are no remaining implementation blockers for the locally validated V1 scope.

## Usage guide

Added root [GUIDE.md](../GUIDE.md) with Windows/source/wheel setup, provider configuration,
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
GUIDE.md covers npm setup; docs/PUBLISHING.md covers tarball checks and publication.
Python package metadata now uses a product README instead of the canonical handoff README.

Validation: launcher unit/contract tests, real Windows npm tarball installation with
--ignore-scripts, isolated runtime setup, version/JSON/error-code/module-isolation smoke,
frontend tests/build/lint, ESLint/Prettier, Ruff and strict typing for release scripts.
The package CI workflow builds one tarball and installs it on Windows/Linux/macOS.
Hosted cross-platform CI has not run in this workspace. The previous full backend
validation remains applicable; this slice changes distribution, not Core behavior.

No architectural deviation or migration. MIT was selected by the release owner.
Actual registry publication is pending account/name ownership and release-owner action.
No publishing token, remote URL or public release was created.
