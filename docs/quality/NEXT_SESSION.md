# Release qualification worklist

Updated 2026-10-09 for **Orqalis2.1.0: cleanup/commit/push authorized; publication pending**.
This is the single active worklist. [Status](ENHANCEMENT_STATUS.md) owns detailed
findings, failures and tradeoffs; the [master plan](MASTER_ENHANCEMENT_PLAN.md) owns
acceptance criteria; [release readiness](../NPM_RELEASE_READINESS.md) owns owner gates.

## Current candidate and completed checks

Source `01d45811de37528691a2d12fc16e1a677f1b1b57ecf407e9754955581420cc42` and
[394-input freeze](evidence/release-input-freeze-owned-temp-v4.json)
`a0fb5b8621152ba43673947503667e5969a3cb8ecc234075b3409be86553e038` were restored exactly.
HEAD remains `b8506f7d9c471516fe4b21c9caa735a7a7909af6`.
Current focused133, immutable86,13 static gates, clean exact dependency audits,
installed wheel/npm17/MCP41, fixed263-file graph/gold and1,001-row/33-page history
checks passed. Whole30/31 each collected935 tests:933PASS/2explicitSKIP/0FAIL/ERROR.
Both original14-browser qualifications passed. These retain their original capture
identities and times; rollback verification is not a new test execution.

## Larger-corpus performance investigation

The user accepted current-source cold graph rebuild cost for2.1.0 on2026-10-09.
[The explicit exception](evidence/release-cold-performance-user-acceptance-2.1.0-v1.json)
removes this cost as a local release blocker; optimization is deferred to the next
release as [PERF-COLD-01](ENHANCEMENT_BACKLOG.md#next-release-cache-performance-perf-cold-01).
The fixed matched SDK study confirmed the regression in both orders; all4 cold
comparisons crossed the original2Ãƒâ€”baseline+250ms investigation rule. Its warm/delta/
context comparisons did not trigger. [Actual study](evidence/release-heldout-matched-study-actual-v2.json)
and [quality disposition](evidence/release-heldout-matched-study-actual-quality-disposition-v2.json)
retain all captures and the original8,011ms observation. No host/OS cause is established.

The Oct9 fixed full-SDK reader control completed four functional/cleanup passes but
was inconclusive: native cold14.632/5.713s versus alternate CRT4.943/6.390s, with
overlapping ranges. [Quality review](evidence/release-full-sdk-cache-reader-control-actual-quality-disposition-v2.json)
rejects a production reader fallback. Source/input/HEAD are unchanged; no new
qualification credit. The accepted tradeoff does not turn this diagnostic into a
performance fix or identify its cause.

## Rejected optimization retained

Reader/publication controls did not justify a safe fallback. A bounded read experiment
passed123 focused tests but failed6/16 prospective performance comparisons and was
reverted. [Exact rollback](evidence/release-graph-cache-read-ahead-exact-rollback-v1.json)
and [independent verification](evidence/release-graph-cache-read-ahead-rollback-acceptance-review-v1.json)
preserve its source/tests and prove the original source/input map is active again.
No rejected implementation remains in the candidate; no faster-sample selection.

## Retained failures and proof scopes

[Status](ENHANCEMENT_STATUS.md) owns the complete history, including interrupted25,
advisory26, browser28 and the experiment's initial failed/corrected focused runs.
All raw proofs remain retained. Passing current tests do not explain older failures.
The user confirmed concurrent work; that is context, not a causal or host-idleness proof.

## Remaining work, in order

1. The historical prose artifact and archive/installed parity are recorded in
   [the serial record](evidence/release-owned-temp-final-docs-actual-v7.json).
   [Documentation cleanup](evidence/release-prepush-doc-cleanup-20261009-v1.json)
   supersedes that prose snapshot. Hosted CI must build/test the committed LF tree and
   current docs. The qualified raw application source and frozen test inputs are unchanged.
2. Existing whole30/31 are accepted as2/2 bounded local qualifications WITH the
   explicit cold exception. Broader OSS convergence remains incomplete:23 capability
   evaluations remain pending, including current1,001-row payload/timing attribution
   for I03. Semantic1001/33-page correctness has passed; it is not a timing result.
   [Registry](capabilities.json), [matrix](OSS_BENCHMARK_MATRIX.md) and
   [sign-off](OSS_ENHANCEMENT_SIGNOFF.md) retain these scope distinctions;13 DEFER remains.
3. Hosted Linux/Windows/macOS package matrices, Linux installed integration and
   publication require release-owner action and a reviewed committed candidate.
   Cleanup, commit and push were explicitly authorized on2026-10-09.
   Tagging and npm publication remain pending hosted and owner gates.
   [Preparation record](evidence/release-git-npm-preparation-20261009-v1.json) notes
   the missing environment reviewer gate and unverified Trusted Publisher binding.
   [Preparation security review](evidence/release-git-preparation-security-review-20261009-v1.json)
   requires fresh `ci.yml` quality success on the exact committed LF revision before
   tagging/publication. The package publish job does not depend on that separate workflow.
4. Next release: investigate PERF-COLD-01 with preserved snapshot/freshness/security
   guards and new source-bound qualification. No blind retries or weaker reader.

## Retained boundaries

No deadline, assertion or gold relaxation; no global host/security change or universal
speed/RAM claim. Native Linux/macOS, live Docker, direct symlink creation, paid providers
and native assistant tiers remain unqualified. Three memory systems means graph facts,
reviewed project memory and Task Capsules; it does not mean three canonical files.
No owned QA workload or descendants should remain after final checks.

## Cleanup and commit/push preparation, 2026-10-09

The user authorized cleanup, commit and push. Three redundant handoff/migration/audit
documents were merged into existing authority, implementation-status and readiness docs;
stale current qualification text was corrected. The [cleanup result](evidence/release-prepush-generated-cleanup-result-20261009-v1.json)
records removal of 1,361 generated targets (about 3.1 GiB), with no failures. Two fixture
junctions were unlinked without traversing their targets before their roots were removed.
Raw validation evidence and reviewed investigation helpers remain; old local tarballs and
installed fixtures were removed. The qualified application source and all 394 frozen
inputs still match. Documentation changed, so hosted CI must build/test a fresh artifact
from the exact pushed revision before tagging or publication.

## Hosted package portability follow-up

The first pushed candidate's package workflow failed strict Linux typing in three
Windows-only benchmark helpers before packing. [Failure and fix disposition](evidence/release-hosted-package-portability-failure-disposition-20261009-v1.json)
retains the original hosted failure and first local correction failure. The final
platform guards pass script lint/format and strict typing for Linux, macOS and Windows
([static checks](evidence/release-hosted-portable-script-checks-20261009-v2.json)).
Application source, tests, dependencies and workflows are unchanged; 391 original input
hashes match and three helper hashes changed. The [successor input map](evidence/release-input-freeze-portable-scripts-20261009-v1.json)
does not rebind the old full rounds or timings. Fresh hosted CI must pass on the
follow-up commit before tagging/publication; static platform checks do not certify
native runtime behavior.
