# Enhancement backlog

## Next-release cache performance: PERF-COLD-01

The user accepted cold graph-rebuild cost for2.1.0 on2026-10-09 and deferred
optimization to the next release; its version is not selected. The fixed matched
SDK study measured candidate4.672/8.471s versus baseline1.504/1.597s. Later reader
controls were inconclusive, including native14.632/5.713s and CRT4.943/6.390s.
Retain all costs and unknown causes. [Authorization](evidence/release-cold-performance-user-acceptance-2.1.0-v1.json)
is a release-specific exception, not evidence of a fix.

Investigate a simple cache-storage design that reduces independent file transactions
while preserving fresh bytes, parser/version/hash checks, strict decoding, containment,
snapshot reads, atomic publication, missing/corrupt recovery and bounded memory.
Reject weak CRT readers, stat-only freshness shortcuts and blind timing retries.
Validate with focused semantic/security checks, prospectively fixed SDK comparisons
and two complete source-bound qualifications. [Status](ENHANCEMENT_STATUS.md) owns
the raw results and rejected experiments; avoid adding another narrative worklist.


Updated 2026-10-09 for candidate 2.1.0. **Full release qualification pending.** Priority reflects accepted engineering work, not project popularity.
IMPLEMENTED_PENDING_EVAL means code and focused checks exist; it does not mean the full program passed.
Dependencies identify order, not a requirement to adopt upstream packages. All P1 items must close before sign-off.
Current source01/inputa0 passes focused133/static13/immutable86, installed17/MCP41,
heldout263 and history1001 semantics. Both whole30/31 completed with933 PASS/two
explicit optional SKIP/zero FAIL/ERROR each; both browser14 suites and all timed
phases passed. Execution medians25.810/20.452s compare with pooled55.870s.
Larger-corpus cold8,011ms crossed its investigation threshold and is explicitly
accepted for2.1.0; broader per-ID evaluation and final docs/package checks remain. No capability is promoted in advance.
[Status](ENHANCEMENT_STATUS.md) owns evidence; [the worklist](NEXT_SESSION.md) owns
the remaining investigation, final acceptance and distribution checks.

Release-specific update: the user accepted cold graph-rebuild cost for2.1.0;
PERF-COLD-01 is deferred to the next release. Two completed local qualification rounds
can be accepted WITH EXCEPTION. Broader capability evaluation remains pending;
all23 statuses below are unchanged, including I03's missing current1,001-row latency
attribution. The accepted cost does not certify universal or clean OSS convergence.
[Authorization](evidence/release-cold-performance-user-acceptance-2.1.0-v1.json) and
[worklist](NEXT_SESSION.md) own the exact exception and remaining gates.

## O04 - P1 - Recovery

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADD.

Reference: Temporal; LangGraph; Agent Framework ([evidence](research/RUNTIME_RESEARCH.md)). Gap: Process death skips finally blocks.

Desired behavior / acceptance: Add deterministic child-process death/restart barriers across all phases.

- Test strategy: Owned-child kill/restart at planning, execution, tool, review, repair, docs and Git boundaries; no duplicate effect; real-lock polling starvation, prompt cancellation and repeated-cancel ownership drain.
- Benchmark strategy: Restart outcome, event continuity, side-effect count; live Docker tier separate.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: O02.

## X01 - P1 - Execution

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: OpenHands SDK; SWE-agent; E2B ([evidence](research/RUNTIME_RESEARCH.md)). Gap: Orphan uncertainty and ignored cleanup failure.

Desired behavior / acceptance: Persist exact ownership, inspect labels, reconcile before reuse/recovery; fail closed.

- Test strategy: Create/start/inspect/remove fake transport; crash windows; mismatch/daemon denial; all application command paths.
- Benchmark strategy: Zero unrelated deletion or unsafe concurrent writer; deterministic cleanup outcomes.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: O02.

## S01 - P1 - Change Guardian

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: Superpowers; SWE-agent; Semgrep concepts ([evidence](research/RUNTIME_RESEARCH.md)). Gap: Test weakening can pass the current deterministic guard.

Desired behavior / acceptance: Detect conservative AST/diff signals; exact reviewed hash-bound exception.

- Test strategy: Assertion removal, skip/xfail, legitimate refactor, exact-hash approvals and stale approval denial.
- Benchmark strategy: Zero known weakening fixture misses; documented false positives.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: O03.

## S02 - P1 - Change Guardian

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: OpenHands runtime; bounded resource patterns ([evidence](research/RUNTIME_RESEARCH.md)). Gap: Oversized changed file can exhaust controller memory.

Desired behavior / acceptance: Stat and bounded reads before secret/diff analysis.

- Test strategy: Sparse/oversized file, growth race, ordinary allowed file.
- Benchmark strategy: Read bound and explicit denied outcome.
- Estimated impact: High; implementation scope: Low.
- Dependencies: None.

## G01 - P1 - Graph

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: Graphify ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Unknown receiver can bind to unrelated unique name.

Desired behavior / acceptance: Separate extracted occurrences from inferred target bindings; invalidate cache.

