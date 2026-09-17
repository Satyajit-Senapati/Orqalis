# Orqalis npm release readiness

## Current local-first release gate - 2026-09-16

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project owns its project intelligence and execution history through a structured `.orqalis/` directory located in the repository root. External database infrastructure is not required for standard operation.

This section supersedes the setup assumptions in the historical 1.0.0/1.0.1 evidence below.
The dated results are intentionally retained unchanged as evidence for the artifacts that
were actually tested; mentions of PostgreSQL, pgvector, Docker and database environment
variables in that historical appendix are **not** current standard-runtime requirements.

The current candidate must pass, without a database service or `DATABASE_URL`:

- clean npm pack/install and first-run bootstrap;
- `orqalis init`, status and doctor in a temporary Git repository;
- Task Capsule creation, event/snapshot restart and historical retrieval;
- filesystem atomicity, locking, schema migration and read-only failure tests;
- project-root and simultaneous-assistant isolation;
- memory provenance/freshness/staging/secret tests;
- graph incremental/cache/delete/rename/dirty/branch tests and derived-index recovery;
- CLI, MCP, API, WebSocket and Control Center regressions;
- Python lint/format/strict typing/tests, web lint/test/build and npm launcher checks; and
- tarball inspection proving no Compose/database bootstrap or project `.orqalis/` data.

Final local-first release evidence passed after the persistence, filesystem-migration,
read-only-store, worktree-context and curated-memory authority corrections. Python collected
425 tests (424 passed; one opt-in Docker sandbox test skipped without an image), the Control
Center passed 33 tests plus lint/build, and the npm wrapper passed 29 tests plus syntax,
lint and formatting. The exact rebuilt 2.0.0 tarball then passed isolated cold/cached launch
and the installed CLI, project-store, Task Capsule, context/memory, 26-tool MCP, API,
WebSocket and packaged-Control-Center verifier outside the checkout. Exact hashes are in
`REPOSITORY_CLEANUP_AUDIT.md`.

The Docker sandbox test is a separate opt-in check. The current package contains no SQL
compatibility extra, database migration command or legacy exporter.

Candidate version: `2.0.0` (unpublished). Public npm `latest` remains the immutable,
historical database-backed `1.0.1` artifact until an authorized release owner publishes
this candidate.

### Final publication preparation - 2026-09-17

The existing `npm-package.yml` workflow now keeps packaging, platform smoke,
installed-application verification and publication in one artifact chain. Publication is
disabled by default and is available only for an explicit `workflow_dispatch` with
`publish=true` on a version tag, after both smoke jobs pass. The job uses the protected
`npm-release` environment, npm Trusted Publishing, job-scoped `id-token: write`, pinned
npm 12.0.2, exact-artifact name/version/tag checks and provenance. It contains no npm token
or automatic tag-push publication path.

Public registry inspection found `orqalis@1.0.0` and `orqalis@1.0.1`, with `1.0.1` as
`latest`; `orqalis@2.0.0` remains unused. The expected maintainer is `satyajit-pro`.
The local release environment is not authenticated to npm, and npm's private
Trusted-Publisher relationship plus the GitHub `npm-release` environment cannot be
confirmed without release-owner access. Those are external publication controls, not
repository verification failures. No npm publication was attempted.

## Historical 1.0.x verification appendix

Everything below this heading records the published database-backed 1.0.x candidates and
must be read in that historical context.

