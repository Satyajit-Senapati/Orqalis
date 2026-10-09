# Enhancement status

Updated 2026-10-09 for **Orqalis 2.1.0: local candidate, uncommitted and unpublished**.
HEAD remains `b8506f7d9c471516fe4b21c9caa735a7a7909af6`.

**Current disposition, Oct9:** the user explicitly accepted cold graph-rebuild cost
for2.1.0 and deferred optimization to the next release (PERF-COLD-01).
[Authorization](evidence/release-cold-performance-user-acceptance-2.1.0-v1.json)
amends only this release-specific performance criterion. The two existing whole
qualifications are accepted as bounded local2/2 WITH EXCEPTION;
broader OSS capability convergence remains incomplete and is not labeled clean.
All23 capability statuses remain IMPLEMENTED_PENDING_EVAL /13 DEFER. In particular,
source01 history1001 proves ordered coverage/integrity, not current1,001-row latency;
older-source timings have no proved equivalence bridge. Final prose/package checks
are refreshed in [the serial record](evidence/release-owned-temp-final-docs-actual-v7.json).
No production change, new full run or commit is implied. Earlier blocked dispositions
below retain their capture-time meaning; the measured regression remains real.

**Resumed on Oct7 at the user's request; round28 failure is retained; the current candidate has completed both whole functional qualifications.**

**Historical failed capture:** patched round28 stopped at browser qualification:13 PASS /1 FAIL. The unchanged governance test did not see PLAN version1 within5000ms after approval; its preview request remained pending. Round29 and all round28 audits, benchmarks and full regression are unrun. Owned descendants were closed and reaped. Subsequent targeted and original full14 instrumented browser diagnostics passed (approved previews1.8398s and1.7321s), with concurrent capsule reads waiting on commits. These do not reproduce or close the original failure; no diagnosis establishes that failure's cause. A subsequent descriptor optimization targets independently measured temporary-read costs. The failed capture remains in [round28 evidence](evidence/release-browser-28.json); a targeted pass-through request trace is diagnostic only, with no acceptance credit.

## Rejected cache-read optimization

The bounded Windows read experiment on35a12/input670e passed123 focused tests,
including all eight new concurrency/duplicate/policy/byte-accounting cases, lint
and strict typing. Its initial120PASS/1FAIL capture is retained. The fixed SDK
baseline/current/current/baseline screen completed all functional checks but triggered
six of16 original performance comparisons: candidate cold3,232.236/6,822.727ms versus
baseline1,894.285/2,800.841ms; the second candidate also crossed warm/delta/context
comparisons. No host or OS cause is established and no faster sample was selected.
[Actual screen](evidence/release-heldout-matched-study-actual-v4.json) retains all results.
The [exact rollback](evidence/release-graph-cache-read-ahead-exact-rollback-v1.json)
restores source01d458/all394 inputs and archives experimental engine/test bytes.
These experimental timings are not current-source regressions or qualification credit.
No read-overlap implementation remains in the release candidate.

## Full-SDK cache-reader control, Oct9

The fixed native/CRT/CRT/native diagnostic preserved the original263-file SDK
workload, graph/model validation and gold/context/incremental checks. All four
captures passed; source01d458, all394 inputs, environment, corpus and HEAD remained
stable, and all owned jobs closed/reaped with zero descendants and cleanup errors.
The alternate opener applied only to cache reads during the timed rebuild and was
restored before every warm/delta/index/context operation. Production code is unchanged.

| Capture | Reader | Cold rebuild | Warm refresh | One-file refresh | Context median |
| --- | --- | --- | --- | --- | --- |
| 1 | Native | 14,631.914ms | 839.540ms | 5,288.590ms | 789.292ms |
| 2 | CRT diagnostic | 4,943.136ms | 485.009ms | 2,788.394ms | 934.778ms |
| 3 | CRT diagnostic | 6,389.876ms | 406.786ms | 2,909.128ms | 1,287.051ms |
| 4 | Native | 5,713.473ms | 523.668ms | 2,760.725ms | 1,987.018ms |

