# Runtime, orchestration, isolation, and Change Guardian research

This combined guide preserves dated runtime research and the iteration-1 independent audit. For current acceptance and
release status, use the [enhancement status](../ENHANCEMENT_STATUS.md).

Inspected 2026-09-26. Baseline: `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / immutable `v2.0.0`. Research covers master-plan sections 4–7, 21–28, 33 and 60–61. This is an independent source/documentation audit, not a comparative execution benchmark of every upstream system. Local probes described below ran against the current development checkout before fixes. No upstream source was copied. Canonical authority: `SIGNOFF.md`, `docs/SOURCE_OF_TRUTH.md`, `docs/06-security-git-and-governance.md`. Root `AGENTS.md` was absent.

## Upstream refresh - 2026-10-03

[Current refresh disposition](../evidence/release-upstream-refresh-20261003-independent-disposition-v1.json)
rechecks all40 linked references across the three guides. Historical Daytona is now
archived and still states that its core is unmaintained; its remote adapter remains
DEFER. The bounded metadata/README review identifies no new confirmed accepted P0/P1
gap and preserves the existing owned lifecycle/cancellation boundaries. All23 accepted
implementations remain pending evaluation and13 DEFER decisions remain. Changed
upstream code, deployed runtimes and nested license payloads were not comprehensively
audited; the inspections below retain their original dates and pins.

## Evidence quality and limitations

Read Orqalis scheduler, orchestrator/task transitions, execution driver, recovery, workspace binding, worker/tool service, command runner, filesystem scope, review/digest, Guardian, Git delivery and filesystem transaction journal. Inspected existing tests for execution, recovery, runtime, Guardian, security and sandboxing. Upstream inspection combines primary documentation, pinned implementation entry points and public GitHub metadata. GitHub unauthenticated API later returned 403; public raw files and `git ls-remote` remained usable. Maintenance is assessed from both activity and explicit project statements, not stars. No paid model benchmark, hosted sandbox benchmark, real Docker hard-kill experiment, POSIX containment experiment, or whole-upstream test suite ran in this stream. Claims of relative speed/success remain hypotheses until measured. No critical vulnerability is asserted; three high-priority correctness/security candidates are described precisely below.

## Revision, maintenance, portability and license register

Repository links identify inspected revisions, not floating claims of currency. Metadata queried 2026-09-26; commit dates below are upstream committer dates unless stated otherwise.

| Reference | Inspected revision and maintenance | License scope / reuse decision |
|---|---|---|
| [LangGraph](https://github.com/langchain-ai/langgraph/tree/7daa3ab49d678a5da75edb08baa87db4a2be52c3) | `7daa3ab49d678a5da75edb08baa87db4a2be52c3`, 2026-09-23; unarchived, recent activity | MIT metadata; concept-only adaptation. Preserve license notices if source is later reused. |
| [Microsoft Agent Framework](https://github.com/microsoft/agent-framework/tree/6f1522a50b66f117da34cc25ea299ba24a528b15) | `6f1522a50b66f117da34cc25ea299ba24a528b15`, 2026-09-25; active forward-looking Microsoft reference | MIT metadata; concept-only. No Azure or framework dependency proposed. |
| [CrewAI](https://github.com/crewAIInc/crewAI/tree/4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec) | `4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec`, 2026-09-25; active | MIT metadata; concept-only. Flow persistence adapter is separable from its database implementation. |
| [Temporal](https://github.com/temporalio/temporal/tree/d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d) | `d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d`, 2026-09-25; active | MIT metadata for server repository; semantics only, no Temporal service requirement. |
| [OpenHands application](https://github.com/OpenHands/OpenHands/tree/47a10808d78561546a02555d0d2c7fa96fa96300) | `47a10808d78561546a02555d0d2c7fa96fa96300`, 2026-09-26; active | Root MIT text inspected; component exceptions must still be checked before reuse. |
| [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk/tree/d77ada7a030b3acaa82593d402632680361dfe42) | `d77ada7a030b3acaa82593d402632680361dfe42`, HEAD observed 2026-09-26; current docs explicitly distinguish SDK from product and exclude legacy V0 | [MIT text](https://github.com/OpenHands/software-agent-sdk/blob/d77ada7a030b3acaa82593d402632680361dfe42/LICENSE) inspected. Concepts only. |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5) | `3ea751c087f32b16e039a2233dd6eefecef325d5`, 2026-07-16; unarchived, pushed 2026-09-21 | MIT metadata; inspect SWE-ReX separately before adopting runtime code. |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent/tree/04d809ceab9df28f9adaed044884180159172930) | `04d809ceab9df28f9adaed044884180159172930`, HEAD observed 2026-09-26; README documents v2 and current benchmark tooling | [MIT](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/LICENSE.md). Narrow inspected scope: README/license, not implementation-quality certification. |
| [Daytona historical core](https://github.com/daytonaio/daytona/tree/ec4c21b2d597091ac09ecc278f3bcc172575a987) | `ec4c21b2d597091ac09ecc278f3bcc172575a987`, 2026-06-25. **README explicitly says core moved private in June 2026; public core will receive no further updates/fixes/releases.** `archived=false` is misleading as a maintenance signal. | Current root has no LICENSE. README points to [v0.190.0 AGPL-3.0](https://github.com/daytonaio/daytona/blob/v0.190.0/LICENSE), tag `1bd2f45e4e1d1e332bc9b6064bccbce021d4debd`. Historical concepts only; do not vendor. |
| [Daytona clients](https://github.com/daytona/clients/tree/429a608f226cc29204cc2213ca05167531f26722) | `429a608f226cc29204cc2213ca05167531f26722`, HEAD observed 2026-09-26; current client successor | README distinguishes CLI AGPL-3.0 from SDK/API/examples Apache-2.0. Do not infer server license from clients. |
| [E2B](https://github.com/e2b-dev/E2B/tree/ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b) | `ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b`, 2026-09-18; active | Apache-2.0 metadata. Optional adapter would need component/NOTICE audit; no hosted dependency accepted. |
| [AutoGen](https://github.com/microsoft/autogen/tree/027ecf0a379bcc1d09956d46d12d44a3ad9cee14) | `027ecf0a379bcc1d09956d46d12d44a3ad9cee14`, 2026-04-06. README explicitly maintenance-only/community managed; use historical event ideas | Root LICENSE is CC-BY-4.0 **documentation**, [LICENSE-CODE](https://github.com/microsoft/autogen/blob/027ecf0a379bcc1d09956d46d12d44a3ad9cee14/LICENSE-CODE) is MIT. Both texts inspected. |
| [Semgrep](https://github.com/semgrep/semgrep/tree/56e04ee9581f76a2a1cfcdd806dd2d276851a39f) | `56e04ee9581f76a2a1cfcdd806dd2d276851a39f`, 2026-09-23; active | LGPL-2.1 root text inspected. [Community rules use a separate Semgrep Rules License](https://github.com/semgrep/semgrep-rules/blob/develop/LICENSE); public rules are not automatically MIT. No rules/code copied. |
| [Gitleaks](https://github.com/gitleaks/gitleaks/tree/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b) | `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b`, HEAD observed 2026-09-26; README/config contract inspected, release cadence not independently assessed | MIT text inspected on fetched default branch; pin license/config again before packaging. Optional subprocess integration, not vendoring, is preferred. |

License entries are engineering due diligence, not a declaration that every nested component or trademark can be reused.

## Capability findings

### RT-01 — Local checkpoint authority and atomic commits — KEEP

- **PROJECT:** LangGraph, Microsoft Agent Framework, CrewAI.
- **SUBSYSTEM / FEATURE:** Durable execution / explicit checkpoint boundaries.
- **HOW IT WORKS:** LangGraph separates graph checkpoint state from long-term stores; its Pregel loop sequences checkpoint writes. Agent Framework supports local file checkpoints and restores executor state. CrewAI exposes a `FlowPersistence` interface around state saves.
- **WHY EFFECTIVE:** Clear recovery boundaries and pluggable storage avoid conflating conversations, memory and execution state.
- **ORQALIS CURRENT STATE:** Task Capsule snapshot, append-only events, transaction marker replay, generation CAS, per-run controller lease and strict JSON already implement the necessary local semantics.
- **GAP:** No replacement framework is justified; fault coverage, not architecture, needs expansion.
- **ADAPTATION IDEA / EXPECTED BENEFIT:** Keep filesystem authority; add crash-boundary tests under RT-03.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Low test cost; references MIT. Copying framework serializers or database adapters would increase dependency/security burden.
- **RECOMMENDATION:** KEEP; reject importing pickle checkpoint formats.
- **EVIDENCE:** `persistence/filesystem/task_store.py:_recover,_commit_capsule,try_run_lock`, `io.py:atomic_write_bytes`; [LangGraph loop](https://github.com/langchain-ai/langgraph/blob/7daa3ab49d678a5da75edb08baa87db4a2be52c3/libs/langgraph/langgraph/pregel/_loop.py), [MAF checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints), [CrewAI persistence interface](https://github.com/crewAIInc/crewAI/blob/4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec/lib/crewai/src/crewai/flow/persistence/base.py).

### RT-02 — Side-effect uncertainty is explicit — KEEP

- **PROJECT:** Temporal, LangGraph.
- **SUBSYSTEM / FEATURE:** Activity idempotency / safe retry.
- **HOW IT WORKS:** Temporal distinguishes deterministic workflow progress from retriable activities and recommends idempotent activities; durable results avoid repeating completed steps.
- **WHY EFFECTIVE:** A timeout does not prove an external effect never occurred.
- **ORQALIS CURRENT STATE:** Tool request hash plus stable invocation ID; persisted completed observation is reused; uncertain tool result blocks replay. Recovery requires an explicit uncertainty acknowledgement and bounded new attempt. Git commit objects and branch compare-and-swap support reconciliation.
- **GAP:** Sandbox process ownership is missing despite effect receipts (RT-04).
- **ADAPTATION IDEA / EXPECTED BENEFIT:** Preserve conservative uncertain-outcome behavior; reconcile owned sandbox before recovery.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Keep cost low; MIT concepts. Blind retries or an exactly-once claim would be unsafe.
- **RECOMMENDATION:** KEEP.
- **EVIDENCE:** `execution/tools.py:execute`, `core/recovery.py:retry`, `git/delivery.py:attach`; [Temporal activity idempotency](https://docs.temporal.io/activity-definition), `tests/integration/test_executor.py` commit/attach crash cases, `test_providers.py` interrupted invocation cases.

### RT-03 — Real process-death fault matrix — ADD, P1

- **PROJECT:** Temporal, LangGraph, Microsoft Agent Framework.
- **SUBSYSTEM / FEATURE:** Durable execution / restart evaluation.
- **HOW IT WORKS:** Compare authoritative persisted results after process failure at each effect/checkpoint boundary.
- **WHY EFFECTIVE:** Exceptions running Python cleanup do not simulate termination without `finally`.
- **ORQALIS CURRENT STATE:** Useful injected-exception tests exist for worker result, provider finish, commit creation/attachment and memory staging; storage journals are tested separately.
- **GAP:** No complete hard-process-termination matrix across planning, command execution, review, repair, docs and Git preparation was located.
- **ADAPTATION IDEA:** Child-process test harness with externally observed checkpoint barrier; kill only the owned child, restart from a temporary repo; fake provider and Docker transport keep mandatory suite offline.
- **EXPECTED BENEFIT:** Evidence that no side effect is duplicated and no mutable orphan survives unnoticed.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Medium; MIT concepts, native test implementation. Windows/POSIX process semantics and flaky timing require deterministic barriers.
- **RECOMMENDATION:** ADD.
- **EVIDENCE:** `tests/integration/test_executor.py`, `test_recovery.py`, `test_sandbox.py`; [MAF checkpoint/HITL restoration](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop).

### RT-04 — Durable sandbox ownership and cleanup reconciliation — ADAPT, P1 / high reliability impact

- **PROJECT:** OpenHands SDK, SWE-agent/SWE-ReX, E2B; Daytona historical lifecycle concepts.
- **SUBSYSTEM / FEATURE:** Coding runtime / lifecycle ownership.
- **HOW IT WORKS:** Explicit workspace/deployment/sandbox IDs make connection, interruption, stop and cleanup distinct operations. E2B reconnects using sandbox ID; SWE-agent delegates interruption to its runtime deployment.
- **WHY EFFECTIVE:** Controller lifetime and execution-environment lifetime are different.
- **ORQALIS CURRENT STATE:** Docker is restricted, per-command and default; Windows Job/POSIX process-group cleanup protects local descendants. Docker name is random and only local to `CommandRunner.run`; `ToolInvocation` persists no sandbox identity. Cleanup is only in `finally`. `docker rm --force` uses `check=False` without checking return code.
- **GAP:** Controller hard death can leave daemon-owned container active after controller lease release. Restart cannot identify/reconcile it. A normal cleanup denial is silently ignored (probe below).
- **ADAPTATION IDEA:** Persist exact invocation ownership before launch; deterministic container name plus root/run/invocation labels; inspect exact identity and reconcile only that owned container before recovery/reuse. Unknown daemon status or ownership mismatch blocks recovery. Record cleanup disposition; absence is successful only after bounded verified inspect. Keep command execution policy and no-network defaults.
- **EXPECTED BENEFIT:** Prevent overlapping old/new writers and false cleanup success.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Medium; MIT/Apache concepts. Must cover validator commands as well as ToolService; never remove containers by name prefix alone. Docker job cleanup is not daemon-container cleanup.
- **RECOMMENDATION:** ADAPT.
- **EVIDENCE:** `execution/commands.py:run`, `domain/execution.py:ToolInvocation`, `core/recovery.py:retry`, `execution/evaluator.py`; [OpenHands conversation](https://docs.openhands.dev/sdk/arch/conversation), [SWE-agent environment](https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/sweagent/environment/swe_env.py), [E2B sandbox ID/lifecycle reference](https://e2b.dev/docs/sdk-reference/python-sdk/v2.5.0/sandbox_sync).

### RT-05 — Typed action/observation events — KEEP

- **PROJECT:** OpenHands SDK, AutoGen historical core.
- **SUBSYSTEM / FEATURE:** Runtime event stream / controller boundary.
- **HOW IT WORKS:** Typed actions and observations link tool results to requests; immutable event storage offers observer integration. OpenHands EventLog uses file locking and a disk index.
- **WHY EFFECTIVE:** Tool output does not itself become authoritative workflow state.
- **ORQALIS CURRENT STATE:** Typed ProviderToolCall, ToolObservation, ToolInvocation and Event contracts; role checks and persisted request match precede dispatch; events correlate actor/task/attempt.
- **GAP:** No need for a second conversation/event authority. Sandbox lifecycle fields can enrich existing records.
- **ADAPTATION IDEA / EXPECTED BENEFIT:** Keep existing contracts and add RT-04 lifecycle observations through them.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Low; MIT code concepts, AutoGen docs CC-BY-4.0. Persisting raw conversation/thought events would violate privacy invariants.
- **RECOMMENDATION:** KEEP.
- **EVIDENCE:** `execution/tools.py`, `domain/events.py`; [OpenHands event architecture](https://docs.openhands.dev/sdk/arch/events), [pinned EventLog](https://github.com/OpenHands/software-agent-sdk/blob/d77ada7a030b3acaa82593d402632680361dfe42/openhands-sdk/openhands/sdk/conversation/event_store.py).

### RT-06 — Deterministic fan-out/fan-in and approvals — KEEP

- **PROJECT:** Microsoft Agent Framework, LangGraph, CrewAI.
- **SUBSYSTEM / FEATURE:** Agent coordination / typed orchestration and human input.
- **HOW IT WORKS:** MAF graph executors route typed messages with a superstep barrier; pending HITL requests survive checkpoints. CrewAI listeners encode explicit dependencies.
- **WHY EFFECTIVE:** Routing and resume points remain inspectable.
- **ORQALIS CURRENT STATE:** Validated DAG, current-goal/version gates, read-worker waves, one writer, persisted fingerprinted approvals and bounded repair; workers cannot own global transitions.
- **GAP:** Fixed role driver is less general than arbitrary graph executors, but no measured workload requires importing their framework.
- **ADAPTATION IDEA / EXPECTED BENEFIT:** Keep authority and approval fingerprints; benchmark skewed read branches before changing wave barriers.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Low keep cost; MIT. Removing barriers without explicit shared-state rules invites races.
- **RECOMMENDATION:** KEEP.
- **EVIDENCE:** `core/executor.py:_context_wave`, `core/scheduler.py`, `core/task_runtime.py`, `core/approvals.py`; [MAF supersteps](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows), [CrewAI Flows](https://docs.crewai.com/en/concepts/flows).

### RT-07 — Worker mailboxes and independent parallel writer worktrees — DEFER, P2

- **PROJECT:** Microsoft Agent Framework, AutoGen, OpenHands.
- **SUBSYSTEM / FEATURE:** Agent coordination / handoffs and workstream isolation.
- **HOW IT WORKS:** Typed messages route between stable agent identities; isolated workspaces separate concurrent mutations before integration.
- **WHY EFFECTIVE:** Reduces conflicting writes and permits dependency-local parallelism.
- **ORQALIS CURRENT STATE:** One run worktree, one writer invariant, bounded parallel read workers, typed worker returns and context packs. No arbitrary agent chat.
- **GAP:** Workstream parallelism and explicit inter-worker mailbox are absent; task results are not a general message bus.
- **ADAPTATION IDEA:** Only after benchmark evidence: durable typed proposal mailbox owned by Orchestrator; optional task worktrees with content-hash integration gate and conflict queue.
- **EXPECTED BENEFIT:** Faster independent multi-file work without shared-write races.
- **IMPLEMENTATION COST / LICENSE / RISKS:** High; MIT concepts. Merge conflicts, disk/process overhead and stale context may outweigh parallel speedup.
- **RECOMMENDATION:** DEFER. Unconstrained agent-to-agent chat remains out of scope.
- **EVIDENCE:** `core/scheduler.py:WRITE_ROLES,dispatch_wave`, `execution/workspaces.py`, `workspace/manager.py`; [MAF handoff identity guidance](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff).

### RT-08 — Rich hosted sandbox adapters and snapshots — DEFER, P2

- **PROJECT:** E2B, OpenHands Docker/remote workspaces, Daytona clients.
- **SUBSYSTEM / FEATURE:** Isolation / optional capability tiers.
- **HOW IT WORKS:** API-owned environments expose start/stop/pause/reconnect, filesystem/process access and network policy separately.
- **WHY EFFECTIVE:** Long sessions may amortize setup and preserve process state.
- **ORQALIS CURRENT STATE:** Simple Docker command sandbox; explicit trusted-local fallback; exact approved argv, time/output/resource limits, scrubbed environment, no-network Docker default, read-only reviewer mount.
- **GAP:** No snapshot/fork/network allowlist interface or portable sandbox capability report.
- **ADAPTATION IDEA:** First define a small adapter protocol only if RT-04 needs it; keep Docker/local defaults, fail closed on unsupported requested isolation. Add remote providers only on demonstrated demand.
- **EXPECTED BENEFIT:** Extensibility without mandatory infrastructure.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Medium-high; E2B Apache-2.0, OpenHands MIT, Daytona clients mixed. Cloud cost, source exfiltration and server/license coupling need opt-in.
- **RECOMMENDATION:** DEFER.
- **EVIDENCE:** `execution/commands.py`, `domain/execution.py`; [OpenHands Docker workspace](https://docs.openhands.dev/sdk/guides/agent-server/docker-sandbox), [Daytona current sandbox/network API](https://www.daytona.io/docs/en/python-sdk/sync/sandbox/).

### RT-09 — Guardian test-integrity checks — ADAPT, P1

- **PROJECT:** Semgrep structural-rule patterns, Gitleaks diff/baseline concepts, Orqalis independent review.
- **SUBSYSTEM / FEATURE:** Change Guardian / protection against weakening tests.
- **HOW IT WORKS:** Structural rules distinguish syntax behavior from text markers; findings retain stable rule identity and source locations.
- **WHY EFFECTIVE:** Keeping a test declaration does not preserve its assertions or execution.
- **ORQALIS CURRENT STATE:** Guardian checks scope, generated paths, sensitive config, secret-like content, binary changes, deletion ratio and removed declaration strings.
- **GAP:** Removing the only assertion while retaining `def test_...` passes; new skip/xfail decorators also evade declaration removal. This weakens the canonical prohibition on disabling security tests.
- **ADAPTATION IDEA:** Conservative Python AST checks for removed assertion-bearing test body and added disabling decorators/calls; explicit finding, not a proof of semantic equivalence. Require an exact reviewed-change approval for intentional refactors; do not silently whitelist a test directory. Extend other languages only with fixtures and parser support.
- **EXPECTED BENEFIT:** Detect common acceptance-gaming and accidental test weakening before delivery.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Medium; native rules avoid Semgrep copyleft/rule-license imports. Assertion count is incomplete and can false-positive on helper extraction, parameterization and test renames.
- **RECOMMENDATION:** ADAPT.
- **EVIDENCE:** `delivery/guardian.py:_TEST_MARKERS,inspect`, `tests/unit/test_guardian.py`; [Semgrep rules/source license boundary](https://github.com/semgrep/semgrep-rules), reproducible probe below.

### RT-10 — Bounded Guardian file reads — ADAPT, P1 / availability

- **PROJECT:** Orqalis scoped-file/read limits; bounded-execution patterns in SWE-agent and OpenHands.
- **SUBSYSTEM / FEATURE:** Security review / resource bounds.
- **HOW IT WORKS:** Bound allocation before reading an untrusted changed artifact, then read at most limit+1 to detect growth.
- **WHY EFFECTIVE:** A sparse/huge changed file cannot exhaust reviewer memory before rejection.
- **ORQALIS CURRENT STATE:** Guardian executes `target.read_bytes()` before its 10 MB size check. ScopedFilesystem and workspace_digest already check size earlier.
- **GAP:** Guardian allocates unbounded bytes first; a command can create huge files in the writable mount despite container memory limits.
- **ADAPTATION IDEA:** Stat first, bounded stream read, reject nonregular/oversize changes; test that read_bytes is never called on an oversize fixture and that growth is bounded.
- **EXPECTED BENEFIT:** Review remains available on malformed/adversarial artifacts.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Low, Orqalis-native. Size checks alone have TOCTOU limits; bounded read is still required.
- **RECOMMENDATION:** ADAPT.
- **EVIDENCE:** `delivery/guardian.py:inspect` (read precedes len check), `execution/filesystem.py:read`, `execution/review.py:workspace_digest`. Source-confirmed ordering; no memory-exhaustion attack was run.

### RT-11 — Optional static/secret scanner evidence — DEFER, P2

- **PROJECT:** Semgrep, Gitleaks.
- **SUBSYSTEM / FEATURE:** Security / stable scanner findings.
- **HOW IT WORKS:** Configured scanners produce structured rule/path/range findings; Gitleaks supports redacted output and baseline fingerprints.
- **WHY EFFECTIVE:** Established rule catalogs catch more patterns than a small redaction regex.
- **ORQALIS CURRENT STATE:** Typed findings, deterministic Guardian and redaction exist; no scanner-result contract was found in this scope.
- **GAP:** Additional security coverage useful, but importing full rule catalogs adds licensing, updates and false-positive maintenance.
- **ADAPTATION IDEA:** Optional offline scanner subprocess adapter with pinned rules, policy-controlled executable, output size/time bounds, redaction before persistence, exact diff fingerprints and explicit waiver provenance. A scanner baseline must never waive a newly introduced secret.
- **EXPECTED BENEFIT:** Broader detection with auditable evidence.
- **IMPLEMENTATION COST / LICENSE / RISKS:** Medium. Gitleaks MIT; Semgrep LGPL-2.1, separate rules license. Avoid remote auto-config fetching and raw secret artifacts.
- **RECOMMENDATION:** DEFER until native P1 correctness fixes pass.
- **EVIDENCE:** `security/redaction.py`, `domain/artifact.py`; [Gitleaks pinned README](https://github.com/gitleaks/gitleaks/blob/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b/README.md).

### RT-12 — Replace core with an upstream orchestration service — REJECT

- **PROJECT:** Temporal server, LangGraph service, CrewAI platform; Daytona historical core.
- **SUBSYSTEM / FEATURE:** Architecture / framework transplantation.
- **HOW IT WORKS:** Adopt an external controller/persistence/runtime as the product execution authority.
- **WHY EFFECTIVE:** Such stacks can provide broad distributed infrastructure for their intended deployments.
- **ORQALIS CURRENT STATE:** Portable local filesystem authority and provider-neutral application services already match product needs.
- **GAP:** No evidence justifies duplicated workflow authority or mandatory service.
- **ADAPTATION IDEA / EXPECTED BENEFIT:** Extract narrow semantics instead; preserve clean clone/no database operation.
- **IMPLEMENTATION COST / LICENSE / RISKS:** High integration and migration burden; mixed licenses; historical Daytona core is unmaintained. Violates accepted local-first scope if mandatory.
- **RECOMMENDATION:** REJECT.
- **EVIDENCE:** `SIGNOFF.md` local-first amendment; `docs/SOURCE_OF_TRUTH.md`; revision/license register.

## Confirmed local audit probes and acceptance proposals

The following isolated Python probes used `.venv/Scripts/python.exe`, stdlib mocks and a temporary Git repository. They modified no project source or release history. The original failing behavior must become a regression assertion, not be recorded as a passed benchmark.

1. **RT-04 cleanup:** mocked successful Popen command, mocked `WindowsJob`, and `subprocess.run` returning `CompletedProcess(['docker','rm'], 1)`. Actual result: `{"probe":"cleanup_nonzero","cleanup_exit":1,"passed":true,"error_code":null}`. Confirms an ignored cleanup exit; it does not prove a real container was present. Required fixture: fake Docker state owned independently from controller process, persisted identity before launch, termination before finally, restart reconciliation. Acceptance: owned matching container removed once; missing container handled idempotently; mismatched labels/project untouched and blocked; daemon unreachable or failed removal yields a non-PASS observation and blocks retry until resolved; no orphan writable process when new attempt starts.
2. **RT-09 weakening:** temporary repo baseline `tests/test_security.py` contains `def test_authorization():` plus an assertion; edit keeps declaration and replaces body with `pass`. Guardian result: `{"probe":"test_assertion_removed","passed":true,"findings":[]}`. This is a diff-classification probe, not a security-test execution. Acceptance: fixture matrix includes removed assertions, skip/xfail, unchanged tests, added assertions, helper extraction, rename, multiline tests and legitimate reviewed refactor. Dangerous fixtures block; permitted reviewed change binds exact base/new content hashes; changing content invalidates permission.
3. **RT-10 bounds:** source shows size check after unbounded read. Acceptance: sparse file over limit rejected without reading its full body; growing file read bounded to limit+1; report remains auditable with unsafe/oversize finding; normal <=limit content behavior unchanged.

## Runtime benchmark design

Use deterministic fake provider traces and isolated fixture repos; collect baseline/current source revision, OS, Python/Git versions, case ID, repetition count, median/p95 and raw samples. Mandatory cases: linear DAG, diamond with skewed read workers, blocked dependency, writer conflict, duplicate tool request, changed-argument identity collision, interrupted provider/tool, replay after completed receipt, pending approval resume, budget exhaustion, bounded repair convergence, Guardian attack/benign pairs, cleanup success/failure/uncertainty. Crash tests must observe durable barriers, not guess delays. Metrics: duplicate external effects (must be 0), unsafe replay (0), unrelated cleanup (0), leaked owned containers (0 when verified infrastructure available), event continuity, restart success/block reason, time to cancellation, retained stdout size, startup/command latency and task success. Retain existing single-writer invariant as benchmark oracle.

Real Docker tier is separate and optional: run with an already-pulled explicit test image; test no network, read-only reviewer mount, resource limits, descendants, crash recovery and cleanup. If Docker is unavailable, mark those results NOT RUN, never PASS. Compare live providers only after deterministic reliability passes; record token/model/time/cost data without hidden reasoning. Two clean iterations require rerunning the same suite after accepted changes, not counting research as a benchmark iteration.

No Gitleaks code or rule was imported.


## Implementation follow-through (2026-09-26)

The bounded RT-03, RT-04, RT-09 and RT-10 adaptations were accepted and implemented after this audit. The capability findings above describe the pre-change checkout; this section records the resulting behavior and measured local evidence. No upstream code or new runtime service was adopted. These are scoped results, not final program convergence or two full benchmark iterations.

| Finding | Implemented behavior | Source and executable evidence |
|---|---|---|
| RT-03 | A real child controller is terminated at eight deterministic boundaries in one run: plan persistence, completed tool observation, completed agent result, review persistence, repair-plan persistence, documentation file effect, Git commit creation and branch attachment. Each restart checks the released controller lease, retained event prefix, contiguous event sequence and run state. Final assertions cover unique completed provider invocations, two intentional implementation writes (initial + repair), two tool receipts, two reviews, one documentation marker and exactly one Git commit. Corrupt snapshot input is rejected visibly. | `tests/integration/test_hard_crash_matrix.py`; `tests/support/crash_worker.py`. Eight real process kills, followed by completion and repeated idempotent finalize. |
| RT-04 | Application Docker commands persist a schema-validated invocation receipt outside the writable worktree before `docker create`; only `docker start --attach` executes it. Root/workspace/run/invocation labels and Docker daemon identity are verified before removing the exact full container ID. Cleanup must confirm absence. Missing infrastructure, changed daemon, mismatched ownership, corrupt receipts, failed removal or continued presence block success/recovery. Reconciliation runs under the existing controller lease before workspace reuse, explicit recovery and delivery. Tool, evaluator and delivery-validator paths supply the owner. Command observations expose the sandbox name as their source reference. | `execution/sandbox.py`; `execution/commands.py`; `execution/tools.py`; `execution/evaluator.py`; `execution/workspaces.py`; `core/executor.py`; `core/recovery.py`; `core/delivery.py`; `delivery/validation.py`; `tests/unit/test_sandbox_lifecycle.py`; `tests/integration/test_sandbox_recovery.py`. |
| RT-09 | Python test deletion, reduced assertion count (including raises/warns/fail assertion helpers), new/changed skip or expected-failure constructs (including assigned bare module-wide markers), and newly uninspectable syntax/AST complexity produce `test_reduction`. Repairing an uninspectable baseline into inspectable tests is permitted. A legitimate refactor may use optional `DeliveryPolicy.reviewed_test_changes`, binding path plus exact old Git blob and new working-file SHA-256 hashes. The nonempty policy participates in existing delivery approval fingerprints; the default empty field is omitted from serialization to preserve existing fingerprints. Changed content invalidates the exception; unrelated Guardian checks remain active. | `delivery/test_integrity.py`; `delivery/guardian.py`; `domain/delivery.py`; `core/delivery.py`; `tests/unit/test_guardian_integrity.py`. |
| RT-10 | Guardian and reviewer workspace digests check file size before opening contents and cap each read at the limit plus one byte, rejecting oversize or concurrently growing content. | `delivery/guardian.py`; `execution/review.py`; sparse-file regression in `tests/unit/test_guardian_integrity.py`. |

Observed targeted executions on Windows/Python 3.12 in this checkout:

- Runtime/Guardian/recovery/executor/supervised-delivery/sandbox regression selection: **31 passed, 1 skipped in 332.65 seconds**. The skipped case requires `ORQALIS_TEST_SANDBOX_IMAGE`; it is not live-Docker evidence.
- Final focused lifecycle, Guardian, execution-tools and cancellation selection: **27 passed in 23.36 seconds**. Includes real controller termination at receipt-prepared, container-created and container-started barriers using an external fake-daemon state file; the fake daemon persists independently of the terminated controller.
- Application-level fake-Docker recovery integration: **1 passed in 20.90 seconds**. Cleanup denial blocks the run and explicit retry; successful subsequent reconciliation removes only the owned container, retires the prior attempt and makes the task ready without another provider call.
- Guardian final syntax/complexity, module-marker and assertion-helper follow-up plus existing Guardian regressions: **26 passed in 26.98 seconds**. New invalid or excessively recursive ASTs require review; valid repair of an invalid/overcomplex baseline is permitted. The independent knowledge reviewer identified loss of raises/warns/fail assertions; forward-removal and benign-addition fixtures cover the correction. Ruff and mypy passed for this follow-up; the preceding 18-file runtime static selection also passed.
- Full phase hard-kill matrix: **1 passed in 123.01 seconds**. This is one chained scenario with eight barriers, not eight independent end-to-end scenarios. Documentation replacement is intentionally replay-safe: an unreceipted atomic write is repeated once, producing one final marker. No exactly-once claim is made for arbitrary external effects.

The initial failing matrix fixture incorrectly cited all historical evidence, including the earlier failed review, during repair verification. Orqalis correctly rejected that evidence; the fixture now cites the current validation evidence. This was a test-fixture correction, not a relaxed product check. Targeted tests above overlap and must not be summed as distinct benchmark repetitions.

Remaining limits: real Docker daemon behavior, image compatibility, container process descendants, POSIX process containment and adversarial remote daemon races were **NOT RUN**. Windows Job termination alone is not proof of daemon-owned container cleanup. Fake-daemon tests validate ownership and fail-closed control flow, not Docker implementation behavior. The two-stage create/start protocol means a daemon create accepted late after controller death cannot start user code; a late create after an absence check can still leave a stopped resource, and this race has not been exercised against a real daemon. Low-level `CommandRunner` calls without an application owner have verified normal cleanup but no durable restart ledger; all inspected application Docker call sites supply an owner. Host receipts are writable metadata, not trusted deletion authority: root/workspace/run/invocation, daemon identity and live labels must agree. An adversary already controlling the Docker daemon or forging all daemon labels remains outside this ownership defense.

Guardian remains a conservative Python syntax heuristic, not a proof that test semantics are preserved. It can flag helper extraction/refactoring and cannot detect every weakened expression or arbitrary test framework. The exact-hash reviewed exception supports intentional changes through the existing approval mechanism. The new detector does not execute repository code. Static type/lint checks and the full repository regression are tracked by the coordinating stream; these targeted outcomes do not substitute for that final run.

## Independent G02 implementation cross-review

The coordinating stream requested an independent read-only review of the JavaScript/TypeScript parser implementation after runtime work. This review inspected `graph/ecmascript.py`, `graph/parsing.py`, Python collector and assembly integration in `graph/engine.py`, grammar dependency metadata/licenses, and the parser/provenance/symbol-read tests. No graph source was changed by this reviewer.

Concrete pre-fix witnesses found and corrected by the owner:

- Escaped module `"./base\u002fsecret"` was incorrectly shortened to `"./base"`; string-named imports could persist quoted literal contents. The corrected parser omits unsupported escaped specifiers/string aliases and emits diagnostic metadata.
- JavaScript heritage had a different grammar shape from TypeScript, so `class C extends Base` lost its base. A named class expression exposed its internal name instead of its variable binding. Both syntax facts now pass the original fixtures.
- Nested declarations amplified a 20,009-byte, 1,000-level source into 7,164,304 bytes of cache JSON. After depth/name/count/visit budgets, the same fixture emits 13,859 bytes, 32 symbols, a maximum qualified name length of 223 and explicit `depth_limit`. One local extraction sample took 0.0034 seconds; this is not a performance distribution or a native-parser worst-case bound.
- Python byte offsets used broad Unicode `splitlines` semantics, so legal U+2028, U+0085 or vertical-tab characters inside a string shifted later source slices. Physical CR/LF handling now reproduces the exact function bytes.
- `class Base{} { const Base = replacement; class Child extends Base{} }` falsely inferred the global Base as the inheritance target. JavaScript/TypeScript calls, inheritance and implementation relations now remain syntax occurrences with unresolved references; no unsupported lexical/type resolution is claimed.

Just-over-limit fixtures separately confirmed 5,000 calls, 2,000 symbols, 1,000 imports and 5,000 bindings, each with the corresponding visible diagnostic. Input sizes were at most 58,918 bytes. Final independent parser/provenance/symbol-read/project-graph selection: **59 passed in 29.73 seconds**. No remaining P0/P1 was established in this bounded audit. Native-parser pathological runtime, other operating-system wheel execution and compiler-level semantic equivalence were not tested. The installed Windows distributions totalled 3,564,038 bytes and contained MIT license texts for tree-sitter 0.26.0, tree-sitter-javascript 0.25.0 and tree-sitter-typescript 0.23.2.

## E01/E04 deterministic execution harness

Added a separate [`scripts/benchmark_execution.py`](../../../scripts/benchmark_execution.py), leaving the frozen retrieval/contract benchmark script unchanged. The runner copies the same three helper files (`tests/__init__.py`, `tests/support/filesystem.py`, `tests/support/trace_fixture.py`) into a disposable bundle and uses a fresh `python -I` child per repetition. It validates every loaded Orqalis/helper module against its selected source root, fingerprints source/resources/manifests, helper bytes, script, deterministic repository contents and environment, and verifies input stability after execution. The report retains failed measurements and checks persisted reload, event continuity/cursor, original-worktree isolation and final source contents. It does not export raw provider output.

The fixed case deliberately fails initial acceptance, runs one repair, and stops at a persisted passing review (`REVIEWING`); it does not include documentation, delivery commit, push or live-model quality. Raw outcomes include first-pass acceptance, repair iteration, model/tool counts and statuses, parallelism, invocation IDs, persisted capsule/event hashes and measured execution/process durations. Active/waiting values come from the existing event projection and are not CPU-time measurements. Missing fake-provider token and cost reports remain null. Smoke mode explicitly marks timings unqualified; measured captures require the coordinating stream's quiet-environment signal.

Both compatibility smokes passed with identical script/helper/fixture/environment hashes and distinct intended source hashes: [immutable baseline smoke](../evidence/baseline-execution-smoke.json) and [current source smoke](../evidence/current-execution-smoke.json). Each recorded nine successful provider invocations, two successful writes, one repair, two overlapping read tasks, FAIL then PASS reviews, final acceptance PASS and 174 contiguous events. Source-isolation audits covered 144 baseline modules and 154 current modules. These are repeated executions of one deterministic scenario, not independent engineering tasks or benchmark timing claims.

Harness integrity verification: **12 tests passed in 1.07 seconds**; Ruff formatting/checks and strict mypy passed for the new script/tests. Tests include poisoned-PYTHONPATH isolation, mixed-source import rejection, resource/hash changes, frozen helper independence, rejection of invalid persisted outcomes and retention of a failed child result. No production source or existing fixture helper was edited for this harness. Qualified comparative timing captures remain pending.

---

## Runtime independent audit, iteration 1

Observed 2026-09-26. This is a bounded **preflight audit with corrections**, not a clean qualification iteration or a claim of global convergence. The immutable release baseline remains `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / `v2.0.0`. Scope: an independent review of the memory workflow benchmark, a fresh upstream maintenance/HEAD check, and reassessment of the runtime recommendations in [the original research](RUNTIME_RESEARCH.md). The initial memory/maintenance slice did not change production code; its authorized corrections are in [the standalone memory benchmark](../../../scripts/benchmark_memory.py) and [its calibration tests](../../../tests/unit/test_memory_benchmark.py).