**Historical public latest: [orqalis@1.0.1](https://www.npmjs.com/package/orqalis/v/1.0.1)**
(`latest` at the time of this candidate audit)

The current publication and artifact record is [below](#public-101-publication---2026-09-15).
The original matrix remains the historical 1.0.0 readiness audit.

**Historical release: [orqalis@1.0.0](https://www.npmjs.com/package/orqalis/v/1.0.0)**

Historical pre-publication audit decision: **READY FOR NPM PUBLISH**.

Audit date: 2026-09-14. Version: 1.0.0. Public identity: `orqalis`.

Source baseline: `c0ff0ded46c35d8e044147553a2d13baaff00d20`, branch `main`, repository `Satyajit-Senapati/Orqalis`. Canonical v1.2 requirements were read completely before changes; software release version is 1.0.0. ADR 0001 bounds the deterministic V1 execution DAG; ADR 0002 defines npm as the sole application distribution channel.

### Historical 1.0.0 publication update - 2026-09-14

The public npm registry records version 1.0.0 as published at 09:12:43.151 UTC,
with `latest` pointing to 1.0.0. Its SHA-1 digest and SHA-512 integrity match the
reviewed tarball below. Package publication is complete; install with:

```sh
npm install -g orqalis
orqalis --version
```

A fresh global-prefix installation of `orqalis@1.0.0` from the public registry passed
on Windows x64 (Node 24.16.0, Python 3.12.14). Cold and cached launch, the global
`--version`/`--help` commands, JSON output, invalid-command exit status and hostile
current-directory isolation all passed using `scripts/smoke_npm.py`. The temporary
prefix and runtime were outside the source checkout. Results are retained in the
[publication record](verification/npm-release-readiness.json).

The requirement matrix and test totals below preserve the pre-publication audit.
Earlier E404/ENEEDAUTH observations describe that audit, not current availability.
Subsequent releases require an unused version and the gates in [PUBLISHING.md](PUBLISHING.md).
The current [installation guide](../README.md#install-and-start) is maintained
in Git; the already-published 1.0.0 archive remains unchanged.

## Pre-publication gate

NOT_APPLICABLE: 1, PASS: 105. Total: 106.

No public npm publication had been performed when this audit was captured. External account checks were separated from repository-controlled acceptance. PASS means recorded execution/source evidence; PARTIAL means some required evidence remains; BLOCKED means a prerequisite/check remains outstanding. NOT_APPLICABLE excludes an external gate from software readiness, without waiving publication authorization.

## Release candidate

```json
{
  "version": "1.0.0",
  "package_name": "orqalis",
  "packed_size": 1489198,
  "unpacked_size": 1882257,
  "npm_file_count": 58,
  "wheel_file_count": 180,
  "wheel_size": 403089,
  "sha256": "699364407e1c86d78424186e87c695347859a2f89909b9d586676fa79322e7d2",
  "integrity": "sha512-5OkgN07xQHeyYC8iG+UHYgNeg7n8gM3vDVikJKYauBqITsem6CUqg/LjB82+pavKVP1NL3TBIeigt3XA7r2ryw==",
  "artifact": "dist/orqalis-1.0.0.tgz",
  "platforms": "Windows, Linux and macOS: hosted tarball smokes PASS; Linux installed Core/MCP/UI PASS; win32-x64 full local installed workflows/browser PASS. Node22/Linux+Python3.12, Node24/Windows+Python3.12, Node24/macOS+Python3.14. Other CPU/runtime combinations unclaimed."
}
```

## Hosted CI

Release source commit: `c223af5b9cbb35eb2be48699d67d7ce5e8a77779`. Final audit-only follow-ups are excluded from the npm artifact.

- [quality](https://github.com/Satyajit-Senapati/Orqalis/actions/runs/34819956866): SUCCESS.
- [npm package](https://github.com/Satyajit-Senapati/Orqalis/actions/runs/34819956822): SUCCESS.


## Validation record

- **backend baseline: PASS** - passed=127; failed=0; skipped=0; seconds=487.89; evidence=.tools/release-audit-20260914/backend-baseline.xml; warning=Existing Starlette/AnyIO deprecation.
- **memory remediations: PASS** - passed=27; failed=0; skipped=0; seconds=24.78; evidence=.tools/release-audit-20260914/memory-regressions.xml.
- **interface regressions: PASS** - passed=45; failed=0; skipped=0; evidence=.tools/release-audit-20260914/interface-regression.log.
- **external finding final targeted: PASS** - passed=15; failed=0; skipped=0; seconds=156.13; evidence=.tools/release-audit-20260914/interface-findings-final.log.
- **Python quality: PASS** - evidence=.tools/release-audit-20260914/python-quality.log; detail=Ruff225 files formatted; strict mypy207 source/tests and3 scripts PASS.
- **npm quality: PASS** - passed=16; failed=0; skipped=0; evidence=.tools/release-audit-20260914/npm-quality.log; detail=Syntax, ESLint and Prettier pass.
- **backend loop1: PASS** - passed=210; failed=0; skipped=0; retries=0; seconds=626.05; coverage_percent=85; evidence=.tools/release-audit-20260914/backend-loop1.xml.
- **final frontend unit/lint/type/production: PASS** - passed=28; failed=0; skipped=0; retries=0; evidence=.tools/release-audit-20260914/frontend-final.log.
- **final source quality: PASS** - detail=Ruff225 files formatted; strict mypy207 source/tests and3 scripts PASS; evidence=.tools/release-audit-20260914/python-quality.log.
- **dependency and source secret audit: PASS** - detail=npm80/294 deps and Python67 deps0 vulnerabilities;323 intended files0 actual secrets; evidence=.tools/release-audit-20260914/packaging-security-summary.json.
- **actual npm tarball and safe publish dry-run: PASS** - detail=58 files,135 local links,29 anchors; exit0; digest unchanged; no public publish; evidence=.tools/release-audit-20260914/package-final-inspection.json; sha256=699364407e1c86d78424186e87c695347859a2f89909b9d586676fa79322e7d2.
- **final backend: PASS** - passed=221; failed=0; skipped=0; retries=0; seconds=767.3; coverage_percent=87; warning=One existing upstream Starlette/AnyIO deprecation; evidence=.tools/release-audit-20260914/backend-final.xml.
- **installed production browser: PASS** - passed=11; failed=0; skipped=0; flaky=0; seconds=48.286; evidence=.tools/release-audit-20260914/installed-browser.json; detail=Two delivered installed-SDK runs: first pass and targeted repair. Desktop1440px, short1024x500 sidebar, mobile390px, keyboard, dark-only, reduced motion, reconnect and degraded requests.
- **exact candidate cold/cached installed CLI: PASS** - evidence=.tools/release-audit-20260914/installed-final.log; detail=win32-x64 Node24.16.0, Python3.12.14; final external prefix/runtime; --version/help, JSON, expected exit codes and CWD isolation.
- **final installed application: PASS** - checks=16; mcp_tools=19; evidence=.tools/release-audit-20260914/installed-integration.json; detail=Actual cold ui under hostile CWD, idempotent reuse, API/assets/routes, real MCP, event replay/reconnect and owned process shutdown.
- **installed verifier regression: PASS** - passed=13; failed=0; skipped=0; evidence=.tools/release-audit-20260914/installed-ownership-checks.json.
- **final independent Change Guardian: PASS** - detail=Cross-review: interface reviewer approved foreign core/security/memory changes; core reviewer approved foreign interface/package/parent-doc/CI changes. No implementer acted as own final reviewer.
- **final intended-tree secret scan: PASS** - files=324; actual_secrets=0; reviewed_candidates=21; evidence=.tools/release-audit-20260914/secret-scan-final.json.
- **hosted exact-source release gates: PASS** - detail=quality and npm package workflows SUCCESS; all platform smokes and Linux installed integration SUCCESS; source_commit=c223af5b9cbb35eb2be48699d67d7ce5e8a77779; evidence=https://github.com/Satyajit-Senapati/Orqalis/actions/runs/34819956822.
- **audit-owned resource cleanup: PASS** - detail=Verified server processes exited; removed external prefixes/runtimes/fixture repositories and labelled disposable database container; main is the only worktree; evidence=.tools/release-audit-20260914/cleanup.json.

## Findings and remediation

| ID | Severity | Issue | Applied correction | Files | State |
| --- | --- | --- | --- | --- | --- |
| F01 | P0 | Cold UI server child could import a hostile current-directory orqalis.py | Preserve Python -I when ensure_server launches Core | src/orqalis/api/hosting.py; tests/unit/test_interface_release.py; scripts/verify_installed.py | FIXED; targeted and complete relevant regression passed |
| F02 | P1 | Nested opaque credential keys and embedded auth headers escaped redaction | Normalize sensitive key names and redact complete credential values while preserving usage counters | src/orqalis/security/redaction.py; src/orqalis/providers/validation.py; tests/unit/test_security.py | FIXED; targeted and complete relevant regression passed |
| F03 | P1 | OpenAI strict output rejected ordinary Pydantic goal/tool schemas | Transport-only strict schema normalization plus original local validation | src/orqalis/providers/openai_schema.py; tests/unit/test_openai_schema.py | FIXED; targeted and complete relevant regression passed |
| F04 | P2 | Python skills unused by default planner and language case mismatch | Infer capabilities only from explicit task scope; preserve during repair; casefold language applicability | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/skills/registry.py; tests/unit/test_planner_skills.py | FIXED; targeted and complete relevant regression passed |
| F05 | P1 | Broad write policy could allow unrelated changes beyond explicit goal paths | Independent Guardian intersects explicit goal file scope and execution write policy | src/orqalis/delivery/guardian.py; tests/unit/test_guardian.py | FIXED; targeted and complete relevant regression passed |
| F06 | P1 | Unmerged run memory could influence main; post-limit filtering could crowd valid facts | Validate source commit ancestry and refill retrieval after SQL exclusions | src/orqalis/memory/service.py; src/orqalis/persistence/memory.py; tests/integration/test_memory_release.py | FIXED; targeted and complete relevant regression passed |
| F07 | P2 | Domain/known issues categories and several build manifests were absent; same-HEAD index changes stayed stale | Deterministic categories/manifests and versioned indexer/embedding fingerprints with one-time refresh | src/orqalis/memory/indexing.py; src/orqalis/memory/service.py; tests/unit/test_memory_indexer.py | FIXED; targeted and complete relevant regression passed |
| F08 | P1 | Memory omitted only some private-key types | Use complete private-key/diagnostic privacy exclusion before excerpting | src/orqalis/memory/indexing.py; tests/unit/test_memory_indexer.py | FIXED; targeted and complete relevant regression passed |
| F09 | P2 | Missing CLI --version/catalog commands and MCP version/tool gaps | Add typed discovery commands, consistent MCP version and advisory finding report contract | src/orqalis/cli; src/orqalis/mcp; tests/unit/test_cli_release.py; tests/integration/test_mcp.py | FIXED; targeted and complete relevant regression passed |
| F10 | P1 | Externally reported source findings could be resolved by unrelated evidence or stale source checks | Require independently observed matching source assertions and final-tree revalidation; matching FileValidation evidence supports deletion and every relied-on criterion is required at final delivery | src/orqalis/execution/finding_review.py; src/orqalis/delivery/validation.py; tests/integration/test_external_findings.py | FIXED; targeted and complete relevant regression passed |
| F11 | P2 | Relative OS cache variables placed executable runtime under invoking project | Require absolute OS cache roots; use user-home fallback | packages/npm/lib/runtime.js; packages/npm/test/runtime.test.js | FIXED; targeted and complete relevant regression passed |
| F12 | P1 | Source edits after preparation could ship a stale Python wheel | Bind exact source inventory plus build inputs and reject changes/additions/deletions at prepack | scripts/prepare_npm.py; packages/npm/lib/bundle.js; tests/unit/test_npm_release.py | FIXED; targeted and complete relevant regression passed |
| F13 | P2 | Release audit files could enter npm and require a circular artifact hash | Exclude only the two maintainer readiness records; reject accidental staged copies | scripts/prepare_npm.py; packages/npm/lib/bundle.js | FIXED; targeted and complete relevant regression passed |
| F14 | P2 | API advertised context bounds different from Core | Align task length1..10000 and max_chars1000..200000; test valid extremes and rejected bounds | src/orqalis/api/app.py; tests/unit/test_interface_release.py; tests/integration/test_api.py | FIXED; targeted and complete relevant regression passed |
| F15 | P2 | Temporary embedding outage left missing vectors indefinitely at unchanged HEAD | Bounded recovery from stored content; stop on outage, retain progress, isolate model/dimensions; no Git rereads | src/orqalis/memory/service.py; src/orqalis/memory/ports.py; src/orqalis/persistence/memory.py; tests/integration/test_memory_release.py | FIXED; targeted and complete relevant regression passed |
| F16 | P2 | Installed verifier assumed a direct Windows listener and snapshot-before-replay ordering | Verify exact managed runtime ancestry; disable fixture hooks/signing; validate replay/live/snapshot/reconnect sequencing | scripts/verify_installed.py; tests/unit/test_installed_smoke.py | FIXED;13 harness tests and all16 actual installed checks PASS |

## Historical requirement matrix

Each row was a canonical product or release acceptance requirement for the recorded 1.0.x artifact. Commands refer to repository-root invocations; its PostgreSQL tests required a disposable database and its Docker sandbox image. Related checks may exercise several rows together. Evidence paths below are retained locally in the ignored audit directory; this committed matrix and its JSON companion preserve historical result summaries.

### Core workflow

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R001 - Deterministic persisted lifecycle and invalid-transition denial | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; tests/integration/test_runtime.py; test_recovery.py; test_cancellation.py; test_repair.py | src/orqalis/core; src/orqalis/domain/run.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R002 - Orchestrator-only workflow control and role separation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; tests/integration/test_runtime.py; test_recovery.py; test_cancellation.py; test_repair.py | src/orqalis/core; src/orqalis/domain/run.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R003 - Restart checkpoints and non-repeatable side-effect receipts | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; tests/integration/test_runtime.py; test_recovery.py; test_cancellation.py; test_repair.py | src/orqalis/core; src/orqalis/domain/run.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R004 - Pause, resume, cancel and terminal-state behavior | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; tests/integration/test_runtime.py; test_recovery.py; test_cancellation.py; test_repair.py | src/orqalis/core; src/orqalis/domain/run.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R005 - Bounded repair escalation to human review | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; tests/integration/test_runtime.py; test_recovery.py; test_cancellation.py; test_repair.py | src/orqalis/core; src/orqalis/domain/run.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Goal and acceptance

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R006 - Explicit goal, scope, constraints and definition of done | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_acceptance.py; tests/integration/test_goals.py; test_requirements.py; test_replanning.py; test_executor.py | src/orqalis/core/goals.py; src/orqalis/evaluation; src/orqalis/execution/review.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R007 - Immutable versioned criteria and explicit goal revisions | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_acceptance.py; tests/integration/test_goals.py; test_requirements.py; test_replanning.py; test_executor.py | src/orqalis/core/goals.py; src/orqalis/evaluation; src/orqalis/execution/review.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R008 - Deterministic command, test, static, file and diff validators | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_acceptance.py; tests/integration/test_goals.py; test_requirements.py; test_replanning.py; test_executor.py | src/orqalis/core/goals.py; src/orqalis/evaluation; src/orqalis/execution/review.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R009 - Independent evidence-backed review and manual-validation behavior | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_acceptance.py; tests/integration/test_goals.py; test_requirements.py; test_replanning.py; test_executor.py | src/orqalis/core/goals.py; src/orqalis/evaluation; src/orqalis/execution/review.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R010 - Pending, testing, pass and fail evidence lifecycle | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_acceptance.py; tests/integration/test_goals.py; test_requirements.py; test_replanning.py; test_executor.py | src/orqalis/core/goals.py; src/orqalis/evaluation; src/orqalis/execution/review.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Planning and execution

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R011 - Typed dependency DAG with cycle and missing-dependency rejection | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; test_planner_skills.py; tests/integration/test_parallel.py; test_repair.py | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/domain/plan.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R012 - Dependency readiness and persisted task attempts | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; test_planner_skills.py; tests/integration/test_parallel.py; test_repair.py | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/domain/plan.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R013 - Bounded parallel context work and serialized writers | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; test_planner_skills.py; tests/integration/test_parallel.py; test_repair.py | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/domain/plan.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R014 - Targeted repair preserving original goal and accepted work | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; test_planner_skills.py; tests/integration/test_parallel.py; test_repair.py | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/domain/plan.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R015 - Task-specific role, capability and skill selection | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_workflow.py; test_planner_skills.py; tests/integration/test_parallel.py; test_repair.py | src/orqalis/core/vertical_plan.py; src/orqalis/core/repair.py; src/orqalis/domain/plan.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Agents and providers

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R016 - Specialized role catalog and least-privilege tool intersection | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R017 - Independent reviewer and Change Guardian | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R018 - Dynamic skill discovery, metadata, version/hash validation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R019 - Irrelevant skills excluded and skill failures fail safely | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R020 - Provider-neutral typed request/result contracts | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R021 - OpenAI Responses adapter and deterministic provider | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Live paid provider/native assistant account calls external; HTTP/MCP contracts, malformed results, failures and deterministic workflows verified |
| R022 - Anthropic adapter and assistant interoperability contract | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Live paid provider/native assistant account calls external; HTTP/MCP contracts, malformed results, failures and deterministic workflows verified |
| R023 - Timeout, cancellation, malformed response and failure handling | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R024 - Reported token usage and optional reliable cost | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_providers.py; test_openai_schema.py; test_anthropic.py; test_planner_skills.py; tests/integration/test_providers.py | src/orqalis/agents; src/orqalis/skills; src/orqalis/providers | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Memory and context

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R025 - Committed bootstrap and repository map | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R026 - Architecture, conventions, ADRs, domain and known-issue categories | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | F07 deterministic category and build-manifest detection, versioned index fingerprints | None identified within signed-off local V1 boundaries |
| R027 - Provenance, confidence, verification, supersession and run attribution | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R028 - Git-aware incremental refresh including recreated repositories | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R029 - No source rereads when HEAD and indexer are unchanged | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R030 - Semantic pgvector retrieval with project/model scope and offline fallback | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | F15 bounded missing-vector recovery from stored content; model/dimension-scoped semantic queries | None identified within signed-off local V1 boundaries |
| R031 - Bounded context packs and explicit inspection gaps | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R032 - Architecture, UI, data, testing, docs and Git retrieval scenarios | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R033 - Controlled accepted-run memory curation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R034 - Branch-aware context excluding unmerged run facts | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | F06 Git ancestry exclusion before query limit and refill | None identified within signed-off local V1 boundaries |
| R035 - Memory privacy and credential exclusion | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_memory_indexer.py; tests/integration/test_memory.py; test_memory_release.py; test_repair.py | src/orqalis/memory; src/orqalis/persistence/memory.py; src/orqalis/git/service.py | None outstanding; applicable remediations are listed in F01-F15 | F08 full-source private-key exclusion before excerpting | None identified within signed-off local V1 boundaries |
### Review and delivery

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R036 - Intentional acceptance failure, diagnosis, repair, retest and pass | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. Installed fake-provider repair run2c436f7a-ac9c-42f5-a2cb-e34c40ac5f29 completed with repair_iteration=1 and commit8127410104c95853bd7ab428531306cf788ef002. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R037 - Repair count, maximum, evidence retention and human escalation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R038 - Guardian rejects out-of-scope, config, dependency, deletion and secret changes | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | F05 explicit goal file paths intersect immutable execution permissions | None identified within signed-off local V1 boundaries |
| R039 - Documentation after acceptance and final-tree revalidation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. Installed first-pass and repair deliveries updated README, passed Guardian/final validation, and created traced commits. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R040 - Safe temporary-repository initialization and dirty-source preservation | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R041 - Branch-aware gated commit and detailed run/evidence message | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R042 - Idempotent commit attachment and permitted local-test-remote push | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R043 - Protected branch, force-push, destructive reset and permission denial | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_guardian.py; test_git.py; tests/integration/test_executor.py; test_repair.py; test_external_findings.py; test_mcp.py | src/orqalis/delivery; src/orqalis/execution; src/orqalis/git | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Telemetry and timing

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R044 - Canonical Run/GoalVersion/AcceptanceCriterion/Task/TaskExecution records | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R045 - Canonical ActorSession/PhaseExecution/Event/Evidence/Finding/Artifact records | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R046 - Single append-only sequenced Event and Orchestrator actor | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R047 - Transactional event/state persistence, replay and concurrency | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R048 - Run and phase wall/active/waiting/blocked timing | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R049 - Task created/ready/start/end/queue/attempt timing | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R050 - Actor working/waiting/blocked/utilization timing | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R051 - Nonnegative finite durations and overlap-safe analytics | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/unit/test_activity.py; test_analytics.py; test_instrumentation.py; tests/integration/test_runtime.py; test_parallel.py; test_api.py | src/orqalis/domain; src/orqalis/persistence; src/orqalis/observability | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Control Center

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R052 - Production-hosted UI and bundled static assets | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R053 - Real orchestrator/sub-agent statuses, tasks, skills and timers | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R054 - Deterministic plan completion, phase, acceptance, blockers and repair | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R055 - Agent inspector context, history, files, artifacts, tools and usage | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R056 - DAG dependencies, parallel branches, repair paths and responsible roles | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R057 - Timeline persisted sequential/parallel/wait/blocked/repair intervals | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R058 - Acceptance validator, evidence, failure and repair linkage | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R059 - Project Brain freshness, indexed commit, decisions and history | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R060 - Actual runtime, provider, token and optional cost metrics | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R061 - Workspace/project/sidebar interaction at desktop and mobile widths | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R062 - Pitch-dark-only theme, keyboard accessibility and reduced motion | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R063 - Refresh, direct routes, reconnect and duplicate-event handling | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R064 - No secrets or private chain-of-thought displayed | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web against installed production UI | web/src; src/orqalis/api; web/e2e | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
### Interfaces

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R065 - REST documented schemas and shared Core services | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R066 - Malformed requests, invalid IDs, missing resources and privacy-safe errors | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R067 - API controls, origin/loopback policy and concurrent event projection | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R068 - Actual MCP stdio startup, protocol version and shared state | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R069 - MCP context, goal, plan, assignment, reporting, review and finalization | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | F09/F10 untrusted finding receipts, independent source/evidence review and post-documentation revalidation, including deletions and optional relied-on criteria | None identified within signed-off local V1 boundaries |
| R070 - MCP project isolation, server-owned permissions and read resources | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | F09/F10 untrusted finding receipts, independent source/evidence review and post-documentation revalidation, including deletions and optional relied-on criteria | None identified within signed-off local V1 boundaries |
| R071 - CLI --version, --help and database-independent discovery | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R072 - CLI project/run/goal/memory/context/agent/skill/config commands | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R073 - CLI invalid arguments, useful exit codes and safe error text | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | tests/integration/test_api.py; test_mcp.py; test_external_findings.py; tests/unit/test_cli_release.py; test_interface_release.py | src/orqalis/api; src/orqalis/cli; src/orqalis/mcp; src/orqalis/core/external.py | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
### Persistence and quality

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R074 - Fresh PostgreSQL/pgvector migration bootstrap | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | pytest; ruff check .; ruff format --check .; mypy; mypy --strict scripts; npm test/run lint/run build --prefix web; uv build --wheel | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R075 - Upgrade/downgrade/re-upgrade and model/schema equivalence | PASS | Final backend221 passed,0 failed,0 skipped,0 retries;87% coverage; backend-final.xml plus source/contract review. Latest memory and finding regressions are included. | pytest; ruff check .; ruff format --check .; mypy; mypy --strict scripts; npm test/run lint/run build --prefix web; uv build --wheel | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified within signed-off local V1 boundaries |
| R076 - Complete backend unit/integration/API/CLI/MCP suite | PASS | Local product/backend full suite221 passed (87% coverage), plus all13 added maintainer verifier regressions; all234 Python tests included in the successful hosted full suite;0 local failures/skips/retries | ORQALIS_TEST_DATABASE_URL=<disposable pgvector DB> ORQALIS_TEST_SANDBOX_IMAGE=pgvector/pgvector:pg17 python -m pytest --cov=orqalis --junitxml=backend-final.xml | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | See resolved findings below; final gate incomplete | Regression-backed corrections recorded below | None identified within signed-off local V1 boundaries |
| R077 - Frontend unit tests and production browser end-to-end suite | PASS | Installed production UI:11 Playwright passed,0 failed/skipped/flaky (48.3s); web/e2e contracts plus28 frontend unit tests; installed-browser.json; desktop/mobile screenshots visually inspected | npm test --prefix web; npm run test:e2e --prefix web -- --reporter=line,json with actual installed fixture IDs and server URL | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | No application defect found in final browser sweep | Existing dark-only responsive components verified against actual installed Core | Native browser coverage is Chromium/Chrome; other engines unclaimed |
| R078 - Python Ruff lint/format and strict type checks | PASS | Final python-quality.log: Ruff225 files, strict mypy207 source/tests+3 scripts PASS; scripts also typechecked for Linux | pytest; ruff check .; ruff format --check .; mypy; mypy --strict scripts; npm test/run lint/run build --prefix web; uv build --wheel | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R079 - Frontend ESLint, TypeScript and production build | PASS | frontend-final.log: ESLint, TypeScript/Vite production build and28 Vitest tests PASS; hosted quality repeats them | pytest; ruff check .; ruff format --check .; mypy; mypy --strict scripts; npm test/run lint/run build --prefix web; uv build --wheel | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R080 - Frozen dependency installation and current lockfiles | PASS | uv sync --frozen, frozen npm ci in both package trees locally/hosted; lockfiles unchanged, uv pip check68 installed packages compatible | uv sync --frozen; npm ci --prefix web; npm ci --prefix packages/npm; uv pip check | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R081 - Internal wheel metadata, migrations, UI and license build | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | pytest; ruff check .; ruff format --check .; mypy; mypy --strict scripts; npm test/run lint/run build --prefix web; uv build --wheel | src/orqalis/persistence; migrations; pyproject.toml; web/package.json; scripts | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
### Security and dependencies

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R082 - Tracked-file secret/private-state scan with redacted findings | PASS | secret-scan-final.json:324 intended files,315 text+9 intended images;21 reviewed defaults/synthetic candidates;0 actual secrets | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Point-in-time advisory/heuristic scan; no unresolved finding |
| R083 - Package-content secret/private-state scan | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R084 - Command injection, argument and environment boundaries | PASS | Source/contract review; backend loop1:210 passed,0 failed,0 skipped; latest targeted finding15, API/CLI24 and memory38 checks passed. See validation record for exact logs. | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R085 - Filesystem traversal, symlink/hardlink and deletion safeguards | PASS | Source/contract review; backend loop1:210 passed,0 failed,0 skipped; latest targeted finding15, API/CLI24 and memory38 checks passed. See validation record for exact logs. | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R086 - Docker resource/network/read-only policy and process-tree cleanup | PASS | Source/contract review; backend loop1:210 passed,0 failed,0 skipped; latest targeted finding15, API/CLI24 and memory38 checks passed. See validation record for exact logs. | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R087 - Safe provider/tool/memory/event redaction | PASS | Source/contract review; backend loop1:210 passed,0 failed,0 skipped; latest targeted finding15, API/CLI24 and memory38 checks passed. See validation record for exact logs. | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | None identified in the tested local V1 scope |
| R088 - npm dependency security audit | PASS | packaging-security-summary.json: npm80/294 dependencies, Python67 locked dependencies,0 known vulnerabilities/0 skips; intended323 files scanned with0 actual credentials | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Point-in-time advisory/heuristic scan; no unresolved finding |
| R089 - Python locked-dependency vulnerability audit | PASS | packaging-security-summary.json: npm80/294 dependencies, Python67 locked dependencies,0 known vulnerabilities/0 skips; intended323 files scanned with0 actual credentials | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Point-in-time advisory/heuristic scan; no unresolved finding |
| R090 - Runtime/dev dependency separation, duplication and license review | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | tests/unit/test_security.py; test_execution_tools.py; tests/integration/test_sandbox.py; npm audit --json; pip-audit exact uv.lock export | src/orqalis/security; src/orqalis/tools; src/orqalis/execution; packages/npm; uv.lock; web/package-lock.json | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
### Distribution

| ID / Requirement | Status | Evidence | Test / command | Affected files | Issue found | Fix applied | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R091 - Public npm metadata, intended identity, URLs, bin and engines | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R092 - Consistent npm/Python/CLI/API/MCP/UI release version | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R093 - Node/Python prerequisites and first-launch assumptions | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R094 - Hash-locked binary dependencies and isolated runtime bootstrap | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R095 - Setup concurrency, failures, upgrades and cache behavior | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R096 - Every npm pack dry-run path and size reviewed | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R097 - Actual final npm tarball and integrity digest | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R098 - Clean global-prefix install outside source repository | PASS | Final exact tarball installed with npm -g --prefix in OS temporary directory outside checkout; installed-final.log cold/cached version/help/JSON/invalid-command/CWD isolation all PASS | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None | Fresh external global prefix and managed runtime tested | Global user default npm prefix unchanged; registry account setup remains external |
| R099 - Installed --version, --help, doctor and invalid-command smoke | PASS | Final exact tarball installed with npm -g --prefix in OS temporary directory outside checkout; installed-final.log cold/cached version/help/JSON/invalid-command/CWD isolation all PASS | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None | Fresh external global prefix and managed runtime tested | Global user default npm prefix unchanged; registry account setup remains external |
| R100 - Fresh temporary-project init/status/context/memory/run smoke | PASS | installed-integration.json:16 checks PASS using final npm global installation; real migrations/doctor/fresh init/idempotency/status/memory/context/goals/catalogs/MCP/UI/static assets/API/replay/reconnect/verified shutdown. README command and packaged-link checks pass. | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | F16 verifier ownership/replay assumptions corrected; application behavior validated | 13 maintainer harness regressions, exact runtime ancestry and canonical sequenced replay assertions | Registry-based install command requires first publication; exact candidate tarball installed locally. Paid provider/account configuration remains external |
| R101 - Installed production UI/API/WebSocket/direct-route/shutdown smoke | PASS | installed-integration.json:16 checks PASS using final npm global installation; real migrations/doctor/fresh init/idempotency/status/memory/context/goals/catalogs/MCP/UI/static assets/API/replay/reconnect/verified shutdown. README command and packaged-link checks pass. | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | F16 verifier ownership/replay assumptions corrected; application behavior validated | 13 maintainer harness regressions, exact runtime ancestry and canonical sequenced replay assertions | Registry-based install command requires first publication; exact candidate tarball installed locally. Paid provider/account configuration remains external |
| R102 - README getting-started commands exercised against candidate | PASS | installed-integration.json:16 checks PASS using final npm global installation; real migrations/doctor/fresh init/idempotency/status/memory/context/goals/catalogs/MCP/UI/static assets/API/replay/reconnect/verified shutdown. README command and packaged-link checks pass. | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | F16 verifier ownership/replay assumptions corrected; application behavior validated | 13 maintainer harness regressions, exact runtime ancestry and canonical sequenced replay assertions | Registry-based install command requires first publication; exact candidate tarball installed locally. Paid provider/account configuration remains external |
| R103 - GitHub workflow permissions, artifact and platform strategy | PASS | ci-packaging-review.json and successful hosted34819956822: contents:read, no publish step, one tarball across5 jobs; platform and installed integration JSON retained | npm test --prefix packages/npm; npm pack --dry-run; npm pack; scripts/smoke_npm.py; scripts/verify_installed.py | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Automated npm publication is intentionally not configured; manual reviewed-tarball publication requires external account checks |
| R104 - Hosted Windows/Linux/macOS checks for final pushed commit | PASS | Release source c223af5: quality34819956866 and npm package34819956822 SUCCESS; backend/build/browser and all5 artifact jobs passed (build, Windows/Linux/macOS smokes, Linux installed CLI/MCP/UI) | GitHub Actions workflows ci.yml and npm-package.yml; GitHub REST run/job status for exact release source SHA | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding | CI now consumes one built tarball in all platform and installed integration jobs; evidence retained as artifacts | Other CPU architecture/runtime combinations are unclaimed; final audit-only commits do not alter the release artifact |
| R105 - Safe publish dry-run for the exact reviewed tarball | PASS | package-final-inspection.json:58 npm/180 wheel files, all source/UI/build hashes and versions match;135 links/29 anchors valid;0 forbidden or secret files; exact tarball dry-publish exit0 | npm publish ./dist/orqalis-1.0.0.tgz --dry-run --access public --registry=https://registry.npmjs.org/ | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | None outstanding; applicable remediations are listed in F01-F15 | Independent review and regression-backed corrections applied | Hosted platform acceptance recorded separately under R104 |
| R106 - External registry login, ownership, 2FA and publishing permissions | NOT_APPLICABLE | npm view orqalis returned E404; npm whoami returned ENEEDAUTH | npm view orqalis; npm whoami | packages/npm; scripts; .github/workflows/npm-package.yml; docs/PUBLISHING.md | EXTERNAL_CHECK_REQUIRED: account ownership, authentication, 2FA and registry permission | No credentials added; no public publication performed | Release owner must verify external account gates; E404 does not reserve name |

## Final quality totals

```json
{
  "python_product_full_passed": 221,
  "python_maintainer_regression_passed": 13,
  "python_total": 234,
  "frontend_unit_passed": 28,
  "npm_unit_passed": 16,
  "installed_browser_passed": 11,
  "test_total": 289,
  "failed": 0,
  "skipped": 0,
  "flaky_or_retried": 0,
  "installed_application_checks": 16,
  "coverage_percent": 87,
  "warning": "One pre-existing upstream Starlette/AnyIO deprecation; no warning suppressed"
}
```

## V1 boundaries

- Local loopback hosting; remote multi-tenant deployment is outside V1
- Deterministic V1 Developer/Tester/Reviewer DAG with parallel context and serialized writers follows ADR0001
- Manual criteria are never auto-attested; explicit verifiable goal revisions remain user-authorized
- Goal scope intersects policy automatically for wholly explicit file/glob/directory scopes; prose/mixed scopes require independent semantic review
- Semantic retrieval requires a configured embedding adapter; default structured memory remains operational offline
- Native assistant process integration is a provider-host/MCP contract, not an arbitrary command launcher
- Documentation delivery updates an authorized file with accepted-run evidence; richer ADR authoring is task-specific

## First-publication commands (historical)

These commands were recorded before the release owner published 1.0.0. They are retained
as audit context, not instructions to republish that version. For future releases use
[PUBLISHING.md](PUBLISHING.md#publication).

```powershell
npm.cmd login --registry=https://registry.npmjs.org/
npm.cmd whoami --registry=https://registry.npmjs.org/
npm.cmd publish ./dist/orqalis-1.0.0.tgz --access public --registry=https://registry.npmjs.org/
npm.cmd view orqalis@1.0.0 version dist.integrity --registry=https://registry.npmjs.org/
```


## External checks at audit time

- **EXTERNAL_CHECK_REQUIRED:** intended npm login, package-name ownership, registry publish permission and account 2FA.
- **EXTERNAL_CHECK_REQUIRED:** trusted publisher configuration if the owner chooses future automation. Current CI only builds, tests and uploads artifacts.
- Live paid OpenAI/Anthropic account calls are unverified; transport contracts, failures, structured outputs and deterministic complete workflows are tested without credentials.

## Current next steps

- Users install the public package with `npm install -g orqalis` and follow the combined README guide.
- Maintainers prepare a new version for future changes; 1.0.0 cannot be overwritten.
- Optional future trusted publishing requires separate npm configuration; current workflows do not publish.

The two maintainer readiness records are intentionally excluded from the npm tarball to avoid embedding private audit material or creating a circular tarball hash. Public usage documentation remains included. No database migration accompanies these fixes.

## 1.0.1 direct-update patch candidate - 2026-09-14

This section supplements the historical 1.0.0 audit above. The public registry still
serves 1.0.0 as `latest`; the reviewed 1.0.1 package is **not published**. The source
patch adds the npm-global `orqalis update --check` and `orqalis update` path, an
explicit Windows PowerShell session alias for bare `orqalis` on restrictive hosts, and
stale-wheel cleanup during consecutive release preparation. The updater calls the npm
CLI installed beside Node with absolute argv, pins the exact version checked from the
public registry, retains the invoking global prefix, and cannot downgrade.

Validation: 175 Python unit tests (including 18 focused CLI/packaging tests)
and 29 npm launcher tests passed;
Python Ruff and strict script mypy, npm syntax/lint/Prettier, frontend lint/28 tests/build
and `git diff --check` passed. `prepare_npm.py` staged only the 1.0.1 wheel. The exact
reviewed `dist/orqalis-1.0.1.tgz` contains 59 files, including the current README,
release notes, updater, wheel and locked requirements; it excludes stale wheels,
maintainer-only audit records and GUIDE.md. `npm publish --dry-run` passed without an
upload. Tarball SHA-256:
`9C7ADB0110483B3EDED94BE4973166E12E9F0009CDB360613A7DEB091CB3A9A5`.

An isolated Windows x64 install of this tarball passed cold/cached version startup,
help, JSON output, invalid-command exit and hostile working-directory isolation on
Node 24.16.0/Python 3.12.14. In restricted PowerShell, a session-local alias executed
`orqalis update --check` and correctly refused to downgrade 1.0.1 while `latest` was
1.0.0. To exercise actual self-replacement without touching the user's installation,
a disposable global prefix had its fixture manifest marked 0.9.9; `orqalis update`
then replaced that temporary package with the real public 1.0.0 and returned success.
The first broad unit run exposed a test assertion hard-coded to 1.0.0 and one
Windows process-cleanup timing failure. The assertion now checks release metadata.
The timing case passed separately, its full module passed, and 12 measured repetitions
completed in 0.203-0.297 seconds without escaped descendants. The subsequent
complete unit run passed 175/175; no cleanup defect was reproduced.

The final reviewed tarball was also installed over the real public 1.0.0 package
in the same disposable prefix; its installed CLI smoke passed again.
This does not claim an actual 1.0.1-to-future-version upgrade, which requires a future
public release. No database or paid-provider call was needed for this patch validation.

Public publication remains a separate irreversible release-owner action. Recheck the
unused version, source commit, hosted CI and tarball integrity before publishing.

## 1.0.1 foreground CLI candidate supersession - 2026-09-14

The 1.0.1 tarball identified by SHA-256
`9C7ADB0110483B3EDED94BE4973166E12E9F0009CDB360613A7DEB091CB3A9A5`
above is historical and must **not** be published. It still contained the previous
UI helper that could leave a detached `orqalis serve` process after the CLI returned.
The final 1.0.1 candidate replaces that helper with terminal-owned hosting in the
invoking Python CLI process. No Windows service, scheduled task, startup entry or
post-install process is registered. The UI listener ends when its owning CLI exits;
a healthy same-version listener may be reused without claiming its lifetime.

Validation: 190 unit tests, seven PostgreSQL-backed API/schema integration tests,
29 npm launcher tests, Ruff, format and strict mypy passed. `npm publish --dry-run`
reports 59 intended entries. A disposable global npm install passed cold/cached
launcher smoke and 17 installed Core/MCP/UI checks: exact CLI listener ownership,
second-command reuse, packaged assets, API snapshot, ordered WebSocket replay and
port release after stopping the test-owned CLI tree. Windows source and installed
npm CLI Ctrl+C checks released their listeners and left no child process; a scoped
installed Ctrl+Break check also released its listener and process group. The final
README version note changed wheel metadata while Python source and npm launcher
stayed unchanged. Final wheel SHA-256:
`E9F3C99E3453B73C58330851D7081E6140750AC5FBD81841327D8FACEBA3EF09`.
The exact final tarball passed installed global CLI smoke. The disposable PostgreSQL
container and installed-prefix fixtures were removed after validation.

The local full-suite attempt stalled in Windows collection after a transient resource
exception; unit, targeted database integration and installed-package validation passed.
Hosted CI must pass the full suite before publication.

The replacement `dist/orqalis-1.0.1.tgz` SHA-256 is
`8908D09867669179F258EDDA90E3DE980B441A25A622A5186B4CA7D2C299B8AD`.
This is an unpublished candidate. Hosted CI status must be checked against the
pushed source commit before the release owner decides whether to publish.

## Public 1.0.1 publication - 2026-09-15

The candidate hashes above are historical and were not published. The final release
contains the updater, foreground UI ownership, enhanced agent/skill selection, and
persisted supervised approval and plan-editing controls. Its source commit is
`dfd8e31f2d6c84b2df9565bff8f3c1d03cd30c9f`. GitHub Actions `quality` run 34932652087 and `npm package` run
34932652099 both passed for that exact commit. The package workflow passed package
construction, Windows/Linux/macOS launcher smokes, and Linux installed Core/MCP/UI
integration. Local validation passed 312 PostgreSQL-backed Python tests, the isolated
Docker sandbox test, 33 frontend tests, 12 browser end-to-end tests, 29 npm launcher
tests, all static checks, npm dry publish, and a disposable install of the exact tarball.

The published `dist/orqalis-1.0.1.tgz` contains 69 files, is 1,539,392 bytes
(1,968,593 bytes unpacked), and has SHA-256
`b0bf31832c40d59c5b03b4e6cfed7f15f6ec9f47983e736b8a008867500c9011`. npm published version 1.0.1 at `2026-09-15T05:33:58.810Z` with shasum
`10d66da1c2a47b4aabcf9be4bad7cc7f7021705e` and integrity
`sha512-3TNPpq3Eskq6eVsl0BFxYG4Ch5d8bq1wIfEtAApSO6CNLe8YuYEQR0depln7v2Y0mO9hz68A6JcTQ1HX4M/nSA==`. Registry metadata identifies 1.0.1 as `latest`. A direct registry download matched the reviewed local tarball byte-for-byte by SHA-256.

Fresh disposable public-registry installs of `orqalis@1.0.1` and unqualified `orqalis`
both resolved to 1.0.1 and manifest SHA-256
`c7488460f9cb442563388e354cb1d972f6c1cc40232ea97fb3263fae939fee07`, matching the
reviewed package. The exact install passed cold/cached launch, version/help, JSON,
invalid-exit and working-directory isolation; the unqualified install also passed
`modes --json` and `update --check`. Temporary prefixes and runtimes were isolated from
the user's global package and removed after verification. Migration
`6b93c20e21af` must be applied with `orqalis migrate` after upgrading.