[Raw controller](evidence/release-full-sdk-cache-reader-control-actual-v2.json),
[independent quality disposition](evidence/release-full-sdk-cache-reader-control-actual-quality-disposition-v2.json)
and [acceptance review](evidence/release-full-sdk-cache-reader-control-actual-acceptance-disposition-v2.json)
retain all four comparisons: three negative CRT-minus-native differences and one
positive. Overlapping ranges and native variation do not isolate a reliable opener
benefit or a host/OS cause. The CRT arm weakens delete sharing and entry-only opening
and remains private-fixture-only. Later warm/delta/context differences cannot be
attributed to an alias already restored. No shipping fallback or acceptance follows.
Duplicate cache aliases account for only24Ã¢â‚¬â€œ26ms in retained traces, so local reuse
cannot resolve the multi-second gap. A cache-container design would need fresh
freshness/security/compatibility checks and source-bound qualification. The user
has now accepted this cold cost for2.1.0; the original results remain unchanged.
This exception permits bounded local qualification, not broader clean convergence.

## Current acceptance boundary

Current application01d458 /394-inputa0fb is frozen in the [owned-temporary input map](evidence/release-input-freeze-owned-temp-v4.json). Exact byte verification and fresh identity guards reuse the owned descriptor, while unknown ownership prevents cleanup mutation. Runtime-focused133 PASS; seven write/ownership and four read-accounting cases were added. Fresh13 static gates/dependency audits and immutable86 PASS. Fresh wheel/npm17-MCP41, exact installed51-package audits, fixed263 heldout and history1001/33pages PASS. Whole30 completed all benchmark/browser/audit checks and full935 (933PASS/2explicitSKIP/0FAIL/ERROR), with all provenance guards stable and owned processes closed/reaped. Execution median25.810seconds versus fixed pooled55.870seconds. Whole31 completed full935:933PASS/2explicitSKIP/0FAIL/ERROR. Independent functional, quality and runtime/security reviews confirm these checks; zero confirmed currentP0/P1 in the bounded runtime/security scope. Cold timing is accepted for2.1.0 under the explicit exception; broader convergence remains incomplete. Earlier evidence retains its original identity; no convergence promotion.

The earlier b897 [native-cost observation](evidence/release-execution-native-cost-summary-v5.json)
measured2,120 temporary-verification reads at31.764s inclusive perturbed wall time,
motivating owned-descriptor verification. It supplies no CPU/physical-I/O, host cause,
current speed or convergence claim; all26 semantic/4 stability witnesses passed.

The original larger-corpus cold8,011.435ms exceeds6,505.331ms. A fixed matched
baseline/current/current/baseline SDK study now confirms a current cold degradation:
baseline1,596.899/1,504.215ms versus current8,470.894/4,672.093ms; all4 cold comparisons
trigger2Ãƒâ€”baseline+250ms, while the other12 warm/delta/context comparisons do not.
All corpus/source/input/environment guards and owned-process cleanup passed.
[Matched study](evidence/release-heldout-matched-study-actual-v2.json) and
[independent quality disposition](evidence/release-heldout-matched-study-actual-quality-disposition-v2.json)
retain the performance blocker. Prior reader controls localized first-open latency
but did not distinguish publication mechanism. The completed publisher control did not support a safe rename optimization;
the bounded read experiment above also failed and was reverted. No weaker fallback
or qualification credit follows.
[Sign-off](OSS_ENHANCEMENT_SIGNOFF.md) owns the master-required pending boundary,
[final functional/quality proof](evidence/release-owned-temp-quality-performance-final-proof-v1.json)
retains all30 quality tradeoffs and richer footprint costs, and the [worklist](NEXT_SESSION.md)
is the sole ordered continuation. Bounded local qualifications are accepted2/2 with the exception;23 capabilities
remain IMPLEMENTED_PENDING_EVAL and13 DEFER. Final documentation/distribution proof
is in the [serial packaging record](evidence/release-owned-temp-final-docs-actual-v6.json).