### Memory evidence audit and correction

The original two calibration tests passed, but direct adversarial probes established three evidence defects. These are benchmark correctness findings, not newly established product memory defects.

| Finding | Reproducible pre-fix behavior | Correction and acceptance witness |
|---|---|---|
| P1: arbitrary substring can satisfy a complete-answer gate | Put the active 72-hour fact and obsolete 24-hour fact in one payload, and the expected code snippet under an unrelated file/body field. `finish(require_source=True)` reports `exact_answer_pass=True` and witness recall 1. Neither active identity nor source provenance is required. | Credit witnesses only through declared response stages. Full memory bodies must equal the frozen canonical active record; pages must match the requested record ID, offset, exact canonical slice, next offset, source provenance, freshness and lifecycle. Source file reads must match the complete fixed path/content inventory; symbol discovery/body must match the independently derived Python symbol ID, name, file, line/byte bounds and full source SHA-256. Symbol body bytes and digest must agree. Wrong identity/hash/span and unchanged gold text no longer pass. |
| P1: obsolete material can coexist with a PASS | There is no rejection of the predecessor record or obsolete fact in active task responses. A valid gold substring hides the contradiction. | All active responses reject obsolete fact text and predecessor IDs. The sole exception is the exact validated successor record's `supersedes` provenance field. This permits the legitimate historical link without returning predecessor guidance as active context. Explicit historical retrieval remains a separate operation outside active task context and outside measured workflows. |
| Evidence instrumentation: valid binary read can raise | Reading the first four bytes of UTF-8 `caf?` raises `UnicodeDecodeError` inside the counter, although the underlying binary read is valid. | Return the original bytes unchanged and decode incrementally only for character counts. Report undecodable and pending bytes separately. Cover byte-split reads, zero-length reads, invalid bytes, `readinto`, `readinto1`, non-byte buffers and seeks. Raw binary byte counts and text re-encoded UTF-8 counts are not physical disk I/O. |
| Timing scope: unrequired witness extends completion | A memory-only workflow sees its durable fact, then an unrequired source snippet; `all_required_witnesses_ms` becomes the later source time. | Compute completion from the declared required witness set. A controlled-clock test proves later source evidence cannot change the memory-only completion time. Witness time now includes verification, rather than treating an unverified payload string as a completed answer. |

