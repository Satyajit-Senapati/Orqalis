# Benchmark and quality evidence guide

The frozen labels in `engineering_cases.json` cover 14 engineering categories and 15
held-out retrieval probes. These are retrieval/routing inputs with linked deterministic
contract tests, not 29 live autonomous coding tasks. Do not tune labels to improve scores.

For the separate parallel execution/repair fixture, use the
[execution workflow](#deterministic-execution-workflow-evidence).

Use one interpreter/dependency environment and one frozen test tree for both source
revisions. For the G01 provenance correction, generate the reviewed compatibility tree:

```powershell
.venv/Scripts/python.exe -I scripts/freeze_contract_tests.py --baseline-source BASELINE_SOURCE --current-source CURRENT_SOURCE --validate
```

The default output is `.tools/research/contract-tests-v3`, pinned to parser `source-ast-v5`.
Version 3 retains the strict v2 graph assertions and writes the shared Git fixture as exact LF
bytes on every platform. This resolves the v2 branch-switch freshness failure caused by
Windows `write_text` CRLF translation followed by Git LF checkout. The failed v2 baseline
contract run remains in [raw evidence](../docs/quality/evidence/baseline-contracts-final-1.json).
Use `--fixture-version v1` or `v2` only to reproduce the preserved older corpora.
The generator starts from the immutable baseline tests, changes only the provenance assertion
block and the exact LF Git fixture writes, and rejects unknown parser profiles. Both source
profiles retain structural, source-evidence, persistence and cache checks; current binding candidates must carry inferred provenance, uncertainty and a
resolution basis. The recorded legacy profile is a compatibility contract, not an endorsement
of its binding certainty. The generator never overwrites a differing frozen test tree.

`docs/quality/evidence/contract-compatibility-v3.json` records source/test inventories,
parser profiles, selected test declarations, patch hashes and the two focused JUnit results.
Its sibling `.patch` records the complete amendment. Preserve the original unamended full
captures and their failures separately; unrelated failures still require investigation.
Use the generated root as `FROZEN_CONTRACTS` below, identically for baseline and current.
Run the contract suite before the measured capture:

```powershell
.venv/Scripts/python.exe scripts/run_quality_contracts.py --source-root BASELINE_SOURCE --tests-root FROZEN_CONTRACTS --output docs/quality/evidence/baseline-contracts.json
.venv/Scripts/python.exe scripts/run_quality_contracts.py --source-root CURRENT_SOURCE --tests-root FROZEN_CONTRACTS --output docs/quality/evidence/current-contracts.json
.venv/Scripts/python.exe scripts/benchmark_quality.py --source-root BASELINE_SOURCE --label baseline --contract-evidence docs/quality/evidence/baseline-contracts.json --output docs/quality/evidence/baseline-quality.json
.venv/Scripts/python.exe scripts/benchmark_quality.py --source-root CURRENT_SOURCE --label current --contract-evidence docs/quality/evidence/current-contracts.json --output docs/quality/evidence/current-quality.json
.venv/Scripts/python.exe scripts/compare_quality.py docs/quality/evidence/baseline-quality.json docs/quality/evidence/current-quality.json --output docs/quality/evidence/quality-comparison.json
```

Replace the source placeholders with absolute checkout/export paths. The frozen test
root contains the complete baseline `tests/` tree and its pytest configuration, with only
the audited compatibility amendment above.
The runner emits JUnit XML and a source-bound JSON report. Failed, skipped, missing and
unmatched test cases are explicit; none count as passes. Contract children that launch
`orqalis` or `python -m orqalis` are redirected to the selected source with an import-root
assertion. This qualifies the CLI contract against that source, not the installed launcher
or package artifact. Package verification remains separate.
Version-2 child-source policy covers synchronous CLI launches and AnyIO/asyncio event-loop
launches, including `python -I -m orqalis`. Windows' native overlapped-pipe process handling
is preserved. The failed baseline MCP version assertion exposed the previous async bypass;
[that 85/86 capture](../docs/quality/evidence/release-contracts-baseline.json) remains a
failure. The strict comparator requires policy v2 and fresh matching captures; old v1
reports cannot claim asynchronous isolation even when both source versions were equal.

The benchmark uses `-I`, strips inherited application/Python/pytest/Git overrides, disables
user/system Git configuration, sets process-scoped `core.autocrlf=input` for deterministic
Git fixture blobs, hashes its full package-resource inventory and dependency
manifests, and checks source/script/dataset/environment stability. Reports include installed
dependency versions and require the same Python/platform/dependency/sample environment for
comparison. Version 1 captures cannot be compared as version 2 evidence.

Graph cold means a parser-cache-cold rebuild after initialization; interpreter and OS caches
may be warm. Python allocation is one observed query, not process RSS. Source-read counts
exclude Git/subprocess/kernel reads. The context relevance channel counts matched graph and
full-memory provenance paths; explicitly marked orientation paths and memory discovery IDs
are separate. Long-memory retrieval/body-fetch quality is not inferred from a preview count.

The comparator reconstructs relevance from unique returned paths, checks dataset case counts
and labels, reports engineering and held-out partitions separately, and requires explicit
review for per-case precision/recall/MRR/nDCG losses. Unmarked negative-query results, wrong
skill selections, permission/pin failures, content mismatch and lost progressive disclosure
fail. An unsupported portable adapter is expected for baseline; current must support it.

`PASS` means the specified deterministic gates passed. It does not establish an improvement
on every workload, model instruction adherence, autonomous task success, observed token
savings, network exporter behavior, Docker isolation, or native assistant qualification.
Missing contract evidence produces `REVIEW`; raw evidence and witnesses remain reviewable.


## Metric definitions and label scope

Gold paths are primary targets, not exhaustive relevance judgments. A returned path outside
that list may still be useful; `precision_at_k` is **labeled-target precision**, and a loss
requires inspecting the paths rather than automatically declaring worse engineering quality.
Each channel deduplicates paths before scoring the first `retrieval_k` (currently 5):

- Recall: distinct labeled targets returned divided by the number of labeled targets.
- Precision: labeled targets returned divided by the number of returned paths, which can be
  smaller than `k`; an empty result has precision zero.
- MRR: reciprocal rank of the first labeled target, or zero when none appears.
- nDCG: binary labeled relevance discounted by `log2(rank + 1)`, normalized by the ideal
  top-k order. Unlabeled negative cases have null recall/nDCG, not fabricated perfect scores.
- Negative returned paths: the count of unmarked returned paths for a no-target query.
  Explicit graph orientation has its own path witness and is not graded as a claimed match.
- Context size: actual serialized UTF-8 bytes and Python Unicode character count. The
  configured cap is on serialized characters, including metadata. Neither is a token count.
- Routing FP/FN: set differences between expected and actual deterministic capabilities.
  Selected skill IDs are checked separately against independent bundled-skill expectations;
  permission/pin cases and typed serialization round-trips are separate witnesses.
- Latency: monotonic wall-clock milliseconds, raw samples, median and nearest-rank p95.
  Graph cold and one-file-change have one sample each; other timed operations use `--repeat`.
  A three-sample p95 is the maximum observed sample, not a reliable tail-latency estimate.
- Reads: Python `open` events classified as repository source or canonical memory records.
  Unique-file counts and operation counts differ; parser cache hits do not imply zero reads.
- Storage/allocation: actual generated file bytes and Python `tracemalloc` peak for one
  context query. These exclude installed dependency disk size and native/process RSS.

`cases` retains every witness, `partitions` separates engineering and held-out results,
`summary` contains validated aggregate invariants, and `portable_skills` demonstrates
metadata/body/reference disclosure on an explicitly generated own-documentation fixture.
The raw dependency inventory and full source file inventory make the measured inputs
reviewable. Contract JSON binds JUnit outcomes to source, dataset, test-tree and runner
fingerprints; its separate `live_engineering_task_success` is null.

The comparison exits 0 only for `PASS`. It exits 1 for `FAIL` or `REVIEW`, preserving the
written comparison report. Schema/input/environment mismatches raise an error instead of
writing a misleading comparable result. `FAIL` means a deterministic invariant failed;
`REVIEW` means missing evidence, a per-case relevance loss, a fixture change, or a timing
investigation budget requires analysis. Keep these outcomes visible; do not edit labels,
remove failing cases, or translate `REVIEW` into success. Run timing captures without
concurrent test/build workloads when practical and retain the raw samples.

Contract evidence schema 2 additionally binds the exact loaded quality-helper bytes and
checks helper, runner and dataset stability. The comparator rejects older helperless
captures. Preserve them as raw preflight evidence; do not upgrade their schema by editing JSON.

The explicit Git line-ending policy corrects the original Windows CRLF fixture failure;
its raw failed JUnit result remains preserved. It changes neither frozen assertions nor
repository/global Git settings. The separate execution fixture writes fixed LF bytes and
uses its own explicit `core.autocrlf=false` policy, recorded in that harness.

---

## Deterministic execution workflow evidence

`scripts/benchmark_execution.py` runs the fixed
`parallel-read-one-repair-reviewed-execution-v1` fixture against an explicitly selected
source tree. Real orchestration, worktree writes, acceptance checks and persisted events
run with an injected deterministic fake provider. This measures a controlled execution
workflow; it does not measure live-model coding quality, tokens or provider cost.

The fixture requires these independent outcomes:

- Exactly **9 successful provider invocations**: architect **2**, developer **4**, repair
  **1**, reviewer **2**. Developer calls include the write request and its follow-up.
- Exactly **2 successful `filesystem.write` invocations**, both owned by developer actors,
  with distinct provider parents and matching actor/task-attempt ownership.
- Two concurrent preparation tasks, a deliberately wrong first write (`answer = 41`),
  reviews `FAIL` then `PASS`, and exactly **1 repair** producing `answer = 43`.
- Final acceptance passes, the current plan is complete, and no blockers remain. The run
  stops in `REVIEWING` after the passing review. Documentation, Git delivery and push do not
  run; the original repository still contains `answer = 42`.

First-pass acceptance is deliberately false. It is a fixture witness, not a model accuracy
score. The fake provider supplies no usage/cost; missing reported values remain null.

### Run and compare

Use the same interpreter, dependencies, runner and `--fixture-root` for both revisions.
The fixture root supplies exactly three helpers, copied into a disposable frozen directory:
`tests/__init__.py`, `tests/support/filesystem.py`, and `tests/support/trace_fixture.py`.
Select immutable baseline production code with `--source-root`; do not substitute baseline
helpers for one side. The following paths assume this workspace and its retained baseline:

```powershell
.venv/Scripts/python.exe scripts/benchmark_execution.py --source-root S:/Orqalis/.tools/research/baseline-b8506f7 --fixture-root S:/Orqalis --label baseline --mode smoke --repeat 1 --output docs/quality/evidence/baseline-execution-smoke.json
.venv/Scripts/python.exe scripts/benchmark_execution.py --source-root S:/Orqalis --fixture-root S:/Orqalis --label current --mode smoke --repeat 1 --output docs/quality/evidence/current-execution-smoke.json
```

`--mode smoke` is the default. Unlike the memory/UI smoke runners, it retains numeric timing
samples for diagnosis, but `summary.timing_qualified` is false. Do not compare those timings
as performance evidence. `--repeat` accepts 1..10 and defaults to 3 in either mode; use an
explicit repetition count.

After test/build/diagnostic workloads finish, capture each revision sequentially:

```powershell
.venv/Scripts/python.exe scripts/benchmark_execution.py --source-root S:/Orqalis/.tools/research/baseline-b8506f7 --fixture-root S:/Orqalis --label baseline --mode capture --repeat 3 --output docs/quality/evidence/baseline-execution-measured.json
.venv/Scripts/python.exe scripts/benchmark_execution.py --source-root S:/Orqalis --fixture-root S:/Orqalis --label current --mode capture --repeat 3 --output docs/quality/evidence/current-execution-measured.json
```

Alternate revision order across repeated comparative captures and retain separate output
names. Capture mode asserts an externally coordinated quiet environment; it does not detect
machine idleness. Before comparing samples, require complete passing reports, stable inputs,
identical runner/helper/fixture/environment hashes and equal repetition counts. Production
source fingerprints should identify the intended distinct revisions. The quality-report
comparator does not accept these execution-report schemas.

Each repetition uses a fresh isolated Python child and disposable repository/worktree.
`--scratch-root` defaults to `.tools/research`; the runner verifies its temporary workspace
stays within that root. Python `-I`, explicit import paths and loaded-module checks bind
Orqalis to the selected source and fixture imports to the frozen helper tree.

The four repository fixture files are written as fixed UTF-8/LF bytes. Git runs with explicit
`core.autocrlf=false`, disabled hooks/signing, fixture identity and fixed author/committer
dates. Inherited application/Python/pytest/Git/OTel overrides and user/system Git configuration
are removed; OTel SDK export is disabled. This is the execution harness's explicit policy,
separate from the contract runner's `core.autocrlf=input` normalization of Windows fixtures.
These policy overrides are process/command-scoped; they do not modify global Git settings
or persist overrides in the fixture repository.

### What the report proves

Each sample reloads the authoritative run and compares its outcome with the original
snapshot. Canonical provider/tool records are joined to snapshot projections and durable
started/completed events by invocation UUID. Checks require unique IDs, exact record/event
counts, matching run/actor/task-attempt/status/timestamps, start-before-terminal order, and
valid tool-provider ownership. Orphan, duplicate or missing records/events fail; matching
aggregate counts alone cannot pass. Event sequences must be contiguous, idempotency keys
unique, and the snapshot cursor equal the persisted event count.

Reports retain those identity witnesses, every boolean check, event-type counts, loaded
module locations, fixture commit, and hashes of persisted `execution/state.yaml` and
`execution/events.jsonl`. The complete selected package-resource inventory plus `pyproject.toml`
and `uv.lock`, all three helper files, runner, fixture bytes and environment are fingerprinted.
Environment evidence includes interpreter binary/version, Git version, platform, dependency
versions and policy. Worker/parent fingerprints and pre/post stability must agree.

`execution_elapsed_ms` spans fixture initialization, run/plan setup, pause/resume, execution,
acceptance, repair and passing review. It excludes interpreter startup, initial fixture Git
setup and the subsequent reload/accounting checks. Those costs remain distinguishable through
`repository_setup_elapsed_ms` and `child_process_elapsed_ms`. Persisted run timing is an
additional event-derived view: active/waiting time is not CPU time, and concurrent task times
are not summed as elapsed time. Raw samples, median and nearest-rank p95 are retained; three
samples do not establish tail-latency guarantees. OS caches may be warm.

The report starts as `complete=false` and is updated atomically as samples arrive. A failed
worker, inconsistent identity, changed input or failed fixture check cannot qualify a capture.
Retain incomplete/failed JSON and terminal output, as well as earlier reports, under distinct
names. A correction requires a new capture; do not edit checks, expected role counts, fixture
behavior or old reports to turn a failure into PASS. Script/helper changes invalidate earlier
comparability even if the schema version is unchanged. Calibration and false-PASS regressions
are in `tests/unit/test_execution_benchmark.py`.

---

## Durable memory workflow evidence

`memory_workflows.json` fixes three illustrative engineering cases: webhook idempotency
retention, repeated-hour dispatch scheduling, and tenant cache namespaces. Each has six
small repository files, a long approved decision, an overview referring to that decision,
unrelated approved conventions, and an immutable superseded predecessor. Gold policy
sentences are absent from repository source, so successful source inspection alone cannot
stand in for retained project knowledge. Gold source branches are checked separately.
These are deterministic knowledge-recovery fixtures, not live autonomous coding tasks.

The script compares **current-version workflows**, not current versus released Orqalis:

1. `full_rediscovery` asks the current Context Builder for bounded orientation, reads every
   fixture source file, and loads all active curated records. This is an explicitly less
   selective workflow baseline; it is not a claim about how every assistant uses Orqalis.
2. `progressive_memory_then_symbol` discovers one overview, reads its explicit reference,
   fetches up to three fixed body pages, finds the named symbol, and fetches its complete
   hashed byte span. It selects the reference from returned data. The page limit does not
   depend on whether the gold sentence has appeared.
3. `restart_direct_memory` closes the earlier SDK and opens a new one with only the retained
   detail ID. It fetches up to three pages and must recover the durable fact again. Its
   declared witness scope excludes source verification, so it is not scored as an equivalent
   complete-code-inspection workflow. No record object or provider session is reused.

The first two workflows alternate order across repetitions. All start with a fresh SDK
object and initialized warm graph/parser files. They are not new interpreter processes or
OS-cache-cold measurements. Initialization and an independent explicit historical read are
outside measured workflow stages; SDK reconstruction is inside. Historical reads must show
the unchanged predecessor body, `SUPERSEDED` state and the active successor ID.

Run the correctness-only smoke at any time:

```powershell
.venv/Scripts/python.exe scripts/benchmark_memory.py --smoke --output docs/quality/evidence/memory-workflow-smoke.json
.venv/Scripts/pytest.exe -q tests/unit/test_memory_benchmark.py
```

The smoke disables all reported timings and runs one repetition. Capture timing only after
other test/build workloads have finished, using the same interpreter and dependency set:

```powershell
.venv/Scripts/python.exe scripts/benchmark_memory.py --source-root S:/Orqalis --repeat 5 --label current-memory-workflows --output docs/quality/evidence/memory-workflow-measured.json
```

The runner launches an isolated Python child, strips inherited application/Python/Git
configuration overrides, verifies the imported package path, and binds the report to source,
script, fixture and dependency inputs. It rejects source or dependency changes during capture.
`--source-root` may select a compatible checkout; old releases without progressive APIs are
rejected rather than silently substituted. The report names immutable v2.0.0 as an unmeasured
reference and sets `release_baseline_measured` to false.

Each stage records actual serialized response characters and UTF-8 bytes, individual API
caps, explicit returned IDs/paths, exact answer witnesses, and cumulative read counters.
The full rediscovery source/full-memory payloads are deliberately uncapped; the bounded
Context Pack and every progressive response must fit their configured caps. Memory discovery
and body pages use 1,800 characters; context and symbol responses use 4,000. The total of
several individually bounded responses is reported separately and is not called one cap.

Read counts distinguish source, canonical memory and metadata files. Instrumentation wraps
Python `Path.open` reads and counts actual returned content, including repeated reads and
zero-byte EOF reads; open operations and unique paths are separate. UTF-8 bytes describe
returned content, not physical disk transfers. Git subprocess, kernel cache and native-library
I/O are outside this counter. Calibration tests check Unicode and immutable stage snapshots.

Discovery currently reads local canonical record bodies. Each body page also loads its
canonical record, so pagination can reread a long body and increase local bytes read even
when returned context is smaller. Small previews do not establish lower memory-file I/O.
Selected result sets share one lifecycle parse and one source hash per path within the
request; they do not retain a cross-request cache. Page-size trials stay within the
serialized response budget, but the canonical record is still parsed on each page.
The [measured read comparison](../docs/quality/research/KNOWLEDGE_RESEARCH.md#project-memory-storage-and-read-optimization)
records both the benefit and the unchanged I/O. A source-bound decision hashes its
declared source during each new freshness check, so explicit memory reads can still open
that source.
User-origin decisions have no source hash to validate. Both behaviors are measured separately.
Symbol calls invoke graph refresh; a warm unchanged graph can avoid rereading source, while
other states can require source analysis. The report retains both refresh count and observed
source reads. It does not claim the automatic Context Builder always avoids repository scans.

Relevance uses fixed fixture targets and deduplicated explicitly returned IDs/source bodies.
The report includes target recall/precision and exact policy/code witnesses. These labels do
not prove semantic correctness beyond the checked branches or general natural-language
retrieval quality. Timed captures retain raw monotonic samples, median and nearest-rank p95
for time to the durable fact, plus per-stage and complete-workflow times. Instrumentation
cost is included. Three or five samples do not establish stable tail latency.

Observed model tokens, provider cost and autonomous task success remain null because no
provider runs. Character counts are never converted into purported observed token usage.

---

## Qualified local browser event benchmark

Build each revision from its own `web` inputs in a disposable copy. The immutable baseline must not be built in place; the helper refuses an existing output directory and never writes the selected web tree. Reused `web/node_modules` requires byte-identical package locks. The manifest inventories selected source, actual dependency files, build tool and resulting artifact, with a temporary Git ignore boundary to keep Tailwind out of dependency sources.

```powershell
.\.venv\Scripts\python.exe scripts/build_benchmark_frontend.py --source-root S:\Orqalis --output S:\Orqalis\.tools\research\ui-current-qualified
.\.venv\Scripts\python.exe scripts/build_benchmark_frontend.py --source-root S:\Orqalis\.tools\research\baseline-b8506f7 --output S:\Orqalis\.tools\research\ui-baseline-qualified
.\.venv\Scripts\python.exe scripts/benchmark_ui.py --source-root S:\Orqalis --frontend S:\Orqalis\.tools\research\ui-current-qualified\dist --output S:\Orqalis\docs\quality\evidence\ui-current-smoke.json --smoke
```

Use the same command with baseline source and baseline frontend to qualify the baseline. The default build evidence is `frontend.parent/build.json`; `--build-evidence` can point to a retained copy. Evidence from a different selected web revision, changed tools/dependencies, or changed artifacts is rejected. A new capture immediately invalidates prior output to RUNNING and failures overwrite it with FAIL; stale PASS output cannot qualify a failed rerun. Helper and harness changes invalidate prior qualifications and require requalification as appropriate.

Each action must return the selected run/state and a newer persisted event cursor. The WebSocket must deliver the exact command's run event and a snapshot with that cursor. The DOM must show the expected state and the same footer cursor on the exact run route. Reports include unique command/event IDs and before/event/persisted/snapshot/DOM cursors, plus stable source, script, helper, tool and frontend inventories. Chrome is launched from an explicitly hashed executable, with the actual Playwright dependency tree bound too.

`--smoke` performs one pause/resume pair by default and emits null timings. Use `--smoke --repeat 3` for repeated correlation calibration while still suppressing timings. A later quiet capture without that flag performs three pairs and reports warm request-to-HTTP/event/snapshot/DOM timings. Build, dependency hashing and evidence checks occur outside the measured action intervals. This is localhost state propagation, not network/provider latency or all dashboard behavior. Alternate revision order across repeated captures; concurrent smoke output is never used for timing comparisons.

Calibration: `pytest tests/unit/test_benchmark_ui_evidence.py -q`. Wrong run/revision/event/sequence and changed inputs must fail before comparing measurements.

---

### UI calibration development history

2026-09-26. These are correctness-only harness development captures, not an estimated production success rate and not timing evidence.

1. Initial isolated current and baseline build qualifications passed. Both initial one-pair browser smokes passed exact run/command/event/persisted/snapshot/DOM correlation.
2. The build inventory was strengthened to exclude generated directories only at web root, preserving real source folders such as `src/dist`; both revisions were rebuilt in new `ui-*-qualified-2` directories.
3. During subsequent development, one current one-pair recapture failed with `Missing correlated command/event/snapshot/DOM witness`. The earlier harness did not retain individual mismatch details, so the absent component and cause cannot be reconstructed. Baseline recapture passed. This failure is not attributed to production code without evidence and is not claimed causally fixed.
4. The harness added bounded mismatch diagnostics (command, exact cursors, recent matching events/snapshots, DOM/footer/route, WebSocket open/close/error and owned server log), invalidates reused output before starting, and overwrites failures with FAIL. Twenty-five adversarial calibration tests pass, including a subprocess test that starts with an old PASS report and requires its replacement after failure.
5. The next current diagnostic completed both exactly correlated transitions but rejected qualification when the helper/production source changed during capture, as expected from concurrent edit broadcasts. The final wrapper preserves already-produced observations when stability fails.
6. After both source owners signaled stability, identical final `--smoke --repeat 3` captures passed for current and baseline. Each has six samples and no page errors; every persisted, WebSocket snapshot and rendered DOM cursor matches (19, 22, 25, 28, 31, 34). Each command's durable event cursor lies between the preceding and resulting cursor. Every timing field is null. Source, frontend, actual dependencies, tools, builder, helper and scripts stayed stable.

Final machine-readable [current capture](../docs/quality/evidence/ui-current-smoke-qualified.json) and [baseline capture](../docs/quality/evidence/ui-baseline-smoke-qualified.json) retain inventories and command/event witnesses. Their backend source fingerprints are respectively `a37dda9e2ca4d37e58ffc6fcab606324df31e16b02dc1261a3371cd44792a757` and `7dcede8468792d5c51805bb3fc865f09370892ba6ca101d40dcfd6b840fcbad7`. Current and baseline selected web inventories contain 52 and 45 files; each build binds 7,760 actual dependency files and nine artifact files. Chrome was 153.0.8010.54 in both.

The witness predicate was preserved: same full run ID, unique command key, correct durable event type/key/ID, strictly advancing cursor, matching persisted/snapshot/DOM cursor, correct route and state, ordered finite timestamps. Repetition or lower load is not asserted to explain the earlier failure. A later formal capture must preserve and diagnose any renewed failure rather than quietly retrying it out of the measurements. These smokes do not qualify UI timing, arbitrary reconnect behavior, live model usage or all dashboard interactions.

---

## Constrained local workload

Run baseline and current sources in the same Windows interpreter/dependency environment:

```powershell
.venv/Scripts/python.exe -I scripts/benchmark_constrained.py --source-root BASELINE_SOURCE --output BASELINE_OUTPUT.json
.venv/Scripts/python.exe -I scripts/benchmark_constrained.py --source-root CURRENT_SOURCE --output CURRENT_OUTPUT.json
```

Use `--smoke` to verify correctness without recording unqualified timing. Use a new output
path per capture and retain failed or interrupted runs as preflight evidence.

The harness launches its own isolated child, removes application/Python/Git overrides,
verifies imports from the selected source, and applies a Windows Job Object to that child.
The kernel enforces one allowed CPU and a 256 MiB **per-process committed-memory** limit.
The job's close policy terminates its owned descendants if the worker exits. This changes
no machine-wide memory/CPU policy and requires no provider, GPU, database or Docker daemon.

The actual workload initializes a disposable Git repository containing 20 Python service
files and a TSX component, checks an unchanged graph refresh processes zero files, and
builds context at 1,000 / 4,000 / 12,000 serialized-character caps. Each response must retain
an actual service-file witness. Exact requested flags, affinity and memory limit are read
back from the kernel, and measured peak process commit must be nonzero and below the cap.
Selected source, own script, helper script and environment must remain unchanged.

Elapsed time covers imports and this workload; later evidence hashing/environment inventory
is excluded. One elapsed sample is descriptive, not a tail-latency estimate. Peak process
commit is neither RSS nor a whole-machine / whole-job RAM measurement. These small fixtures
do not qualify large repositories, live models, browsers or cross-platform resource caps.

Primary API references: [Windows extended job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
and [basic limit flags and affinity](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).


## Optimization pass, 2026-10-02

This pass compares the frozen **pre-optimization enhancement candidate**, not released
v2.0.0, against the corrected optimization candidate. [Source identity](../docs/quality/evidence/source-inventory-optimization-final.json)
and [qualified comparison](../docs/quality/evidence/optimization-quality-comparison-final.json)
bind the final source. The 29 queries, four durable facts, three repeats and frozen
labels are unchanged; both sources use parser profile v5 and lexical-v3. Both passed
86 frozen contracts on Windows build 26300. Historical build-26200 contracts were
[rejected](../docs/quality/evidence/optimization-preflight-rejections.json); the
[fresh-evidence binding proof](../docs/quality/evidence/optimization-baseline-rebind-proof.json)
preserves every original timing/data field. Comparison is PASS with zero new per-case
metric losses or failed invariants. The earlier released-baseline 30-loss REVIEW remains
historical and still needs acceptance disposition.

| Metric | Pre-optimization | Corrected candidate | Observation |
| --- | ---: | ---: | --- |
| CLI version, alternating six-sample probe | 1,223 ms | 865 ms | -29.2% |
| CLI help, alternating six-sample probe | 1,337 ms | 988 ms | -26.2% |
| MCP startup, three-sample corpus batch | 1,940 ms | 2,177 ms | +12.2% |
| Graph bytes | 2,243,664 bytes | 1,641,247 bytes | -26.8% |
| Index bytes | 6,471,050 bytes | 5,680,850 bytes | -12.2% |
| Total project-store bytes | 9,240,083 bytes | 7,847,466 bytes | -15.1% |
| One-query Python peak allocation | 13,529,515 bytes | 13,629,128 bytes | +0.7% |

The [startup probe](../docs/quality/evidence/optimization-startup-final.json) alternates
source order across six fresh processes each. Disk reductions follow compact **derived**
graph/index JSON; existing pretty-printed artifacts remain readable and compact when
next rebuilt. Canonical memory/tasks stay readable in their original formats. The
[compatibility probe](../docs/quality/evidence/optimization-format-compatibility-final.json)
reopened actual old graph/index artifacts without rewrite/rebuild and retained identical
ranked matches. Python allocation is tracemalloc for one query, not whole-process RAM;
no RAM reduction or MCP latency win is claimed. Other wall-time batches vary too:
unchanged graph refresh was slower in this batch, while cold/changed refresh was faster.
These samples do not establish tail latency or cross-machine speed.

[History review](../docs/quality/evidence/optimization-history-review.json) retains three
1001-capsule, three-traversal pairs. Every traversal returned all IDs once in 11 pages.
The corrected-source median was 249 ms against 266 ms for the frozen source in its last
pair, but a corrected-source page reached 23.4 s. Earlier pairs had different median gains
and large outliers. Unchanged pages avoid index replacement/fsync/read-back; canonical
metadata and filesystem boundaries are still checked on every request, including
same-size/same-mtime edits. This is reduced redundant work, not a consistent twofold gain.
[Diagnostic profiles](../docs/quality/evidence/optimization-history-diagnostic-review.json)
also reproduced a 6.2 s frozen-source stall (1.1 s process CPU); they ran alongside
correctness checks, so filesystem wait versus scheduler/resource interference is unproven.
No timeout or path guard was weakened. Investigate representative larger histories next.


The [current history implementation mapping](../docs/quality/evidence/release-history-source-mapping-final.json)
compares the entire store class, history file and direct dependencies against exact retained
source755-bound bytes. They remain unchanged at source47; this is code continuity proof,
not a new 1,001-row execution. Preserve the historical 17.46 s read tail, unblocked
104/44 ms reservations and pending current full history/regression qualification.

Corrected-source validation passed 77 focused checks, 86 contracts, full static gates,
nine exact-answer/cap/history memory workflow samples, execution smoke, and a one-CPU /
256-MiB process-commit smoke (49,250,304 bytes peak). The [full regression](../docs/quality/evidence/full-regression-optimization-1.json) passed
748 cases with two explicit Docker-image/Windows-symlink environment skips and no failures.
The source, test inventory, helper and environment stayed stable throughout that run.
The [isolated wheel](../docs/quality/evidence/installed-wheel-optimization.json) and
[17 installed npm checks](../docs/quality/evidence/installed-npm-optimization.json) passed
locally on Windows. No package was published. Release qualification remains 0 / 2 clean
full audit iterations; Docker, Linux/macOS installed runtime and paid-provider quality
are outside these checks.

## Historical 2.1.0 larger-corpus qualification

The source-640 [baseline](../docs/quality/evidence/release-heldout-baseline-v5.json),
[candidate](../docs/quality/evidence/release-heldout-current-v5.json) and
[summary](../docs/quality/evidence/release-heldout-review-v5.json) use the same immutable
263-file / 1,812,392-byte real-code/documentation slice. Candidate source is
`640c2988804e3117e8cb844a593b1b3afc4fdd1dc1023351afe073e3e0493769` on the frozen
Windows/Python dependency environment. This is one larger slice with three exact target
witnesses, not a universal relevance or performance assessment.

| Measurement | Released baseline source | Candidate source |
| --- | ---: | ---: |
| Graph nodes | 3,533.00 | 11,505.00 |
| Graph edges | 10,003.00 | 13,575.00 |
| Graph bytes (MB) | 4.85 | 8.25 |
| Index bytes (MB) | 9.50 | 28.85 |
| Store bytes (MB) | 16.29 | 39.78 |
| Python query peak allocations (MB) | 30.50 | 65.66 |
| Parser-cache-warm rebuild (ms) | 1,823.09 | 2,285.76 |
| Unchanged refresh median (ms) | 394.12 | 737.68 |
| One-file refresh (ms) | 1,828.37 | 3,068.29 |
| Context median (ms) | 681.74 | 1,263.80 |

Both implementations pass exact ProjectGraphEngine, ProjectContextBuilder and TaskCapsuleStore
index-first/context-presence witnesses with a 12,000-character cap. Unchanged refresh
parses zero files and one-file refresh parses one. Candidate facts are richer: most added
nodes are distinct source-reference occurrences, with substantially more TypeScript facts.
The storage and allocation increases are real; no lower-RAM claim is justified. Allocation
is tracemalloc, excluding native memory and process RSS. This probe's PASS is functional;
it has no built-in timing acceptance gate and raw sample arrays are not retained.

That source-bound run's cold/warm/delta/context medians stay below the investigation threshold
`2 * baseline + 250 ms`. Earlier source-bound v3/v4 captures crossed graph thresholds;
their raw data and phase diagnostics remain preserved. A quieter later run does not identify
the OS cause or remove tail-latency risk. Runtime analysis observed off-process-CPU waiting
and real richer-fact CPU cost; it did not prove a particular filesystem/kernel cause.
Independent disposition and both complete release rounds remain separate requirements.


## Release graph digest investigation and bounded proof

Source47's fixed263-file heldout v8 passed functional checks but retained a2680.00ms warm
median versus1091.03ms baseline, above the2432.06ms investigation line. One predeclared
ABBA diagnostic retained all12 samples: median process CPU1085.94ms versus242.19ms, with
canonical graph digest515.63ms inside graph load1031.25ms. Nested timings must not be
summed; process CPU excludes Git children, and the4884.54ms wall tail remains unexplained.
[Raw diagnostic](../docs/quality/evidence/release-heldout-warm-diagnostic-review-auxiliary.json)
and [design review](../docs/quality/evidence/release-heldout-warm-optimization-design-review.json)
preserve those results without rewriting v8 or adjusting its threshold.

Candidate `1e3fc528...` retains only one raw-byte SHA/model-digest pair per engine. Every
load still strictly decodes the same bytes hashed, validates fresh models and checks the
current manifest/schema/parser. Only explicit graph timestamps qualify; failures clear
the proof and link policy still propagates. Returned models cannot poison later loads.
The cache helps retained engine/context-builder calls. SDK/MCP paths constructing fresh
instances do not reuse it across requests; index search does not consult the engine, and
index rebuild writes a new graph. The sourceb7f v10 capture below measures the retained
engine/builder behavior. Complete release rounds remain pending; there is no universal
latency or tail-cure claim.


## Historical sourceb7f history and no-commit heldout capture

The sourceb7f [fresh history probe](../docs/quality/evidence/release-history-current-b7f.json)
passes three traversals covering all1,001 rows once in stable order, with a concurrent
reservation completing in45.10ms. Across33 pages, median wall time is681.75ms,
maximum1764.05ms and maximum aggregate lock acquisition0.57ms. These are descriptive
local observations; earlier17.46/23.4-second read tails remain preserved.

Automatic approval review rejected heldout v9 before execution because its fixture
commits conflict with the user's no-commit instruction. The
[v10 methodology record](../docs/quality/evidence/release-heldout-no-commit-method-v10.json)
preserves the helper change: fresh copies of the exact263-file corpus receive only
already-existing Git metadata and the retained ignore file, with clean-status and
unchanged-HEAD guards. No commit is created. The workload, repeat counts, functional
assertions and separate investigation threshold remain unchanged. The method record
is the immutable pre-execution plan; the following raw report proves completion.


The [paired v10 capture](../docs/quality/evidence/release-heldout-review-v10.json) passes
functional witnesses with stable baseline/current source and environment identities.
Both fresh fixtures retain the copied existing HEAD `be00c39a5a86bb737404fdca9f6e19ebf1f66bdf`.

| Measurement | Baseline | Sourceb7f candidate |
| --- | ---: | ---: |
| Parser-cache-warm rebuild (ms) | 3371.20 | 1838.28 |
| Unchanged refresh median (ms) | 664.97 | 462.10 |
| One-file refresh (ms) | 3590.54 | 2061.38 |
| Context median (ms) | 1358.87 | 1027.89 |
| Python query peak allocations (MB) | 30.50 | 56.67 |
| Graph nodes | 3533 | 11505 |
| Store bytes (MB) | 16.29 | 39.78 |

All four timing costs are below the unchanged `2 * baseline + 250ms` investigation
lines for this paired run. PASS remains functional; timings are descriptive and raw
sample arrays are not retained by this helper. Richer facts still cost more storage
and query allocation than the released baseline. Tracemalloc excludes native memory
and RSS. Different revisions/runs do not isolate the digest optimization's causal
benefit or remove prior wall tails. Neither full qualification round is complete.

[Independent verification](../docs/quality/evidence/release-current-benchmark-independent-review-v10.json)
recomputed corpus/source/environment/Git identities, all four timing comparisons and
current history coverage/order. It retains allocation costs, earlier tails and browser
failures, with no P1 closure or release certification.

## Historical source797 release benchmarks

Measurements in this section remain bound to source797. The later sourceb2aa capture is recorded below.


The [fresh paired capture](../docs/quality/evidence/release-heldout-review-v12.json)
uses the same263-file/1,812,392-byte corpus and retained Git metadata. Both sources pass
exact retrieval, bounded context and zero/one-file incremental witnesses with stable
source/environment identities. Candidate fingerprint is
`79708defe1e43dc90b33a9e79bbe05de5ee913af12ecaee3b161417732600a35`.

| Measurement | Baseline | Current candidate |
| --- | ---: | ---: |
| Parser-cache-warm rebuild (ms) | 2271.24 | 2736.68 |
| Unchanged refresh median (ms) | 452.95 | 447.10 |
| One-file refresh (ms) | 1920.29 | 2308.19 |
| Context median (ms) | 975.13 | 893.30 |
| Python query peak allocations (MB) | 30.50 | 56.67 |
| Store bytes (MB) | 16.29 | 39.78 |

All four timings are below the unchanged `2 * baseline + 250ms` investigation lines.
Warm refresh and context medians are lower; rebuild and one-file refresh are higher.
Richer facts retain higher storage and Python allocation costs. Tracemalloc excludes
native memory and RSS; these observations are descriptive and do not isolate a causal
benefit or establish a latency guarantee.

The [fresh1,001-row history capture](../docs/quality/evidence/release-history-readpath-1001-v1.json)
passes three traversals/33 pages with exact unique coverage and stable order. Page-wall
median is194.81ms and maximum360.78ms; maximum aggregate lock
acquisition is0.27ms. The separate real concurrent reservation completes in
29.97ms with a unique ID and created directory. Historical17.46/23.4-second tails
remain preserved. Neither required complete qualification round is finished.

[Independent current verification](../docs/quality/evidence/release-current-benchmark-independent-review-v12.json)
recomputes corpus/source/environment/Git identities, the unchanged four investigation
thresholds, canonical history hash and owned-copy reservation. No new timing trigger or
binding/functional defect is found; full qualification remains separate.


## Historical sourceb2aa release observations

The [fixed263-file pair](../docs/quality/evidence/release-heldout-review-v13.json)
passes its retrieval/context witnesses on the original1,812,392-byte corpus. The
context response cap is12,000 characters, not UTF-8 bytes. Fresh parser-call counters
are absent from these reports; inherited zero/one-parse assertions do not supply
fresh measured counts. These observations retain their actual source and environment.

| Measurement | Immutable baseline | Sourceb2aa candidate |
| --- | ---: | ---: |
| Parser-cache-warm rebuild (ms) | 5159.56 | 6071.16 |
| Unchanged refresh median (ms) | 1034.56 | 1042.51 |
| One-file refresh (ms) | 4380.82 | 5351.68 |
| Context median (ms) | 2085.81 | 1612.92 |
| Python query peak allocations (MB) | 30.50 | 56.67 |
| Store bytes (MB) | 16.29 | 39.78 |

None of the four paired timings crosses the existing `2 * baseline + 250ms`
investigation line. Both sources have higher absolute graph times than v12; this
pair does not explain that variation. Richer facts retain higher storage/allocation
costs. Python tracemalloc is not native memory or process RSS.

The [1,001-row history witness](../docs/quality/evidence/release-history-websocket-1001-v1.json)
passes all three traversals/33 pages with stable canonical bytes, exact unique
coverage and ordering. The concurrent reservation completes in70.48ms. Page-wall
median662.69ms is3.402x the earlier194.81ms; median process CPU625ms versus187.5ms
also increased. Maximum page1139.20ms and lock acquisition0.864ms remain recorded.
[Independent review](../docs/quality/evidence/release-current-benchmark-independent-review-v13.json)
leaves history performance unresolved. The historical17.46/23.4-second tails remain
visible and cannot substitute for the faster comparison or justify acceptance.

[Incomplete capture16](../docs/quality/evidence/release-execution-current-16.json)
stopped after one93.38-second passing execution sample: repetition1 failed Windows
atomic replacement of `task.yaml` after the existing bounded retries. The denying
process and cause are unproven. Capture17 never ran; neither capture earns
convergence credit. The [active worklist](../docs/quality/NEXT_SESSION.md) owns
diagnosis and remaining release gates. No metadata matching or host boundary
snapshot establishes an otherwise quiet host.

## Successor Windows reliability candidate

The qualified runtime has application SHA256
`24ffafca60dc7d153d92006445096d0c92ad057f04692349355387638bfda708`;
[portable input freeze](../docs/quality/evidence/release-input-freeze-cleanup-portable-v3.json)
aggregate `97e7f0a386979e296c6ee8581c4edcadf7b48c8d9565540e5443f62531ebcb9f`.
[Accepted reuse](../docs/quality/evidence/release-source-freeze-portable-reuse-accepted-v2.json)
binds unchanged runtime and one corrected public portability test to initial proofs;
raw older source/input identities remain intact. Five-attempt Windows replacement
handling adds at most 300 ms scheduled backoff per affected atomic write; cleanup
clears READONLY only on guarded regular owned temporaries and preserves primary errors.
The original denying process remains unknown.

Both complete [20](../docs/quality/evidence/release-iteration-20.json) and
[21](../docs/quality/evidence/release-iteration-21.json) exited successfully. Their
full suites each collected **908: 906 PASS, 0 FAIL/ERROR, 2 explicit SKIP**, with all
five identity checks true. Each has 14 passing browser cases, three clean advisory
gates and all fresh execution/memory/UI/constrained stages. The development Python
audit has 63 third-party packages; the initial installed wheel/npm inventories each
have 51, including pip26.2.1. Inventories/dates are distinct, not interchangeable.
[Independent functional acceptance](../docs/quality/evidence/release-paired20-21-functional-acceptance-performance-blocked-v1.json)
confirms the pair, but strict master section 53 remains blocked by unexplained execution
latency. **0/2 accepted convergence** is separate from two functionally complete rounds.

| Current measurement | Retained result and scope |
| --- | --- |
| Execution median, round20 / 21 | 63.133754 / 70.923486 s; all six samples pass 26 semantic and four stability checks |
| Baseline execution capture medians | 55.642860 / 55.870139 / 95.099944 s; all nine samples retained; pooled median 55.870139 s |
| Candidate quality means | Index/context recall 0.870370 each, versus baseline 0.722222 / 0.851852; exact 30 raw REVIEW case/metric losses remain, zero hard-invariant failures |
| Graph / index / total store / Python peak ratios | Approximately 1.458 / 2.413 / 2.027 / 1.592 times baseline; Python allocation is not native RSS |
| Parsing / lookup structure | Unchanged parse count 0; one changed file count 1; four memory lookups in both rounds |
| UI pause/resume median / p95,20 | Candidate 520.45 / 588.5 ms; baseline 1206.25 / 1445.4 ms; six durable transitions each |
| UI pause/resume median / p95,21 | Candidate 618.4 / 740.2 ms; baseline 1098.6 / 1433.4 ms; six durable transitions each |
| One CPU / 256 MiB peak commit,20 | Candidate 49,451,008 B / 15.752778 s; baseline 46,669,824 B / 19.437569 s |
| One CPU / 256 MiB peak commit,21 | Candidate 49,590,272 B / 15.106173 s; baseline 46,116,864 B / 19.517927 s |

Both memory rounds preserve exact answers, response caps and history witnesses; 45
case observations each. Progressive complete answers return roughly 8.0-8.1 KB versus
11.0-11.5 KB rediscovery, but take longer in these captures. Direct reuse avoids graph
refresh and has narrower semantics, so it is not a complete-answer speed comparison.
Higher candidate commit/allocation and retained ranking misses remain costs, not hidden
behind mean recall or UI improvements. No paid-model, native platform, worker RSS or
otherwise-quiet-host claim follows.

The initial source24 history capture retains exact 1,001-row / 33-page coverage and
successful concurrent allocation: median 301.634 ms / CPU265.625 ms versus dated
194.8125 ms / CPU187.5 ms, with native observer overhead 0.1144%. Historical sourceb2aa
662.6858 / 334.3029 ms and the invalid profiler's 6.735x wall / 6.6x CPU overhead stay
visible in preceding sections. Excessive profiling does not establish causal timing.

The finite matched-package v3 stopped after R1 on unknown no-file module attestation;
its 168.4051 ms timing is invalid, C1/C2/R2 UNRUN. The single import-only diagnostic
identified exactly two generated pyexpat aliases; v4 adds their explicit binary mapping,
without relaxing other origin checks or reusing failed timings. All four fresh v4
captures passed functional/provenance/observer/owned-cleanup checks. Raw status stays
**MIXED_OR_INDETERMINATE**: R1/C1/C2/R2 wall medians 173.917 / 200.227 / 244.206 /
273.122 ms, CPU171.875 / 187.5 / 234.375 / 265.625 ms. C2 tails above R2 are retained.
The [history code-path addendum](../docs/quality/evidence/release-history-page-path-acceptance-addendum-v1.json)
accounts for the candidate-specific source concern: page algorithm unchanged and all
12 traversals had zero writes, excluding the only changed atomic writer. This is not
latency equivalence, historical host attribution or automatic master53 credit.

The predeclared execution attribution pair v3 stopped on immutable-baseline WinError5
replacing execution/state.yaml. Candidate UNRUN, no completed timing/native delta;
owned launcher/native exit and handle cleanup confirmed. Post-exit target metadata
is regular and not READONLY, temporary absent; this cannot prove attributes at failure
or identify a holder. Baseline is not retried.

A separate single [candidate operations diagnostic](../docs/quality/evidence/release-execution-candidate-operations-result-v3.json)
completed unchanged workload/26+4 checks with stable bindings. It measured **51.286747 s**,
26 first lease acquisitions totaling **83.4896 ms** (all-lease union83.4942 ms), 2,120
atomic operations / 2,122 replacement calls, two known Windows denials and **40 ms
inferred scheduled backoff**. Native replacement interval union was955.7452 ms.
Hook bookkeeping fraction0.07051% and native query fraction0.000723% pass the direct
screen; this is not a full perturbation proof. Inclusive lease/native intervals overlap
and must not be added as causal attribution. The measured added lease and backoff costs
are too small to explain earlier candidate medians. A present faster sample does not
replace earlier observations or explain their host causes; acceptance remains open.

One read-only replay of the retained final trace completed in3.0646ms for174 events
and41 nodes, with unchanged inputs. The preceding decoder failure made zero trace
calls; its corrected successor validates schema_version1 and removes only that stored
envelope field, matching production. Import/decoding time is excluded. This is one
current function call, not a historical duration, early-snapshot measurement or general
latency bound. It does not account for the old whole-execution gap. Repeated atomic
targets are not identical-byte proof: structured projections include each new generation.
No recovery-write skip has been applied from these observations.

The prior source4f408 removes three redundant operations: duplicate checked state
serialization, eager lock-gate allocation on a registry hit, and repeated diagnostic
lowercasing. Exact old/new output for42 documents/125,526 bytes and141 focused tests
pass. Fresh source-bound round22 stopped after its first execution sample passed26+4
checks in70.8595s and its second failed with WinError5 replacing an actor `session.yaml`.
The report is incomplete: no new median. Browser14/advisories/paired quality completed;
memory/UI/constrained/fullPython and all of round23 are UNRUN. Guards stayed stable.
Automatic cleanup removed the failed fixture, so failure-time attributes and holders
are unavailable. The one bounded retained-fixture diagnostic passed26+4 and all guards,
observed2,124 replacements/two transient denials/zero terminal denials, and confirmed
owned process exit/handle cleanup. It receives no timing credit and identifies no
original holder or cause. No repeat diagnostic is planned without a justified change.
Prior source24 results above remain historical and do not establish a speedup.

The active sourceb897 candidate combines shared snapshot reads and one native atomic
rename with a pre-mutation thread-owner guard. Focused124, static13 and immutable86
pass, as do current installed packages, heldout263 and history1001. Round24 timed
stages and full924-case suite completed (922 PASS /2 explicit SKIP /0 FAIL/ERROR).
Round25 browser/audits/quality/execution correctness/memory completed; it was interrupted
at the user's request during baseline UI. Current UI, constrained and fullPython25 are UNRUN.
Execution samples are 60.704 / 84.352 / 89.061 seconds, median84.352 versus the pooled
nine-sample baseline55.870 seconds. The [independent provisional review](../docs/quality/evidence/release-round24-provisional-acceptance-performance-blocked-v1.json)
keeps Master53 performance acceptance blocked. Host activity is context, not a proven
cause or a waiver. Canonical `scripts/benchmark_memory.py` now observes native
filesystem opens as well as Path.open. Exact calibration verifies no double counting;
CountedReader/workflow/gold/budget definitions are unchanged. The exact original script
is archived under `.tools/research/release-shared-io-before-v1/scripts/benchmark_memory.py`.
Old narrower metadata/memory read totals cannot be compared with the new method as
identical coverage. Source2489 static11/current86 results remain historical. No holder,
convergence or speedup claim follows from these focused fixes.

[Status](../docs/quality/ENHANCEMENT_STATUS.md) owns final dispositions;
[the worklist](../docs/quality/NEXT_SESSION.md) owns next steps. Methods above and raw
JSON remain the authorities for metric definitions and complete sample/tail details.

Qualification resumed on Oct7 with predeclared fresh28/29 captures. The user confirmed concurrent work;
round25 execution median140.620s remains unaccepted. The raw controller nonzero exit is
classified by the [pause verification](../docs/quality/evidence/release-user-pause-guard-verification-v1.json)
as an administrative interruption. Preserve all partial captures and original references;
resume with fresh predeclared names and reviewed successor admission, never overwrite25.
Round26 stopped on a frontend advisory before benchmarks. A single dev dependency
patch clears the audit and reproduces the tested frontend bytes; fresh28/29 use the
new393 input freeze. No diagnostic or final prose repack has run. [Worklist](../docs/quality/NEXT_SESSION.md).