Oct7 round26 stopped on the frontend HIGH source-map-js advisory, before benchmarks.
The single dev-only lock entry is patched to1.2.2; audit0, lint and39 frontend units
pass. The isolated build reproduces all9 tested frontend bytes; application197 inputs
are unchanged. [Bridge](evidence/release-dependency-advisory-20261007-bridge-v1.json)
and [security review](evidence/release-web-advisory-20261007-security-review-v1.json)
bind the original failed audit and clean follow-up. New393 freezee807 applies only to
fresh28/29; older56c captures remain historical. No convergence credit yet.

The active Windows I/O fix reproduces an owned-reader collision with `os.replace`.
Reader sharing alone fails the new regression (2 failures / 9 passes, retained XML).
Shared-delete reads combined with one native POSIX rename pass the controlled case:
the held reader retains old bytes while the path exposes new bytes. `ReplaceFileW`
was evaluated but rejected because its documented partial failures can remove the
original path. The implementation preserves the five attempts, backoff, permissions,
fsync, journal, recovery and storage formats. Unsupported native rename classes fall
back only after closing the handle; permission errors do not select another API.
The first implementation passed [143 focused persistence/memory/history/hard-crash cases](evidence/release-shared-io-regression-actual-v1.json).
The final platform-structured candidate passed [94 native/foundation cases](evidence/release-shared-io-portable-focused-actual-v1.json).
All existing assertions across 54 foundation functions are unchanged. Strict Windows
289-file typing and Linux/macOS I/O selections pass; native non-Windows execution remains
unqualified. [Independent review](evidence/release-shared-io-portability-memory-security-review-v1.json)
found no new concrete P0/P1. A calibrated memory successor observes canonical native reads
once without changing workloads, oracle, budgets or returned-byte accounting; original
scripts remain protected. Final installed checks below have since passed; whole qualification remains pending.
Previous qualified application is `b89701256391d82bd51a347e5fe02ff4293c32b2a59b167ac492559041f0cc30`;
393-input freeze is `56c454c8630d017a71802cccda1ef0d8d8521964babfa6ee4df8c1284a2c8750`.
The additional P2 wrong-thread release defect reproduced in both depth1/depth2 cases.
The fix validates ownership before changing counters/native handles, retaining the
existing no-instance-hold rejection and final gate/platform-release ordering. Final
[124 focused cases](evidence/release-final-fixes-focused-actual-v1.json) pass. The public
benchmark now adopts the calibrated observer; its exact original bytes are archived,
workloads/gold/deadlines preserved and the method label records wider coverage. Two
prelaunch collection errors due Windows source encoding/repair boundary are retained;
no tests or benchmark ran in those failed collections. The earlier source2489 preflight
actually completed static11/current86 PASS before retirement; its exit identity guard
prevented termination because it had already finished. The final source-bound preflight
has all13 static gates PASS, including strict checks across 290 files for Windows,
Linux and macOS, and three clean dependency audits. Its immutable86 suite passes with
zero failures/errors/skips in 1,590.79 seconds (verification overhead, not a benchmark);
Previous [wheel/npm artifacts](evidence/release-artifact-identity-final-fixes.json) pass
installed17/MCP41 verification and both exact installed dependency audits. The
[263-file heldout](evidence/release-heldout-current-final-fixes-v1.json) also passes.
The [history1001 semantic check](evidence/release-history-final-fixes-semantics-v1.json)
passes all three traversals / 33 pages, with canonical bytes unchanged and concurrent
reservation preserving the scan snapshot. Whole24 completed; whole25 was interrupted at the user's request during baseline UI.
The [independent current artifact review](evidence/release-artifact-security-independent-review-final-fixes-v1.json)
verifies complete71 npm files /209 wheel entries, installed payload parity and current
source/frontend bytes, including the source-bound17/MCP41 smoke chain and two clean51
package audits. Final prose remains UNRUN. Round24 timed phases pass their functional
checks, but [provisional acceptance](evidence/release-round24-provisional-acceptance-performance-blocked-v1.json)
records execution median84.352 seconds versus pooled all-nine baseline55.870 seconds
(+50.98%). All three samples pass26+4 unchanged checks. Same event/work volume and
boundary host58.4% activity /72% to82% physical-memory load do not establish a cause.
The full924-case round24 suite completed with922 PASS /2 explicit SKIP /0 FAIL/ERROR.
Round25 browser14/audits/quality/execution correctness/memory completed; baseline UI
was interrupted, and current UI/constrained/fullPython are UNRUN. Native-I/O attribution
and final prose helpers remain UNRUN. No convergence credit or historical-holder claim follows.
Earlier source-bound results below remain historical.

