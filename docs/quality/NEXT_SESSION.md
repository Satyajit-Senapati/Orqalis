# Release qualification worklist

Updated 2026-10-09: **Orqalis 2.1.0 is published and verified as npm's latest.**
Immutable `v2.1.0` points to `19865786a0280e6875902fe2d4dbe9d02975cc23`.
[Publication receipt](evidence/release-publication-closeout-2.1.0-20261009-v1.json) records exact-source hosted quality,
three-platform package smoke, installed integration and public artifact identity.
Release preparation is complete; this worklist now tracks the next release.
This is the single active worklist. [Status](ENHANCEMENT_STATUS.md) owns detailed
findings, failures and tradeoffs; the [master plan](MASTER_ENHANCEMENT_PLAN.md) owns
acceptance criteria; [release readiness](../NPM_RELEASE_READINESS.md) owns owner gates.

## Historical local qualification and completed checks

Source `01d45811de37528691a2d12fc16e1a677f1b1b57ecf407e9754955581420cc42` and
[394-input freeze](evidence/release-input-freeze-owned-temp-v4.json)
`a0fb5b8621152ba43673947503667e5969a3cb8ecc234075b3409be86553e038` were restored exactly.
The restored local checkpoint was `b8506f7d9c471516fe4b21c9caa735a7a7909af6`; it is not the released commit.
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

## Remaining work for the next release

1. Investigate [PERF-COLD-01](ENHANCEMENT_BACKLOG.md#next-release-cache-performance-perf-cold-01)
   with preserved snapshot/freshness/security guards and fresh source-bound qualification.
   The accepted 2.1.0 cold-cost exception is not a performance fix.
2. Complete the 23 IMPLEMENTED_PENDING_EVAL capability evaluations and revisit the
   13 DEFER decisions only where justified. [Registry](capabilities.json),
   [matrix](OSS_BENCHMARK_MATRIX.md) and [sign-off](OSS_ENHANCEMENT_SIGNOFF.md) own scope.
3. Resolve I03 current 1,001-row payload/timing attribution. Ordered 1001/33-page
   correctness has passed; older-source timings do not establish current latency.

## Retained boundaries

No deadline, assertion or gold relaxation; no global host/security change or universal
speed/RAM claim. Paid providers, native assistant tiers, live Docker and direct symlink creation remain
unqualified by these checks. Hosted Linux quality and three-platform launcher smoke
do not certify every native feature or workload. Three memory systems means graph facts,
reviewed project memory and Task Capsules; it does not mean three canonical files.
No owned QA workload or descendants should remain after final checks.

## Historical preparation checkpoints, 2026-10-09

The following checkpoints retain their capture-time scope. The publication receipt
above supersedes their pending release gates.

### Cleanup and commit/push preparation

The user authorized cleanup, commit and push. Three redundant handoff/migration/audit
documents were merged into existing authority, implementation-status and readiness docs;
stale current qualification text was corrected. The [cleanup result](evidence/release-prepush-generated-cleanup-result-20261009-v1.json)
records removal of 1,361 generated targets (about 3.1 GiB), with no failures. Two fixture
junctions were unlinked without traversing their targets before their roots were removed.
Raw validation evidence and reviewed investigation helpers remain; old local tarballs and
installed fixtures were removed. The qualified application source and all 394 frozen
inputs still match. Documentation changed, so hosted CI must build/test a fresh artifact
from the exact pushed revision before tagging or publication.

### Hosted package portability follow-up

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

The first quality run also failed two immutable-baseline fixture tests because the
shallow Actions checkout did not contain their pinned baseline commit. Its remaining
results were 911 passes/22 explicit optional or Windows-only skips. The quality
workflow now fetches full history; [the two focused tests pass](evidence/release-hosted-history-checkout-fix-20261009-v1.json).
Only that checkout setting changed; assertions and baseline remain fixed. The
[latest input map](evidence/release-input-freeze-hosted-history-20261009-v1.json)
records four changed support inputs/390 original matches with unchanged application,
tests and dependencies. Fresh hosted quality/package success for the final revision
remains a prerequisite to tagging/publication.

### Merge and publication preparation

The user authorized merging and releasing. Main was fast-forwarded to tested commit
`d767255f722d870e35d6af6836b0d7777565044a`. Both hosted quality and package workflows
passed, including Linux/Windows/macOS smoke and installed integration. The required
release-owner review gate is now configured on `npm-release`. After user security-key verification, npm's Settings page confirmed the existing
Trusted Publisher is Valid for `Satyajit-Senapati/Orqalis`, `npm-package.yml`,
`npm-release`, with `npm publish` permission. No npm access settings were changed;
local CLI authentication is unnecessary for this OIDC release. README and release-note presentation are being prepared for the
2.1.0 artifact; fresh CI for this prose revision must pass before a new tag/publication.
No tag or publication has been performed at this checkpoint.