- Test strategy: Unknown receiver, aliases, shadowing, duplicate names, inheritance and rebuild equality.
- Benchmark strategy: Zero false extracted target bindings on labeled fixtures.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: None.

## G02 - P1 - Graph

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADD.

Reference: Tree-sitter; Graphify; Aider ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Own frontend lacks symbol-level intelligence.

Desired behavior / acceptance: Add native abstraction for pinned JS/TS/TSX grammars with declared limits.

- Test strategy: Multiline/generics/JSX/imports/classes/interfaces/partial syntax; Python parity; package portability.
- Benchmark strategy: Symbol/location accuracy, indexing time/size and parser cache reuse.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: G01.

## G04 - P1 - Graph navigation

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADD.

Reference: Graphify; Serena ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Baseline lacked impact/shortest-path surface.

Desired behavior / acceptance: Retain Orqalis-owned bounded traversal in SDK/CLI/MCP.

- Test strategy: Cycles, direction, ambiguity, provenance, bounds, SDK/CLI/MCP contract.
- Benchmark strategy: Returned nodes/bytes vs whole graph; deterministic witness validity.
- Estimated impact: High; implementation scope: Low.
- Dependencies: G01.

## G05 - P1 - Source tools

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADD.

Reference: Serena/SolidLSP; multilspy ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Useful source cannot be read precisely through graph contract.

Desired behavior / acceptance: Add bounded native outline/body/reference reads with source-hash checks.

- Test strategy: Duplicate/nested/decorated/Unicode symbols, stale source, path escape, byte limits.
- Benchmark strategy: Exact source selection and bytes avoided versus full-file read.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: G01; G02.

## R01 - P1 - Retrieval

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADAPT.

Reference: Aider; Agent-Memory ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Baseline inconsistent tokenization misses identifier parts.

Desired behavior / acceptance: Use shared whole-word/snake/camel terms; invalidate lexical index version.

- Test strategy: Identifier/acronym/noise cases, index invalidation, memory/context parity.
- Benchmark strategy: Fixed labels, recall/precision/MRR/nDCG, negative queries and size.
- Estimated impact: High; implementation scope: Low.
- Dependencies: E01.

## R02 - P1 - Retrieval

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADAPT.

Reference: Aider ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: No evidence yet that changing ranker beats existing one.

Desired behavior / acceptance: Measure held-out gold and negative context; change only on demonstrated benefit.

- Test strategy: Hard serialized budget, negatives clearly marked or omitted, held-out recall.
- Benchmark strategy: At least 24 varied queries; bytes per relevant target; no unexplained recall loss.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: E01.

## M02 - P1 - Project Memory

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: Graphiti; Mem0; coding-agent-memory-mcp ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Contradictory predecessors remain eligible; stale proposal race.

Desired behavior / acceptance: Reviewed digest-bound supersession with atomic lifecycle metadata.

- Test strategy: Pending/rejected no-op; approval idempotency; concurrent stale approvals; crash windows; history preserved.
- Benchmark strategy: Only current active fact in default retrieval; old fact still inspectable.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: M01.

## M03 - P1 - Project Memory

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: Serena; current Letta; MCP memory ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: Large useful records may be omitted by context budget.

Desired behavior / acceptance: Bounded excerpts/discovery and explicit ID references; fetch detail on demand.

- Test strategy: Broken/self/cyclic/cross-project refs; depth/node/byte caps; exact ID access.
- Benchmark strategy: Metadata/detail context bytes, reference accuracy, long-record visibility.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: M02; E01.

## M04 - P1 - Project Memory

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADD.

Reference: Agent-Memory; Serena ([evidence](research/KNOWLEDGE_RESEARCH.md)). Gap: New lifecycle and references require inspectable integrity.

Desired behavior / acceptance: Shared integrity report and CLI/MCP projection.

- Test strategy: Corrupt schema, dangling predecessor/successor, cycles, unsafe paths; no silent omission.
- Benchmark strategy: Deterministic issue count; valid corpus clean.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: M02; M03.

## H01 - P1 - Skills

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADAPT.

Reference: Agent Skills; Codex; Awesome Copilot ([evidence](research/HARNESS_RESEARCH.md)). Gap: Baseline TOML-only; native body/resource support added.

Desired behavior / acceptance: Retain explicit trusted roots, hashes and tool requirements as constraints.

- Test strategy: Malformed YAML, aliases, links, path escape, changed hash, role/tool requirements.
- Benchmark strategy: Portable discovery/activation/resources bytes and correct routing.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: E01.

## H02 - P1 - Skills

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADD.

Reference: Superpowers; Promptfoo; Codex ([evidence](research/HARNESS_RESEARCH.md)). Gap: No stable routing confusion matrix or disclosure measurements.

Desired behavior / acceptance: Versioned routing/portability evaluation; model quality explicitly unknown without paid runs.

- Test strategy: Positive/negative scope, role restrictions, explicit pins, schema-compatible provider serialization.
- Benchmark strategy: FP/FN counts, selected vs eager bytes, latency; never fabricate tokens.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: E01; H01.