The prior source4f candidate has three additional reductions: reuse the secret-checked
serialized state bytes, allocate lock registry gates only on a miss, and lowercase
diagnostic text once. No write, recovery, deadline, retry or assertion was removed.
[Exact equivalence](evidence/release-pure-work-equivalence-v1.json) confirms identical
bytes for all 42 documents / 125,526 bytes from the retained final aggregate and
unchanged fixture inputs. The focused persistence, locking, security and hard-crash
suite passed **141 tests**. [Independent security review](evidence/release-pure-work-optimization-security-independent-v2.json)
found no new P0/P1 issue. These results do not establish an end-to-end speedup.

Prior tested application SHA256: `4f4088875af3050f10f5be510f8b05159e2bedd37f88fd818a6365a2f0348d44`.
The [prior 390-input freeze](evidence/release-input-freeze-pure-work-v1.json) is
`6a9316bf2d1decb71aef5e40983ad896c1d9bbd082e473f70cdd4d86b2ee5ee3`;
only the three production files differ. All 11 fresh static gates and three development
advisory checks pass; its 86-case frozen suite passed with zero failures,
errors or skips and stable source/test/helper/dataset identities. Fresh
[wheel/npm artifacts](evidence/release-artifact-identity-pure-work.json) pass installed
17-check Core/MCP/UI verification (41 MCP tools) and both exact 51-package audits.
[Independent archive review](evidence/release-artifact-security-independent-review-pure-work-v1.json)
confirms safe entries, complete installed byte/size equality and exact current source
and frontend bytes. Only the wheel and vendor manifest differ among runtime archive
files versus source24. The fresh [263-file heldout](evidence/release-heldout-current-pure-work-v1.json)
also passes. The guarded sequential controller stopped at round 22's second execution
sample; later stages and all of round 23 are UNRUN. Final prose packing and independent
acceptance remain pending. The compatibility suite's
41-minute wall time is verification overhead, not an execution benchmark or a
supported-cause explanation for historical measurements.
The v1 preflight stopped at its source guard before launching any workload because
the preparation replacement literal was mistyped. That failure is preserved;
v2 obtains the prior hash from the immutable freeze. No application fix followed.
The history semantic driver's v1 completed all three 1,001-row traversals but shadowed
`concurrent.futures` with a service variable before starting reservation. Its failure
and copied fixture are retained; v2 changes only that variable and exclusive paths.
No application failure or timing conclusion follows from this driver error.
The corrected [history semantic check](evidence/release-history-pure-work-semantics-v2.json)
passed on the current source: three traversals, 1,001 unique ordered rows / 33 pages,
unchanged canonical task documents, a unique concurrent reservation and stable scan
snapshot. It collects no new timing or performance comparison.

The [actual stopped controller](evidence/release-pure-work-complete-actual-v1.json)
retains stable source/environment/prerequisite guards. Round 22 browser14 and fresh
advisories pass; paired quality preserves the same 30 accepted REVIEW losses with no
new hard failure. Its first execution sample passes all 26 semantic and four stability
checks in **70.8595 seconds**, then sample two fails after the original five attempts
with **WinError 5 replacing an actor `session.yaml`**. The execution report is incomplete;
no current median, accepted whole round or latency improvement follows. Memory, UI,
constrained and full Python stages did not run. The benchmark's automatic cleanup
removed the failed fixture: attributes/holders at failure are unknown.
[Bounded triage](evidence/release-execution22-atomic-denial-security-disposition-v1.json)
finds no demonstrated persistent owned-handle leak or source-supported recovery fix.
History can read actor projections via `*/session.yaml`, but no invocation is established
in this frozen worker. The [single reviewed retained-fixture diagnostic](evidence/release-execution-terminal-denial-v3.json)
completed with all26+4 checks, all six final stability guards and confirmed owned
launcher/native exit and handle close. Of 2,124 replacement calls, two recognized
denials were handled by existing retries; no terminal denial reproduced. Observer
errors are zero; the bounded weak-reference window discarded 186 older records.
No terminal metadata was captured, so it cannot identify the original holder or cause.
The fixture and all raw reports remain. Instrumented timing receives zero benchmark
or section53 credit. V1/v2 diagnostic helpers remain unrun with their static objections
retained; v3 changes diagnostic hygiene only. No retry expansion, target-permission
change, baseline retry or host-cause claim is justified.
This is a current reliability acceptance blocker in addition to the retained latency gap.