Each credited stage retains the serialized response SHA-256 and typed verified evidence. A memory page reports both the oracle's full canonical content hash and the returned slice hash; it does **not** pretend that the API returned a full-record hash or body. The fixture report retains expected active content hashes and source symbol identity/hash/span. The private canonical oracle bodies are excluded from the report payload. Active context records are verified against the known active fixture set even though the context-record contract itself exposes freshness rather than lifecycle. Full-memory inventory must be complete and duplicate-free; memory/source gold recall also gates completed workflows.

`benchmarks/memory_workflows.json` facts, query labels, source files, budgets and page limit were preserved. Fixed page limits, rather than a gold-text stopping condition, still control progressive reads. A source AST supplies an independent span oracle over the fixed Python input; the benchmark does not execute fixture source.

Validation: **27 calibration tests passed in 1.56 seconds**, with Ruff format/check and strict mypy clean. The [corrected snapshot smoke](../evidence/current-memory-smoke-audit-1.json) passed all **3 cases / 9 workflows**, all serialized caps, all explicit history checks and every required memory/source witness; direct reuse made zero graph refresh calls. Timings were disabled. Script SHA-256: `13494c75a1f0480dffb11211580d93218fc1934f9b3dcbace518df7f6f01339a`; unchanged dataset SHA-256: `eede4e76fb4a0b6b3949cef8de6e969dce41f9ed583669de2bc9bd41ddfd7d27`; snapshot source SHA-256: `d61354eb1786571741402d0e10838f25ef1728c0c24c5ed93582c6394b46d9a8`.