## I01 - P1 - Assistant integrations

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: Codex; Claude Code; Copilot; OpenCode; Goose ([evidence](research/HARNESS_RESEARCH.md)). Gap: Generic MCP evidence must not imply native-host certification.

Desired behavior / acceptance: Document and evaluate supported config/root/discovery/continuation/error contract.

- Test strategy: Fresh stdio clients, two-client continuation, root isolation, permission failure and configuration syntax.
- Benchmark strategy: Initialize/discovery latency and deterministic contract passes; native-host limits explicit.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: I02; H02.

## I02 - P1 - MCP

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADD.

Reference: MCP SDK; OpenCode; Goose ([evidence](research/HARNESS_RESEARCH.md)). Gap: Missing pause/resume/cancel/recover interface.

Desired behavior / acceptance: Expose existing services behind server work policy and root binding.

- Test strategy: Readonly denied, scoped run, legal transitions, explicit uncertainty, repeated calls.
- Benchmark strategy: Lifecycle contract pass/fail; no duplicated effects.
- Estimated impact: High; implementation scope: Low.
- Dependencies: O04; X01.

## I03 - P1 - MCP

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: MCP SDK; GitHub MCP server ([evidence](research/HARNESS_RESEARCH.md)). Gap: Old history unreachable; large payloads costly.

Desired behavior / acceptance: Add root/revision-bound pagination and bounded graph discovery while preserving old tools.

- Test strategy: Multiple pages, no duplicate/omission, stale/tampered/cross-root cursors, payload limits.
- Benchmark strategy: 1000+ history rows and graph node pages; bytes and latency.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: G04.

## T01 - P1 - Telemetry

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: OpenHands; OTel; Langfuse ([evidence](research/HARNESS_RESEARCH.md)). Gap: Declared trace fields not assigned; UI separates call lists.

Desired behavior / acceptance: Project existing parent IDs into local trace hierarchy and allowlisted spans.

- Test strategy: Run/task/actor/model/tool correlation; historic missing fields; no secrets/prompts.
- Benchmark strategy: Actual persisted fixture hierarchy and overhead.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: I02.

## T02 - P1 - Control Center

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Assigned specialist. Decision: ADAPT.

Reference: OpenHands; Langfuse ([evidence](research/HARNESS_RESEARCH.md)). Gap: Timeline omits model/tool intervals and critical path cues.

Desired behavior / acceptance: Consume backend projections; test actual multi-agent/repair snapshots.

- Test strategy: API-derived intervals, parallel/blocked/repair state, empty/historical data, mobile layout.
- Benchmark strategy: Browser update latency, event/payload sizes, bundle deltas.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: T01.

## T03 - P1 - Telemetry

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADAPT.

Reference: Langfuse; AgentOps ([evidence](research/HARNESS_RESEARCH.md)). Gap: Baseline lacked provider grouping.

Desired behavior / acceptance: Keep nearest-rank p50/p95 and coverage counts sourced from invocations.

- Test strategy: Completed/running/cancelled/error outcomes, unknown vs zero, SSR and live API table.
- Benchmark strategy: Reported coverage, API/UI equality; no fabricated cost.
- Estimated impact: High; implementation scope: Low.
- Dependencies: E01.

## E01 - P1 - Evaluation

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADD.

Reference: Promptfoo; DeepEval; Agent-Memory ([evidence](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research)). Gap: Improvement claims lack reproducible baseline.

Desired behavior / acceptance: Source-isolated 14-category corpus plus held-out retrieval/routing/contract suite.

- Test strategy: Dataset/source hash isolation; reject incomplete/mismatched reports; existing integration contracts.
- Benchmark strategy: Before/after context, recall, startup, graph/memory/disk; unknown model metrics explicit.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: None.

## E04 - P1 - Distribution/performance

Status: **IMPLEMENTED_PENDING_EVAL**. Owner: Root. Decision: ADAPT.

Reference: Existing Orqalis; Tree-sitter/PyYAML dependency audit ([evidence](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research)). Gap: New parser/skill dependencies need measured footprint.

Desired behavior / acceptance: Verify licenses, wheel availability, startup/bundle/disk and offline contracts.

- Test strategy: Wheel build, npm launcher, manifest linkcheck, no baseline tag change.
- Benchmark strategy: Cold/warm startup, memory/disk/bundle vs baseline; optional Docker not required.
- Estimated impact: High; implementation scope: Medium.
- Dependencies: G02; H01; E01.

## Reconsideration queue

DEFER decisions are listed in the matrix and reviewed on every iteration. They are not silently accepted P1 work.
Native harnesses, parallel writers, LSP/SCIP, vectors, remote sandboxes and exporters remain optional opportunities with explicit workload/dependency reasons.

## Exact next step

Current source and ordered remaining qualification are recorded in ENHANCEMENT_STATUS.md and NEXT_SESSION.md. Earlier source-bound contracts, larger-corpus probes, partial rounds and installed artifacts remain preserved. Count only actual complete accepted rounds. Retain raw REVIEW tradeoffs and close individual criteria only after independent disposition; no commit or publication is authorized.