Both prior candidate rounds 20 and 21 finished successfully on source24. Each full Python
suite collected **908 tests: 906 PASS, 0 FAIL/ERROR, 2 explicit SKIP**; all five
stability checks passed. Independent [paired functional acceptance](evidence/release-paired20-21-functional-acceptance-performance-blocked-v1.json)
confirms both rounds. **Release acceptance remains blocked by the current replacement
failure and unexplained execution latency under master section 53: 0/2 accepted convergence
iterations.** The 23 accepted
P1 capabilities remain `IMPLEMENTED_PENDING_EVAL`; 13 DEFER decisions remain.
That historical review found no newly confirmed production P0/P1 correctness defect.
The historical failed capture remains unresolved; its origin and regression classification
are not established by passing focused tests or the historical disposition.

Prior application SHA256: `24ffafca60dc7d153d92006445096d0c92ad057f04692349355387638bfda708`.
The [390-input freeze](evidence/release-input-freeze-cleanup-portable-v3.json) has aggregate
`97e7f0a386979e296c6ee8581c4edcadf7b48c8d9565540e5443f62531ebcb9f`.
[Accepted portable reuse](evidence/release-source-freeze-portable-reuse-accepted-v2.json)
binds that prior application and one corrected public portability test to
initial static/contracts/frontend/artifact/heldout/history proofs. Original reports
remain bound to their original source/test identities.

| Prior source24 evidence | Result and limits |
| --- | --- |
| Whole rounds [20](evidence/release-iteration-20.json) / [21](evidence/release-iteration-21.json) | Both complete; stable source, inputs, protected helpers and environment; independent functional acceptance only |
| Browser and advisories | 14 browser cases per round pass; three advisory checks per round clean; current development Python audit has 63 third-party packages |
| Full Python [20](evidence/full-regression-release-20.json) / [21](evidence/full-regression-release-21.json) | 906 PASS and the same two explicit skips each; live Docker image and direct symlink creation unqualified; broad symlink OSError catch does not prove the precise OS cause |
| Static and focused portability | 81 foundation cases, zero skips; Ruff/format 295 files; strict typing 287 files with Windows/Linux/macOS selections; selections do not certify native Linux/macOS execution |
| Initial wheel/npm | Installed 17 checks and MCP41 pass; dated exact 51-package wheel/npm audits clean including pip26.2.1; source24 final provisional pack, installed payload/modes and local documentation audit passed; new source needs a fresh build and installed checks |
| Heldout and history | Fixed 263-file heldout and 1,001-row / 33-page history functional proofs pass; native history measurement and retained matched captures preserve performance limits |
| Memory / UI / constrained | Both fresh rounds complete; memory answer/cap/history witnesses pass, UI pause/resume improves in these captures, candidate constrained peak commit is higher; no universal speed or RSS claim |

## Decisions and evidence ownership

The 50 decisions comprise **9 KEEP, 15 ADAPT, 8 ADD, 13 DEFER and 5 REJECT**.
The [registry](capabilities.json), [backlog](ENHANCEMENT_BACKLOG.md),
[master plan](MASTER_ENHANCEMENT_PLAN.md), [OSS matrix](OSS_BENCHMARK_MATRIX.md),
[catalog](OSS_CAPABILITY_CATALOG.md) and [license audit](OSS_LICENSE_AUDIT.md) own
individual criteria, research and adoption decisions. Forty upstream entries are
source/capability comparisons; they are not forty independently benchmarked runtimes.
The current upstream refresh retains exact identities and component license limits;
Daytona core remains deferred. Implemented areas include portable skills, conservative
syntax facts, bounded graph/symbol reads, identifier retrieval, reviewed memory lifecycle,
MCP lifecycle/history tools, local trace/provider metrics, owned sandbox recovery,
Change Guardian and frozen provider-free evaluation.