The first corrected smoke exposed an oracle-label mismatch (`Python` is the SDK language label), corrected without weakening identity checks. A subsequent full workflow run rejected its report because shared production source changed. That rejection is required behavior: no mixed-source measurement was retained. The passing smoke used a fingerprint-verified source copy under `.tools/research`; it is not a final-source qualification or speed measurement. Observed memory-file bytes were higher for progressive navigation than full rediscovery in these fixtures (for example, webhook retention: 21,086 versus 13,754 bytes), while source-file bytes were lower (168 versus 791). Those observed counters support narrower response/source selection, not a universal I/O improvement.

#### Fairness and metric limits

This harness compares **three current-version workflows**, not the immutable release against the current release. Both complete-witness workflows start fresh SDK instances over the same initialized repository and warm derived graph. The less selective workflow requests bounded context, every fixture source file and all active records. The progressive workflow uses a fixed discovery query, an overview reference, three bounded detail pages and an explicit symbol read. Repetitions alternate those two workflows; direct-ID reuse always follows and has the narrower memory-only target. It receives a stable ID learned from the earlier overview. It is not an autonomous discovery experiment.

The three illustrative cases deliberately place lasting decisions in approved memory, with a reachable detail reference and useful source symbol. They cannot establish broad engineering task success, model answer quality, token savings, general retrieval recall, repository-scale speed or hosted cost. The legacy field `exact_answer_pass` means that the declared fixed retrieval witnesses were verified; no generated answer is scored. Token, provider cost and live task-success fields remain null. Instrumentation observes Python `Path.open`/read results; it excludes Git/subprocess/kernel I/O. Memory discovery can still scan every canonical record, and provenance checks can read source files. Smaller responses do not establish less memory-file I/O. Timings include the probe and verification work, and any qualified captures require the coordinating stream's quiet-environment signal.

