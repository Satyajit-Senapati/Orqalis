# Orqalis npm release readiness

<a id="candidate-210---local-preparation-on-2026-10-03"></a>

## Published 2.1.0 - 2026-10-09

**Published and verified as npm's `latest`, with the accepted cold-rebuild tradeoff.**
Main was merged, and immutable `v2.1.0` points to `19865786a0280e6875902fe2d4dbe9d02975cc23`.
[GitHub release](https://github.com/Satyajit-Senapati/Orqalis/releases/tag/v2.1.0),
[npm package](https://www.npmjs.com/package/orqalis/v/2.1.0) and
[publication receipt](quality/evidence/release-publication-closeout-2.1.0-20261009-v1.json) record the completed release.
Exact-source hosted quality passed 913 Python tests with 22 explicit skips and no
failures; browser checks passed 13 with one explicit skip. The published artifact
passed Linux/Windows/macOS launcher smoke and 17 Linux installed integration checks,
including 41 MCP tools. Public registry download and GitHub release asset match the
publication-workflow artifact byte for byte. The release-owner environment review
and Valid npm Trusted Publisher binding were checked before publication.

## Original local qualification and preparation

The original locally qualified application `01d45811de37528691a2d12fc16e1a677f1b1b57ecf407e9754955581420cc42`
retains its original whole30/31 qualification against the 394-input freeze
`a0fb5b8621152ba43673947503667e5969a3cb8ecc234075b3409be86553e038`.
After the first push, hosted Linux typing found Windows-only API references in three
benchmark helpers. The focused portability correction changes those three helper inputs
only; application/tests/workflows/dependencies are unchanged. The
[successor input map](quality/evidence/release-input-freeze-portable-scripts-20261009-v1.json)
and [Linux/macOS/Windows static checks](quality/evidence/release-hosted-portable-script-checks-20261009-v2.json)
record the fix without rebinding earlier benchmark or full-suite evidence. Fresh hosted
CI on the final release source passed; the publication receipt above records its exact revision. The initial quality run also lacked the
pinned immutable-contract baseline in its shallow checkout. Quality now fetches full
history, with both affected fixture tests passing locally and all assertions preserved.
[Latest input binding](quality/evidence/release-input-freeze-hosted-history-20261009-v1.json)
records this workflow-only correction plus the three helper fixes; original full-suite
and timing evidence keeps its original bindings.
Atomic writes verify bytes through the owned temporary descriptor and check identity
before replacement. Original durability, retry and recovery contracts remain.
The frontend advisory is resolved by the dev-only source-map-js1.2.2 update.

[Engineering status](quality/ENHANCEMENT_STATUS.md) owns findings, retained failures
and tradeoffs. The [worklist](quality/NEXT_SESSION.md) owns remaining local work;
this document owns release-owner gates. Historical captures retain their original
source identities and do not substitute for the published release's hosted qualification.

## Current evidence and gates

| Gate | Current disposition |
| --- | --- |
| Source/input/helper identities | Published tag at `19865786a0280e6875902fe2d4dbe9d02975cc23`; original Source01/inputa0 local records retain their capture bindings |
| Python regression | Exact-release hosted:913 PASS/22 explicit SKIP/0 FAIL; original local whole30/31 each:933 PASS/2 explicit SKIP/0 FAIL/ERROR |
| Browser/static/advisories | Exact-release hosted:13 browser PASS/1 explicit SKIP; strict typing291 files and frontend9 test files PASS; original local static/advisory checks retain their bindings |
| Installed wheel/npm | Current installed17/MCP41, exact installed dependency audits, archive/source/frontend review PASS; final prose checked in the linked packaging records |
| Heldout/history | Fixed263-file graph/gold/delta checks and1,001-row/33-page history PASS; larger-corpus cold cost accepted for2.1.0 and deferred to the next release |
| Paired quality/execution/memory/UI/constrained | Both timed rounds PASS with all30 reviewed quality tradeoffs retained; execution medians25.810/20.452s against pooled all-nine55.870s; bounded local acceptance with cold exception; broader per-ID evaluations remain pending |
| Master sections53/54 | Two exact-source complete local qualifications accepted WITH the user-approved cold-performance exception; broader23 IMPLEMENTED_PENDING_EVAL /13 DEFER remain; no clean/global convergence claim |
| Documentation/distribution | Canonical docs retained; final-prose artifact, archive/installed payload and link records linked below |
| Hosted platform gates | PASS on exact released artifact: Linux/Windows/macOS launcher checks and Linux installed17/MCP41 |
| Publication | PUBLISHED: user authorization, owner environment review, Valid Trusted Publisher, provenance and exact registry-download identity recorded |

## Preparation evidence and retained acceptance boundaries

Do not select the slow baseline to accept execution timing. Preserve all failed captures,
raw quality losses and measured costs. Any production change requires refreshed
source-bound qualification; prose alone does not require another full functional run.
Paid/live models, native assistant harnesses and live Docker remain unqualified. Hosted
Linux quality/integration and Windows/macOS launcher smoke now have native evidence;
those checks do not certify every native feature or workload.

The candidate's final-prose checks are recorded in [the serial pipeline](quality/evidence/release-owned-temp-final-docs-actual-v7.json),
[artifact identity](quality/evidence/release-final-artifact-identity-owned-temp-release-docs-v3.json),
[archive/installed parity](quality/evidence/release-owned-temp-archive-payload-checks-v3.json)
and [local links](quality/evidence/release-owned-temp-final-docs-actual-v7.json).
Runtime smoke reuse requires exact bytes, sizes and archive modes. Repository-only
quality docs are excluded from npm. Packaging validates the tested candidate; final
release acceptance retains the explicit user-approved cold-cost exception. Documentation consolidation supersedes the old local package prose snapshot. The released
artifact was rebuilt and checked from the exact committed LF tree before publication;
old local tarballs remain historical evidence only and were removed during cleanup.

The user authorized merge and publication on 2026-10-09. Exact-source hosted quality
and all artifact gates passed before the owner approved `npm-release`. OIDC published
the tested tagged artifact. Published versions and tags remain immutable; future releases
follow [PUBLISHING.md](PUBLISHING.md).

## Historical release evidence


These records describe the versions and dates they tested, not current candidate gates.
Standard operation is repo-local and requires no PostgreSQL service or DATABASE_URL.
No SQL compatibility extra, migration command or legacy exporter belongs in this package.

| Historical record | Preserved authority |
| --- | --- |
| 2.0.0 local-first preparation and artifact checks | [Consolidated cleanup record](#historical-200-cleanup-record), [release notes](RELEASE_NOTES.md#orqalis-200-historical-pre-publication-validation) |
| 1.0.x acceptance matrix, findings, totals and publication records | [Original JSON: all 106 requirements](verification/npm-release-readiness.json) |
| Published 1.0.1 identity, CI and registry-installed verification | [Publication record](RELEASE_NOTES.md#publication-record) |
| Historical 1.0.1 updater, terminal hosting and SQL migration `6b93c20e21af` | [Versioned release notes](RELEASE_NOTES.md#orqalis-101-historical-published-artifact), [compatibility boundary](PUBLISHING.md#historical-database-compatibility) |

Earlier unpublished patch-candidate hashes are not the published 1.0.1 artifact.
Historical `latest`, account and registry observations remain date-qualified; they do
not establish today's registry state. Future commands belong in PUBLISHING, not a
historical readiness appendix. Current filesystem upgrade guidance is in
[Operations](OPERATIONS.md#data-ownership-and-backup).

## Historical 2.0.0 cleanup record

Consolidated from the 2026-09-17 repository cleanup audit; all observations below describe
that pre-publication candidate. They do not establish current registry or CI state.

The migration removed 38 tracked files: three obsolete root/configuration files, 32 SQL
persistence/migration files and three database-only tests/fixtures. SQLAlchemy, Alembic,
psycopg and pgvector plus unused transitives were removed. Storage-neutral ports,
filesystem services and migrated behavior tests were retained. Generic database-edit
skills remain useful for user repositories; no database runtime, exporter or compatibility
extra was introduced. Entry points for CLI, npm, init/run, UI/API and MCP all composed
root-bound filesystem services. The completed phase sequence and impact matrix remain
in [implementation status](IMPLEMENTATION_STATUS.md#local-first-persistence-redesign---2026-09-16).

The original 425-test baseline passed 424 with one optional Docker skip. Final collection
was 430 after publication and process-ownership regressions were added; focused final
reruns and isolated installed verification passed. Ruff/typing, frontend lint/33 tests,
production build and npm checks/29 tests passed. The npm archive contained 69 allowlisted
entries and passed cold/cached setup plus CLI/MCP/API/WebSocket/UI/root-isolation checks.
No project data, credentials, retired SQL runtime or database bootstrap was included.

| Historical artifact | SHA-256 |
| --- | --- |
| Python wheel 2.0.0 | `7e6129fc2f167c644a5e882bfacc208dfd3521a197505eec0eb6b4e2d7cd2fb0` |
| npm tarball 2.0.0 | `2161403a190034585f07de473530ec1b93ff4194aa745e062e6bb43cd4de8a88` |

The archive npm shasum was `b75c400eb6963cb4a31fc30b1becde541adeb44a`, with
1,907,436 unpacked bytes and 1,544,012 package bytes. At that capture, npm latest was
1.0.1, local npm was unauthenticated and publication remained pending. The v2.0.0 tag
and registry now identify the shipped version; the dated local audit is not its
publication receipt. Final hygiene then removed 278 ignored cache roots/2,007 generated
files and the frontend build-info file. Current generated-output policy is in
[development](DEVELOPMENT.md) and the repository ignore rules.