## Performance acceptance

Execution medians are **63.134 s (20)** and **70.923 s (21)** against retained baseline
capture medians **55.643 / 55.870 / 95.100 s**. All nine baseline samples remain visible.
Both candidate captures pass the original 26 semantic and four stability checks, but
are slower than the fastest and pooled references. Equal 174 events and essentially
equal persisted bytes cannot explain added latency. Selecting the slow reference,
passing deadlines, range overlap or disclosing costs does not satisfy section 53.
See the [strict blocker](evidence/release-master53-performance-blocker-addendum-v1.json)
and [independent nonclosure](evidence/release-execution-performance-nonclosure-independent-v1.json).

Both paired quality comparisons remain raw **REVIEW**, preserving the exact 30 accepted
case/channel/metric losses and zero hard invariant failures. Mean candidate index/context
recall is 0.870370, versus baseline 0.722222 / 0.851852. Better means do not erase misses.
Candidate graph/index/store/Python peak ratios are approximately 1.458 / 2.413 / 2.027 /
1.592 times baseline. Python allocation is not native RSS. Progressive complete memory
answers use fewer response bytes but take longer than full rediscovery in these captures;
direct reuse has narrower semantics. Exact definitions and historical numbers live in
[the benchmark guide](../../benchmarks/README.md) and unchanged raw evidence.

The finite retained797/current history comparison completed all four predeclared
captures with functional/provenance/observer checks passing. Its raw status remains
**MIXED_OR_INDETERMINATE**: wall medians 173.917 / 200.227 / 244.206 / 273.122 ms;
CPU medians 171.875 / 187.5 / 234.375 / 265.625 ms. All references and tails remain.
A bounded [source-path acceptance addendum](evidence/release-history-page-path-acceptance-addendum-v1.json)
accounts for the candidate-specific history code concern: unchanged page path and
zero measured traversal writes exclude the only changed atomic-writer edge. It does
not establish runtime equivalence, explain historical host interference or grant
iteration credit. No further history timing lottery is indicated without a new cause.

The completed [candidate-only operation diagnostic](evidence/release-execution-candidate-operations-result-v3.json)
passed all26+4 checks with stable inputs in51.286747s. Its 28 lease calls (26 first
acquisitions) span83.4942ms, and two known denials imply40ms scheduled backoff. These
are too small to explain the historical gap; the faster present sample replaces none.
The [read-only trace reconstruction](evidence/release-trace-replay-result-v3.json)
measured3.0646ms for one final174-event/41-node call. It does not measure earlier
snapshots or historical overhead. V2's envelope-decoder failure had zero trace calls;
V3 uses the unchanged production envelope rule. All failures and input bindings remain.

Repeated targets in the operation report are not necessarily identical bytes: structured
projections carry a new generation on each commit. A recovery skip optimization would
need separate durability/race evidence; it is not a justified release fix from these
measurements. A controlled future comparison is needed to resolve the timing evidence
gap. Additional successful timings on this host would not reconstruct past causes.

## Material repairs and preserved invariants


The WebSocket change shields the existing child cancel/join against framework
cancellation while native cancellation still propagates. Authorization, replay,
filesystem worker and deadline contracts stay intact. Direct AnyIO metadata changes
no dependency version; its exact two root lock entries invert to the prior audited file.
Broader approval transaction changes remain unapplied.

Known-run goal/evidence/approval lookups avoid foreign capsule scans; generic queries
with unknown owners retain cross-run discovery. The unchanged ten-second lock timeout
is preserved in the real [before](evidence/release-lookup-lock-before.json) and
[after](evidence/release-lookup-lock-after.json) reproducer and
[integrity review](evidence/release-lookup-integrity-independent-review-v3.json).
Global auxiliary identity checks still perform full canonical recovery/duplicate
validation. One project lease releases run locks before waiting, reacquires in stable
order and rejects stale generations. Owner-scoped provider/tool reads, rollback-required
handoff failure, partial-lease cleanup, nested ownership and memory-write ordering
remain enforced. See [final auxiliary guard review](evidence/release-auxiliary-lock-final-guard-independent-review.json).