### Fresh upstream maintenance and revision check

All 14 references were independently re-observed between **2026-09-26 16:12:59 and 16:13:07 UTC**, using public `git ls-remote --symref`, unauthenticated GitHub repository metadata and pinned README bytes. All default HEADs match the initial research, and all repositories report `archived=false` and `disabled=false`. Those booleans are not maintenance guarantees. Unlike an earlier API-limited pass, repository metadata succeeded for every reference in this refresh.

The table's times are repository API `pushed_at`, **not HEAD commit dates, release dates or support guarantees**. Full metadata observations, pinned README URLs and SHA-256 values are retained in [the upstream evidence register](../evidence/runtime-upstreams-audit-1.json). License scope below carries forward the original pinned-file inspection where HEAD is unchanged; this iteration reread README maintenance/license statements and metadata, not every nested license file.

| Reference | Exact observed HEAD | Repository pushed at (UTC) | License scope retained |
|---|---|---|---|
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph/tree/7daa3ab49d678a5da75edb08baa87db4a2be52c3) | `7daa3ab49d678a5da75edb08baa87db4a2be52c3` | 2026-09-26T04:38:30Z | MIT |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework/tree/6f1522a50b66f117da34cc25ea299ba24a528b15) | `6f1522a50b66f117da34cc25ea299ba24a528b15` | 2026-09-25T19:09:24Z | MIT |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI/tree/4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec) | `4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec` | 2026-09-26T06:24:42Z | MIT |
| [temporalio/temporal](https://github.com/temporalio/temporal/tree/d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d) | `d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d` | 2026-09-26T12:22:25Z | MIT |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands/tree/47a10808d78561546a02555d0d2c7fa96fa96300) | `47a10808d78561546a02555d0d2c7fa96fa96300` | 2026-09-26T15:32:57Z | MIT root; check component exceptions |
| [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk/tree/d77ada7a030b3acaa82593d402632680361dfe42) | `d77ada7a030b3acaa82593d402632680361dfe42` | 2026-09-26T15:30:55Z | MIT |
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5) | `3ea751c087f32b16e039a2233dd6eefecef325d5` | 2026-09-21T22:02:50Z | MIT; runtime dependency separately scoped |
| [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent/tree/04d809ceab9df28f9adaed044884180159172930) | `04d809ceab9df28f9adaed044884180159172930` | 2026-09-21T22:02:14Z | MIT |
| [daytonaio/daytona](https://github.com/daytonaio/daytona/tree/ec4c21b2d597091ac09ecc278f3bcc172575a987) | `ec4c21b2d597091ac09ecc278f3bcc172575a987` | 2026-07-24T07:12:07Z | No current root license; README points to historical AGPL-3.0 |
| [daytona/clients](https://github.com/daytona/clients/tree/429a608f226cc29204cc2213ca05167531f26722) | `429a608f226cc29204cc2213ca05167531f26722` | 2026-09-25T14:48:10Z | Mixed CLI AGPL-3.0 / SDK, API and examples Apache-2.0 |
| [e2b-dev/E2B](https://github.com/e2b-dev/E2B/tree/ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b) | `ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b` | 2026-09-25T21:14:57Z | Apache-2.0; hosted terms separate |
| [microsoft/autogen](https://github.com/microsoft/autogen/tree/027ecf0a379bcc1d09956d46d12d44a3ad9cee14) | `027ecf0a379bcc1d09956d46d12d44a3ad9cee14` | 2026-04-15T11:59:09Z | Code MIT / documentation CC-BY-4.0 |
| [semgrep/semgrep](https://github.com/semgrep/semgrep/tree/56e04ee9581f76a2a1cfcdd806dd2d276851a39f) | `56e04ee9581f76a2a1cfcdd806dd2d276851a39f` | 2026-09-25T00:03:12Z | Engine LGPL-2.1; rule licensing separate |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks/tree/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b) | `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | 2026-09-23T04:14:00Z | MIT |

Two maintenance distinctions materially affect decisions:

- Daytona's [pinned historical-core README](https://github.com/daytonaio/daytona/blob/ec4c21b2d597091ac09ecc278f3bcc172575a987/README.md) says public core maintenance ended after development moved private in June 2026. Do not treat the public core as a currently supported dependency merely because it is not archived. The [current clients README](https://github.com/daytona/clients/blob/429a608f226cc29204cc2213ca05167531f26722/README.md) is a separate component with mixed client licenses; it does not establish an open or supported server implementation.
- AutoGen's [pinned README](https://github.com/microsoft/autogen/blob/027ecf0a379bcc1d09956d46d12d44a3ad9cee14/README.md) describes maintenance-only, community-managed status and directs new work toward Microsoft Agent Framework. MAF remains the forward-looking Microsoft comparison; [its README](https://github.com/microsoft/agent-framework/blob/6f1522a50b66f117da34cc25ea299ba24a528b15/README.md) describes multiple providers/runtimes and local/cloud patterns. Upstream readiness/support claims have not been independently execution-qualified here.

OpenHands application and Software Agent SDK remain separate reviewed components. Their current [application README](https://github.com/OpenHands/OpenHands/blob/47a10808d78561546a02555d0d2c7fa96fa96300/README.md) and [SDK README](https://github.com/OpenHands/software-agent-sdk/blob/d77ada7a030b3acaa82593d402632680361dfe42/README.md) support retaining the workspace/event boundary concepts, rather than assuming older application internals describe the current SDK. SWE-agent and mini-swe-agent remain useful research/runtime references; their published benchmark claims were not rerun. Semgrep engine, rule catalogs, paid tooling and hosted services must retain separate license/operational treatment; engine metadata alone does not authorize bundling every rule.

### Runtime recommendations after this pass

The original report contains the full capability mechanism, local source paths, benefits, cost and license analysis. Fresh maintenance evidence does not justify broadening dependency scope. The following are current bounded decisions, not acceptance of unmeasured performance claims.

| Capability | Recommendation retained | Evidence and reason | Remaining qualification or trigger |
|---|---|---|---|
| RT-01 checkpoint authority; RT-02 uncertain effects | **KEEP** local snapshots/journal/lease and conservative uncertain-outcome handling. | LangGraph, MAF, CrewAI and Temporal remain active references. Orqalis already has the relevant local authority boundaries; the real process-death fixture exercises restart rather than just exception cleanup. | Keep completed-result reuse and explicit uncertainty acknowledgement. No generic exactly-once claim or framework serializer import. |
| RT-03 process-death evaluation | **ADD, P1 implemented**, retain regression matrix. | One real controller run crosses eight deterministic killed-process boundaries from planning through branch attachment; command ownership has separate prepared/create/start barriers. | This is one chained scenario, not eight independent complete workloads. POSIX containment and real Docker remain unqualified. |
| RT-04 sandbox ownership; RT-10 bounded review reads | **ADAPT, P1 implemented**, keep the narrow local correction. | Durable per-invocation identity, live daemon/label verification and exact full-ID cleanup replace reliance on Python `finally`; oversize reads are capped. | Fake transport establishes fail-closed logic, not real daemon cleanup. Late daemon create can still leave a stopped resource. Windows Job termination alone is never container-cleanup evidence. |
| RT-05 typed actions/events; RT-06 fan-out and approvals | **KEEP** typed request/observation and orchestrator-owned DAG/approval authority. | OpenHands/MAF remain suitable comparisons; AutoGen is historical. Existing task/effect identity and one-writer rules are coherent. | The deterministic execution fixture witnesses overlapping read tasks and one repair, not general scheduler optimality. |
| RT-07 worker mailboxes and parallel writer worktrees | **DEFER, P2**. | No measured workload shows that general inter-agent messaging or concurrent mutable worktrees outweigh merge/conflict/recovery cost. | Require skewed-DAG/worktree integration benchmarks, typed mailbox ownership and conflict gating before accepting a new authority surface. |
| RT-08 hosted sandbox adapters and snapshots | **DEFER, P2**. | E2B and maintained OpenHands/Daytona client components offer optional environment concepts; current local scope does not require a remote runtime. | Need opt-in demand, capability/ownership contract, actual reconnect/cleanup tests and component/service/license review. Do not revive unmaintained Daytona core. |
| RT-09 test integrity | **ADAPT, P1 implemented**. | Conservative syntax checks reject loss of assertions, raises/warns/fail helpers, skip changes and newly invalid/overcomplex tests. Exact old/new hashes bind an intentional reviewed change to existing approval. | It is a Python heuristic; semantic weakening and arbitrary frameworks remain outside coverage. Benign refactors may need explicit review. |
| RT-11 external static scanners | **DEFER, P2**. | Gitleaks MIT and Semgrep LGPL engine remain plausible optional subprocess adapters; wider rule coverage has ongoing update/false-positive and licensing cost. | Require pinned executable/rules, bounded offline runs, redacted structured findings and exact diff-bound waivers. No scanner or rule catalog was installed or copied. |
| RT-12 wholesale orchestration replacement | **REJECT**. | No new maintenance evidence displaces the local-first filesystem authority in `SIGNOFF.md` and `SOURCE_OF_TRUTH.md`. | A mandatory server/database/cloud workflow authority remains outside the accepted architecture. |

### Cross-stream limits and remaining evidence

The original execution compatibility smokes used the same frozen provider/helper fixture against immutable baseline and current source. They exercised a persisted FAIL/repair/PASS path with nine provider invocations, two writes and 174 contiguous events. Those are correctness smokes of one deterministic scenario, not qualified timing distributions or live-model quality. An independent harness reviewer subsequently found that the execution report's count gate was too weak; that reviewer owns the correction and final evidence. Old smoke artifacts are preflight and must be regenerated after its script freeze. This audit does not certify another stream's unfinished harness changes.

The earlier independent G02 audit was bounded to small/depth/count fixtures. Root subsequently reproduced a native parser access violation on the fixed engineering corpus and large row/column values, then removed native Point property access and advanced the parser cache identity. See [the native parser correction evidence](KNOWLEDGE_RESEARCH.md#native-parser-preflight-correction). The earlier scoped result did not cover that native lifetime defect; it is not a global clean audit. Corpus/package/final-source verification belongs to the coordinating stream.

No live Docker, remote sandbox, external static scanner, complete upstream test suite, paid provider or model quality experiment ran in this iteration. No new production P0/P1 was established by the memory/maintenance slice; confirmed benchmark defects were corrected locally. A subsequent coordinating-stream cancellation finding is corrected below and prevents treating this iteration as clean. Source-qualified correctness and quiet-environment captures, full repository checks and a genuinely clean later iteration remain separate evidence requirements.


### Follow-up: cancellation polling under state-lock contention

The coordinating stream's original-contract run exposed `LockTimeoutError` in delivery's cancellation watcher while a validation thread owned the run state lock. The traceback alone proves contention, not a specific lock-order deadlock. Inspection found that `watch_cancellation` synchronously opened a UoW and read the run on the asyncio event loop. A deterministic current-code probe with a real `FileLock` then established a P1: a worker holds the state lock, and an event-loop callback is responsible for releasing it after the poll starts. The old poll blocks that callback until its lock acquisition times out. Pre-fix result: **1 failed in 2.11 seconds** at `watch_cancellation -> runs.get -> FileLock.acquire`.

The bounded correction moves each read to `at_checkpoint`, keeping the read UoW entirely in an owned thread and draining it before controller ownership can be released. Only the cancellation observation's `LockTimeoutError` is retried; it is neither treated as a cancelled run nor used to abort otherwise valid work. Other storage failures remain visible. No timeout value, advisory-lock policy or persistence schema changes. The first correction drained an in-flight poll before signalling work on caller cancellation. Independent review identified the resulting delay; a strengthened barrier test failed in 3.39 seconds, then the final implementation was corrected. Caller cancellation now signals both work and poll immediately, shields/drains the owned poll, and drains work before returning. The regression requires work to acknowledge cancellation while the poll barrier is still held, and repeated cancellation cannot release ownership early. Actual operation lock failures and non-lock read errors remain visible.

Validation:

- First thread-poll correction: [11 focused tests passed in 264.42 seconds](../evidence/cancellation-polling-regression.xml), including the original external-finding repair/finalize case (206.315 seconds), persisted cancellation (38.876 seconds), and event-sequence concurrency/idempotency/corruption (8.012 seconds).
- Final prompt-signal correction: [10 focused tests passed in 44.84 seconds](../evidence/cancellation-prompt-signal-regression.xml), covering all six polling cases, three command/cancellation regressions and persisted cancellation integration. Ruff formatting/check and strict mypy passed for the final source/test files. The application delivery/concurrency cases above ran on the first correction; their normal observation path is retained, but final-source full regression still belongs to the coordinating stream.

The concurrency case's isolated pass does not explain or waive its separate full-preflight failure; that traceback remains required. This cancellation source change supersedes the earlier memory-smoke snapshot as a final-source candidate. No broad lock-order or real-time cancellation guarantee is claimed for every synchronous application path.

---

### Final scoped audit: runtime

Date: 2026-09-26. Status: **scoped review complete; global qualification pending; work paused at the user's request**. This report covers O04, X01, S01 and S02 only. It does not certify graph, memory, UI, package, benchmark or complete-product convergence.

The reviewed production source is the provisional freeze captured at `2026-09-26T16:50:12.736553+00:00`, SHA-256 `a37dda9e2ca4d37e58ffc6fcab606324df31e16b02dc1261a3371cd44792a757`. The last completed source comparison and all six final diagnostics still matched it. No production source changed during this final audit. The immutable baseline remains `b8506f7d9c471516fe4b21c9caa735a7a7909af6`; its tag was not moved. The coordinating stream owns final whole-tree qualification and handoff.

No new production P0/P1 was established in this bounded review. A missing S02 evidence case was added and passed. A separate preflight concurrency timeout remains preserved with an unknown precise cause; unchanged lock semantics and quiet repetitions support proceeding without an unsupported production lock change, while retaining the final regression gate.

#### Reviewed controls and acceptance limits

| Capability | Final-source inspection and completed evidence | Disposition and limits |
|---|---|---|
| O04: durable process-death and cancellation ownership | Inspected controller leases, recovery, checkpoint receipts, `execution/cancellation.py`, and the eight-barrier real controller-death fixture. Cancellation reads open/read/close their UoW in one owned worker. Caller cancellation signals actual work before draining an already-running poll; repeated cancellation cannot abandon that worker or release the controller lease early. Only a poll's `LockTimeoutError` is retried; actual operation errors and other read failures remain visible. | **ADD retained, implemented; final full-suite qualification pending.** Existing receipts prevent replay only where completion is durably known. Arbitrary external effects are not exactly once. The chained matrix is one scenario crossing eight barriers, not eight independent complete workloads. |
| X01: durable sandbox identity and reconciliation | Inspected `execution/sandbox.py`, `commands.py`, `workspaces.py`, ToolService, executor validation, delivery validation and recovery wiring. An atomic per-invocation receipt precedes create; create does not start workspace code. Cleanup checks the exact daemon identity, live ownership labels and a full 64-hex container ID; only that ID can be removed. Cleanup requires observed absence, and uncertainty retains the receipt and prevents PASS. Receipt paths stay outside the writable workspace and reject unsafe containment. | **ADAPT retained, implemented; real Docker qualification absent.** Writable host receipts are not sufficient deletion authority: independent live daemon/label/ID checks are required. Fake-daemon prepared/create/start hard-death barriers qualify the decision logic only. A Windows Job kills owned local processes; it does not prove cleanup of daemon-owned containers. Late daemon create can leave a stopped resource. |
| S01: test integrity with reviewed exceptions | Inspected `delivery/test_integrity.py`, Guardian, delivery policy serialization, approval subject and final tree checks. Loss of Python assertions, unittest assertion calls and pytest raises/warns/fail checks is conservative review-required evidence. New disable/skip changes and newly invalid/overcomplex Python tests fail closed; repair of an invalid baseline is allowed. An intentional reduction requires path plus exact old/new content hashes in the reviewed policy. | **ADAPT retained, implemented; heuristic scope explicit.** Count-preserving semantic weakening, arbitrary frameworks and all alias transformations are not proved safe. Legitimate refactors can require review. The exception applies to test reduction only and does not waive other Guardian controls. Empty policy additions preserve legacy approval subject behavior. |
| S02: bounded review reads | Inspected changed-file stat checks and `read(limit + 1)` in Guardian and workspace hashing. Existing before-content Git reads use immutable object size bounds. Added a deterministic test that grows the changed file precisely between the successful size check and binary open, for both consumers. | **ADAPT retained; focused gap closed.** Both cases reject the grown file after requesting/returning exactly 10,000,001 bytes. This establishes a read bound for this race, not atomic inspection of a maliciously changing filesystem. |

Application sandbox ownership is supplied by ToolService, executor validation and final delivery validation. Reconciliation is reached under controller ownership through workspace ensure, recovery and delivery. The ownerless evaluation validator path uses explicitly approved `trusted_local` commands; it is not a missing Docker owner. Low-level standalone CommandRunner use without an owner does not gain a durable ownership ledger automatically. No prefix-based or path-derived container deletion was introduced.

The reviewed Guardian path also retains protected-path, symlink/junction/hardlink, secret, binary, scope and final-tree restrictions. Review policy hashes participate in approval identity. These source findings retain the acceptance boundaries documented in [the original runtime research](RUNTIME_RESEARCH.md), rather than expanding the architecture or importing upstream frameworks.

#### Completed focused evidence and provenance

The added `test_growing_changed_file_is_bounded_after_size_check` parametrization in `tests/unit/test_guardian_integrity.py` uses an exact open barrier, not sleep-based scheduling. The file begins below the size limit, then grows to limit plus one. The wrapper asserts the requested read size and returned byte count; Guardian must return a failed unsafe-path finding with an unverified tree, and workspace hashing must raise `PolicyDeniedError`.

Result: **2 passed, 17 deselected in 26.64 seconds**, [JUnit](../evidence/guardian-growth-final-audit-1.xml). Ruff format/check and strict mypy passed for the test file. These two new cases must be included in the next full collection. They are test-only changes and do not alter the production freeze.

Earlier cancellation evidence is retained in [preflight audit 1](#runtime-independent-audit-iteration-1). The first worker-poll correction passed 11 focused cases, including external-finding repair/finalize and the concurrency case. After the prompt-cancellation refinement, the final cancellation source passed **10 focused cases in 44.84 seconds**, including all six polling cases, command cancellation and persisted cancellation integration: [final prompt-signal JUnit](../evidence/cancellation-prompt-signal-regression.xml). The earlier external-finding application run was before that last refinement; do not relabel it a final full-suite result.

The final diagnostic script and Guardian test passed Ruff and strict mypy together. No additional tests or upstream work were started after the user requested a stop.

#### Preserved concurrency failure and grounded disposition

The full preflight result was **604 passed, 2 skipped, 1 failed in 4468 seconds**. The failed case was `test_event_sequence_concurrency_idempotency_and_corruption_detection`, case duration 26.256 seconds. [The preserved JUnit](../evidence/regression-preflight-full.xml) shows `ThreadPoolExecutor(max_workers=4)` appending eight events; one worker failed in `FileLock.acquire` at the in-process `threading.RLock` gate's 10-second acquisition deadline. This is separate from the corrected asyncio cancellation-poll defect. The failure alone does not reveal the owning thread's hold duration, queued preceding commits, scheduler delays or fairness. The old failed fixture directory was no longer present for additional ledger inspection.

The source comparison is explicit in [lock-source-comparison.json](../evidence/lock-source-comparison.json):

- `locking.py` is byte-identical to baseline, SHA-256 `0b6a097ea313ab219e08d95528476eb179f87f70dddee057f53eb500fb98ef53`.
- `unit_of_work.py` and `io.py` are also byte-identical. Nine selected acquire/release, state-lock, load, recover, commit, close, event append and index methods have identical AST hashes.
- `task_store.py` changes only the projection of memory-preview metadata. This event-only fixture does not construct a memory context. These comparisons establish unchanged inspected code, not a guarantee of identical whole-program timing or fairness.

After all other agents confirmed their heavy jobs stopped, the same frozen test and fixture ran three times per source, alternating baseline/current, each in an isolated child (`-I`). [The diagnostic](../../../scripts/diagnose_lock_contention.py) wraps FileLock calls and fsync only for in-memory timing; it does not change lock deadlines, commit behavior or the contract. Import auditing verifies selected-source modules, and each report binds source, fixture, helper, environment and script. Instrumentation changes scheduling, so these are diagnosis captures, not throughput/speedup measurements.

| Source/repetition | Pytest case seconds | Maximum lock wait seconds | Maximum lock hold seconds | Outcome |
|---|---:|---:|---:|---|
| baseline 1 | 4.957 | 0.859101 | 0.384111 | PASS |
| current 1 | 5.207 | 0.732697 | 0.629208 | PASS |
| baseline 2 | 4.731 | 0.726870 | 0.381387 | PASS |
| current 2 | 4.843 | 0.727051 | 0.442642 | PASS |
| baseline 3 | 4.318 | 0.804466 | 0.387344 | PASS |
| current 3 | 4.253 | 0.895108 | 0.461695 | PASS |

All six final-script captures had no lock acquisition failures, no unreleased acquisitions, no import escapes, and stable source/fixture/helper/script checks. [The summary and raw trace links](../evidence/lock-diagnostic-summary.json) preserve JUnit identities and hashes. These six captures replaced the initial diagnostic files after a test-side typing cleanup. The initial six successful console observations are separately preserved as [console-only observations](../evidence/lock-original-console-observations.json); their original raw traces and script hash are not retained. They must not be presented as additional fully bound performance samples.

**Disposition:** no new lock regression or concrete corrective production change was established. The unchanged 10-second deadline can reject a contended writer; Python's RLock does not provide a fairness guarantee. Quiet passes do not explain or waive the observed preflight failure, and unrelated concurrent workloads are only a plausible contributor, not a proven cause. No timeout was increased and no assertion relaxed. The next isolated whole-suite run remains a required gate; a recurrence should retain lock owner/wait/hold diagnostics before any design change is proposed.

#### Fresh upstream observations and retained decisions

The [final upstream evidence register](../evidence/final-audit-1-runtime-upstreams.json) re-observed all 14 public HEADs and pinned README bytes starting at `2026-09-26T16:52:46.123202+00:00`. All HEADs and README hashes matched the preceding research. Fresh GitHub repository metadata requests returned `HTTPError`; the evidence did not record a status code. Therefore this pass does not claim newly verified `pushed_at`, archived or disabled metadata. The successful metadata observations in [preflight audit 1](#runtime-independent-audit-iteration-1) remain explicitly dated around 16:13 UTC. License classifications carry forward pinned-file inspection at unchanged revisions; this pass did not reread every nested license.

| Primary reference | Exact HEAD | License scope retained |
|---|---|---|
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph/tree/7daa3ab49d678a5da75edb08baa87db4a2be52c3) | `7daa3ab49d678a5da75edb08baa87db4a2be52c3` | MIT |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework/tree/6f1522a50b66f117da34cc25ea299ba24a528b15) | `6f1522a50b66f117da34cc25ea299ba24a528b15` | MIT |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI/tree/4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec) | `4ed2abc7bbf504a634d3b733f2a97e0fbe8d44ec` | MIT |
| [temporalio/temporal](https://github.com/temporalio/temporal/tree/d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d) | `d8f9c6d86b2cd0ea5c27d0694a598da84c6d337d` | MIT |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands/tree/47a10808d78561546a02555d0d2c7fa96fa96300) | `47a10808d78561546a02555d0d2c7fa96fa96300` | MIT root; component exceptions separately scoped |
| [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk/tree/d77ada7a030b3acaa82593d402632680361dfe42) | `d77ada7a030b3acaa82593d402632680361dfe42` | MIT |
| [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5) | `3ea751c087f32b16e039a2233dd6eefecef325d5` | MIT; separate runtime dependencies |
| [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent/tree/04d809ceab9df28f9adaed044884180159172930) | `04d809ceab9df28f9adaed044884180159172930` | MIT |
| [daytonaio/daytona](https://github.com/daytonaio/daytona/tree/ec4c21b2d597091ac09ecc278f3bcc172575a987) | `ec4c21b2d597091ac09ecc278f3bcc172575a987` | Current root has no license; historical core AGPL-3.0 |
| [daytona/clients](https://github.com/daytona/clients/tree/429a608f226cc29204cc2213ca05167531f26722) | `429a608f226cc29204cc2213ca05167531f26722` | CLI AGPL-3.0; SDK/API/examples Apache-2.0 |
| [e2b-dev/E2B](https://github.com/e2b-dev/E2B/tree/ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b) | `ccaf9fc0ffe6ac39c7ec786af7608ab1de19467b` | Apache-2.0; hosted service terms separate |
| [microsoft/autogen](https://github.com/microsoft/autogen/tree/027ecf0a379bcc1d09956d46d12d44a3ad9cee14) | `027ecf0a379bcc1d09956d46d12d44a3ad9cee14` | Code MIT; documentation CC-BY-4.0 |
| [semgrep/semgrep](https://github.com/semgrep/semgrep/tree/56e04ee9581f76a2a1cfcdd806dd2d276851a39f) | `56e04ee9581f76a2a1cfcdd806dd2d276851a39f` | Engine LGPL-2.1; rules separately licensed |
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks/tree/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b) | `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | MIT |

Daytona's pinned historical-core README says public core development moved private in June 2026 and maintenance ended. Its maintained clients are separately licensed components, not proof of an open supported server. AutoGen remains a historical, maintenance-only reference; Microsoft Agent Framework is the forward-looking Microsoft comparison. OpenHands application and Software Agent SDK remain distinct components. Public benchmark or vendor support claims were not rerun or independently certified.

Decisions remain:

- **KEEP:** local checkpoint/journal authority, controller leases, conservative uncertain-effect handling, typed requests/observations, independent approvals and orchestrator-owned DAG transitions. LangGraph, MAF, CrewAI and Temporal provide useful semantics without displacing local authority.
- **ADAPT/ADD:** the narrow ownership, cancellation, hard-death, test-integrity and bounded-read corrections already implemented. This audit adds evidence, not a new runtime dependency.
- **DEFER:** parallel writer worktrees and worker mailboxes until conflict/ownership benchmarks justify them; hosted sandbox adapters until demand, reconnect/cleanup and component/service license qualification exist; external scanners until pinned offline rules, bounded execution, structured redaction and exact diff-bound waivers are qualified.
- **REJECT:** wholesale orchestration replacement or a mandatory remote database/server/cloud workflow authority. The reviewed architecture does not require one.

#### Remaining work for the next session

1. Resume only when the user asks. No runtime-agent test, benchmark or research process remains active.
2. Run the prepared final isolated whole-suite gate with the two added S02 cases, stable source/tests/helpers/environment bindings and no competing heavy workloads. Preserve the existing failed preflight evidence. A new failure is a gate, not a reason to raise the timeout.
3. Complete coordinating-stream final static, package, UI and benchmark gates and two clean audit iterations. Existing preflight captures must not be promoted across source/helper changes without matching provenance.
4. Run deferred quiet baseline/current execution, memory and quality captures under the frozen contracts if still required by the master acceptance plan. Runtime diagnostic timings are not substitutes for those workload metrics.
5. Keep live Docker, POSIX process containment, remote sandbox behavior, upstream suites and real-model quality explicitly unqualified unless their required environment and authorization are provided. No global convergence claim is made here.