Required PLAN requests share the validated locked checkpoint/edit transaction;
journal durability, actor/subject validation, disabled-policy and execution guards remain.
[Atomic checkpoint review](evidence/release-atomic-plan-independent-review.json)
retains rollback and post-commit notification proof. Source memory is constructed on
first actual use, preserving coherence locks, validation and write reload:
[lazy-memory review](evidence/release-lazy-memory-independent-review-v1.json).
Canonical history scanning happens outside the shared allocation-index lock; derived
compare/write stays locked. Fresh canonical validation and stale-scan rejection remain.

Process-local FIFO preserves same-thread reentrancy, original deadlines and OS advisory
locks; [review](evidence/release-fifo-gate-applied-independent-review.json) is bounded to that repair.
Cancellation polling runs in owned/drained threads; work and polling drain before lease
release. [Diagnostic evidence](evidence/lock-diagnostic-summary.json) retains earlier
unexplained waits; focused proof does not establish every browser failure's cause.

Git location/status work is shared only within the validated request/root context;
worktree/common-directory identity, method overrides, errors and successful path whitespace
retain their guards. Same-root Brain reuse accepts the builder's freshly validated graph,
not caller-supplied graph tuples or a cross-request cache. Worktrees and custom service
subclasses/instance overrides retain separate authority reads. See
[Git review](evidence/release-git-location-applied-independent-review-v1.json) and
[Brain review](evidence/release-brain-shared-graph-applied-independent-review.json).
Ordinary-path layout optimization skips only redundant store-prefix resolution after
fresh full ancestry validation; candidate resolution and containment remain. Noncanonical
stores, arbitrary paths and subclasses retain fallback and independent atomic-write guards. [Applied layout review](evidence/release-layout-resolution-applied-independent-review-v1.json)
records alias/race/error-order limits; it does not certify universal filesystem latency.

Graphify's three advertised files are graph exports, not three canonical memory files.
[Project memory](../03-project-memory.md) separates graph facts, reviewed durable memory
and Task Capsules. Request-local sharing/compact derived indexes introduce no persistent
mtime cache, extra storage layer or canonical memory/task/cursor format change.
Source freshness, secret/response caps and malformed/non-finite fail-closed recovery remain.
[Storage research](research/KNOWLEDGE_RESEARCH.md#project-memory-storage-and-read-optimization)
and [batch timing review](evidence/memory-batch-timing-review.json) retain the inconclusive
latency result. Canonical per-page history validation still scales with capsule count;
bounded response size does not make that validation constant-time.

Syntax facts remain conservative: JS calls/inheritance are occurrences, not resolved
semantic claims; incomplete Python extraction disables candidate binding. Explicit
truncation bounds nested-symbol cache amplification. Byte-derived parser positions avoid
the reproduced native Point-getter fault; see [native parser evidence](research/KNOWLEDGE_RESEARCH.md#native-parser-preflight-correction).
Guardian invalid/overcomplex new tests, skip-marker weakening and removed pytest assertion
helpers fail closed. Occurrences remain navigable but outside ordinary Context Pack seeds;
[ranking review](research/RANKING_REVIEW.md) preserves real misses and broadened tail noise.

## Failed observations retained

| Observation | Preserved disposition |
| --- | --- |
| Baseline attribution v3 | [Actual failed run](evidence/release-execution-attribution-actual-v3.json): immutable baseline WinError5 replacing execution/state.yaml; candidate UNRUN; owned processes and handles cleaned up; no baseline retry or usable completed timing |
| Failed fixture inspection | [Post-exit metadata](evidence/release-execution-attribution-failed-fixture-inspection-v1.json): target regular and not READONLY after exit, named temporary absent; does not identify the holder or attributes at failure |
| Candidate execution16 / baseline8,10 | Original WinError5 failures remain; current source now has bounded recognized-denial retry and temporary cleanup; original denying process remains unknown |
| Full10 / full12 | Original failed lease probe and WebSocket teardown retained; narrow reviewed corrections now pass both current full suites |
| Finite history v3 and old profiler | Original dependency-attestation failure and excessive observer overhead remain invalid for causal timing; v4 uses a predeclared corrected method without reusing failed timings |
| Governance/browser and earlier contract failures | Original reports and source-bound corrections retained in the historical ledger; no reconstructed historical cause |

Known Windows replacement denials receive five attempts with 20/40/80/160 ms backoff;
fresh guards, persistent failure and original bytes remain. The cleanup-only repair
clears READONLY on the guarded regular owned temporary only, deletes once and preserves
the original error and target permissions. Ordinary success adds no temporary metadata
check. The 10-second lock and 300-second execution budgets were not relaxed.

## Historical evidence index


| Wave | Preserved source-bound evidence; not current qualification |
| --- | --- |
| Initial enhancement and ranking/cost review | [Two retained comparisons](evidence/quality-comparison-final-source-1.json), [repeat](evidence/quality-comparison-final-source-2.json), [research](research/RANKING_REVIEW.md) |
| Optimization and memory batching | [Benchmark methods/results](../../benchmarks/README.md#optimization-pass-2026-10-02), [format compatibility](evidence/optimization-format-compatibility-final.json), [memory batch](evidence/memory-batch-comparison.json) |
| Lookup, atomic PLAN and auxiliary ownership repairs | [Lookup integrity](evidence/release-lookup-integrity-independent-review-v3.json), [checkpoint](evidence/release-atomic-plan-independent-review.json), [auxiliary guards](evidence/release-auxiliary-lock-final-guard-independent-review.json) |
| Source797 layout/artifacts/heldout/history | [Preparation proof](evidence/release-layout-resolution-prepared-independent-review-v1.json), [historical benchmark ledger](../../benchmarks/README.md#historical-source797-release-benchmarks) |
| Historical sourceb2aa WebSocket repair and standalone regression | [Focused16](evidence/release-websocket-cleanup-focused-v1.json), [full13 and platform limits](evidence/release-full13-platform-skip-independent-review-v1.json) |


[NEXT_SESSION](NEXT_SESSION.md) owns the remaining sequence. Final documentation,
archive parity, installed snapshot and links require fresh checks before local readiness.
This historical checkpoint prohibited main-project delivery. Cleanup/commit/push were
subsequently authorized on2026-10-09; tags/publication remain separate owner actions. Hosted platform gates
require a reviewed committed candidate; owner publication is separate. Paid/live
providers, native assistant harnesses and live Docker isolation remain unqualified.

### Shared-host timing context, 2026-10-04

The user confirmed that other work was running during qualification. Round25 execution
correctness passes all three original samples: 136.189 / 256.755 / 140.620 seconds;
median140.620 seconds versus pooled55.870 seconds, retaining all nine references.
The existing boundary record reports 47.69% aggregate host activity and90% physical
memory load at both endpoints. These observations do not apportion the delay between
candidate work, external work, scheduling, paging or storage. Performance remains
inconclusive/blocked; neither the user confirmation nor a diagnostic timing closes
Master53. No external workload or global configuration was changed. The user subsequently requested stopping; any later timing qualification needs a declared quieter-host
window and unchanged workloads, references, checks and deadlines.

### User-requested pause, 2026-10-04

[Owned stop](evidence/release-user-requested-interruption-round25-v1.json) bound six
process generations/native handles, confirmed all exits and retained raw evidence.
[Pause verification](evidence/release-user-pause-guard-verification-v1.json) confirms
coordinator reaping, no launch-window descendants, source/input/helper/log stability
and unchanged HEAD. Raw controller STOPPED_ON_FIRST_FAILURE /4294967295 is an
administrative interruption, not a spontaneous product/assertion failure. Round25
stopped during baseline UI with no completed UI record; current UI, constrained and
fullPython remain UNRUN. No new tests were started after the pause. Existing diagnostic
and final-prose helpers require completed full24/25/finish admission and cannot be
launched unchanged after this interruption. Resume only on user instruction at a
quieter time, with fresh predeclared output names and reviewed successor admission.
