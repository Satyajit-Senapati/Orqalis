# Independent relevance review after occurrence ranking correction

Reviewed 2026-09-26. No production ranking edits, query changes or label changes were made in this review. The inspected corpus is the same frozen 30-path slice of v2.0.0 for both implementations, plus the four declared durable facts; it is not a whole-repository relevance judgment. The benchmark's gold lists are **primary target paths**, not exhaustive annotations of every useful result. Thus reported precision is labeled-target precision, not a human judgment that every non-gold path is irrelevant.

Evidence: [unchanged dataset](../../../benchmarks/engineering_cases.json), [baseline capture](../evidence/preflight-baseline-quality-v2-smoke.json), [current lexical-v3 capture](../evidence/preflight-current-quality-v3-smoke.json), and [comparison](../evidence/preflight-quality-ranking-smoke-comparison.json). Dataset SHA-256: `03088229d1f1a335fc454baa2ac86a781ff212693e8c3520efae34ac032c2263`; baseline source fingerprint: `7dcede8468792d5c51805bb3fc865f09370892ba6ca101d40dcfd6b840fcbad7`; current source fingerprint: `d61354eb1786571741402d0e10838f25ef1728c0c24c5ed93582c6394b46d9a8`. The retained JSON files are byte-identical preflight copies; [their artifact manifest](../evidence/preflight-ranking-evidence-manifest.json) records exact byte sizes and SHA-256 hashes. Their embedded statuses were not changed or promoted. Raw reports contain timing fields from smoke under concurrent load; this review uses only deterministic retrieval witnesses and makes no timing claim.

## Assessment

The occurrence-category correction closes the concrete new defect: exact declarations such as `source_hashes` and `PermissionProfile` again precede caller occurrences. Every held-out exact-symbol query in this set now returns its defining path first. Keeping explicit REFERENCE index records and reference-navigation tools preserves the useful caller evidence without using unresolved occurrences as primary context seeds.

There are **no newly demonstrated P1 ranking correctness defects in the remaining reviewed cases**. This is a bounded disposition, not universal search quality signoff. One positive index case has a real target-recall regression: memory documentation leaves top five, even though the definition and durable fact remain high and the context channel newly retains both gold paths. Documentation-only MRR also falls (doc rank 2 to 5), and provider-refactor first-hit rank falls because its directly relevant request/response schema is now first. These losses stay recorded; they are not relabeled away.

Most precision losses add lower-ranked component-term matches while preserving the exact primary target first. Some additions are useful consumers/contracts; others are weak generic source/type/input/task matches. Identifier decomposition necessarily broadens recall. Suppressing all such results or boosting named gold documents would be unjustified corpus tuning. A future quality slice can evaluate explicit exact-symbol versus broad-text modes or document-body retrieval against a new held-out corpus, without changing this dataset or requiring a vector database.

Measured mean positive-case index recall moves 72.22% to 87.04%, context recall 85.19% to 87.04%. These aggregate gains do not erase the case-level regressions. Existing misses remain: frontend type-contract retrieval, architecture Markdown section retrieval, interrupted-task paraphrase retrieval, and broad hub disambiguation. The two negative cases have no matched current index/context paths, but still carry explicitly labeled orientation paths; do not report them as empty context.

## Per-case review

### bug-fix: `tokenize project index search identifiers`

**Accept improvement with tail noise.** Index target indexing/service.py rises from rank 3 to 1. mcp/server.py exposes project search, context/builder.py consumes project context, and docs/03-project-memory.md explains retrieval. web/src/types.ts is only a weak shared project/index vocabulary match; its addition does not displace the target.

- Fixed gold: `src/orqalis/indexing/service.py`.
- Current index order: `src/orqalis/indexing/service.py`, `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`, `web/src/types.ts`, `src/orqalis/context/builder.py`.
- Current matched-context order: `src/orqalis/indexing/service.py`, `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`, `web/src/types.ts`.

### refactor: `provider request response execution worker`

**Accept semantic tradeoff.** domain/provider.py defines ProviderExecutionRequest/ProviderExecutionResult and is directly relevant to provider request/response refactoring. Its move to index rank 1 lowers target-only MRR but both worker.py and agents/service.py are now in top 3 (agents was absent before). Context still omits agents/service.py as baseline did; this remains an incomplete cross-module view, not a new regression.

- Fixed gold: `src/orqalis/agents/service.py`, `src/orqalis/execution/worker.py`.
- Current index order: `src/orqalis/domain/provider.py`, `src/orqalis/execution/worker.py`, `src/orqalis/agents/service.py`, `src/orqalis/domain/execution.py`, `src/orqalis/execution/commands.py`.
- Current matched-context order: `src/orqalis/domain/provider.py`, `src/orqalis/execution/worker.py`, `src/orqalis/execution/evaluator.py`, `src/orqalis/domain/execution.py`.

### frontend: `MetricsView duration statistics telemetry`

**Accept with known incomplete recall.** MetricsView.tsx stays rank 1. observability/analytics.py supplies duration/statistics logic. indexing/service.py and graph/engine.py are weak duration/metrics partial matches for this UI request. web/src/types.ts is missing in both revisions; syntax support alone does not guarantee type-contract retrieval.

- Fixed gold: `web/src/MetricsView.tsx`, `web/src/types.ts`.
- Current index order: `web/src/MetricsView.tsx`, `src/orqalis/indexing/service.py`, `src/orqalis/graph/engine.py`, `src/orqalis/observability/analytics.py`.
- Current matched-context order: `web/src/MetricsView.tsx`, `src/orqalis/observability/analytics.py`, `src/orqalis/indexing/service.py`.

### backend: `MCP create task project root policy`

**Accept improvement.** mcp/server.py rises from index rank 3 to 1. Context retains server.py and task/documentation context. Extra root/context/index and policy-memory paths are plausible partial task/project/policy matches.

- Fixed gold: `src/orqalis/mcp/server.py`.
- Current index order: `src/orqalis/mcp/server.py`, `src/orqalis/context/builder.py`, `src/orqalis/indexing/service.py`, `.orqalis/memory/records/MEM-20260926-0004.md`, `.orqalis/memory/records/MEM-20260926-0002.md`.
- Current matched-context order: `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`, `src/orqalis/domain/task.py`.

### architecture: `atomic snapshot filesystem transaction recovery`

**Accept existing limitation.** Filesystem durability memory and filesystem/io.py remain the leading matches; web/src/types.ts snapshot and indexing/curated atomic writes are secondary. docs/07-data-model-and-observability.md has a real Atomic transaction and recovery section but remains missing in both versions. Filename/title-centric document indexing does not fully search Markdown sections.

- Fixed gold: `src/orqalis/persistence/filesystem/io.py`, `docs/07-data-model-and-observability.md`.
- Current index order: `.orqalis/memory/records/MEM-20260926-0001.md`, `src/orqalis/persistence/filesystem/io.py`, `web/src/types.ts`, `src/orqalis/indexing/service.py`, `src/orqalis/memory/curated.py`.
- Current matched-context order: `src/orqalis/persistence/filesystem/io.py`.

### test-failure: `WorkspaceEvaluator validation evidence criterion`

**Accept with tail noise.** WorkspaceEvaluator definition stays rank 1. execution/worker.py uses the evaluator, domain/execution.py contains validation commands, and web/src/types.ts models evidence. graph/engine.py is a weak evidence keyword match. Target recall and first rank are unchanged.

- Fixed gold: `src/orqalis/execution/evaluator.py`.
- Current index order: `src/orqalis/execution/evaluator.py`, `web/src/types.ts`, `src/orqalis/domain/execution.py`, `src/orqalis/graph/engine.py`, `src/orqalis/execution/worker.py`.
- Current matched-context order: `src/orqalis/execution/evaluator.py`, `src/orqalis/domain/execution.py`, `web/src/types.ts`.

### git-conflict: `worktree delivery commit base conflict`

**Accept improvement.** Index newly retrieves git/service.py; delivery/guardian.py and conflict-policy memory are directly relevant to delivery checks. core/orchestrator.py performs delivery orchestration, a reasonable new context path. Target-only context precision falls only because that path is added.

- Fixed gold: `src/orqalis/git/service.py`.
- Current index order: `.orqalis/memory/records/MEM-20260926-0004.md`, `src/orqalis/delivery/guardian.py`, `src/orqalis/git/service.py`, `src/orqalis/core/orchestrator.py`, `src/orqalis/context/builder.py`.
- Current matched-context order: `src/orqalis/delivery/guardian.py`, `src/orqalis/git/service.py`, `src/orqalis/core/orchestrator.py`.

### documentation: `Skill Registry capabilities permissions provider`

**Accepted measured ranking regression.** The exact doc remains indexed but moves rank 2 to 5, while context retains it rank 2. skills/registry.py, mcp/server.py and domain/capabilities.py implement the named concepts. The query contains no explicit documentation-only hint; task scope is not passed to search. Do not promote a docs-specific prior just to restore this label.

- Fixed gold: `docs/02-agent-and-skill-model.md`.
- Current index order: `.orqalis/memory/records/MEM-20260926-0002.md`, `src/orqalis/skills/registry.py`, `src/orqalis/mcp/server.py`, `src/orqalis/domain/capabilities.py`, `docs/02-agent-and-skill-model.md`.
- Current matched-context order: `src/orqalis/skills/registry.py`, `docs/02-agent-and-skill-model.md`, `src/orqalis/domain/capabilities.py`, `src/orqalis/domain/provider.py`.

### memory: `curated memory proposal provenance freshness`

**Accepted measured recall regression; retain as follow-up case.** docs/03-project-memory.md falls out of index top 5 (baseline rank 3); curated.py remains rank 2 behind its directly relevant durable freshness fact. Newly ahead are context/builder.py stale-ranking logic, indexing/service.py memory indexing and mcp/server.py proposal/revalidation APIs. Context now includes both gold paths versus only curated.py before. This is a real index gold-recall loss but not evidence of lost memory facts, freshness enforcement or authority.

- Fixed gold: `src/orqalis/memory/curated.py`, `docs/03-project-memory.md`.
- Current index order: `.orqalis/memory/records/MEM-20260926-0003.md`, `src/orqalis/memory/curated.py`, `src/orqalis/context/builder.py`, `src/orqalis/indexing/service.py`, `src/orqalis/mcp/server.py`.
- Current matched-context order: `src/orqalis/memory/curated.py`, `docs/03-project-memory.md`.

### unfamiliar: `ProjectGraphEngine resolve symbol imports cache`

**Accept improvement.** ProjectGraphEngine stays first, and new context drops unrelated Git context. Index consumers builder.py/server.py/indexing/service.py use the graph/cache and are sensible additional paths.

- Fixed gold: `src/orqalis/graph/engine.py`.
- Current index order: `src/orqalis/graph/engine.py`, `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `src/orqalis/indexing/service.py`.
- Current matched-context order: `src/orqalis/graph/engine.py`.

### multi-agent: `scheduler ready tasks parallel dependencies`

**Accept with tail noise.** scheduler.py remains first. orchestrator.py coordinates scheduling; builder.py/indexing/service.py expose task history and server.py task APIs. These lower target-only precision but are partial topical matches, not replacement of scheduler.

- Fixed gold: `src/orqalis/core/scheduler.py`.
- Current index order: `src/orqalis/core/scheduler.py`, `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `src/orqalis/core/orchestrator.py`, `src/orqalis/indexing/service.py`.
- Current matched-context order: `src/orqalis/core/scheduler.py`, `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`.

### repair: `RepairPlanner failed criterion repair limit`

**Accept with tail noise.** RepairPlanner definition stays first. orchestrator.py executes repair; vertical_plan.py plans criteria tasks and domain/execution.py represents command results. web/src/types.ts exposes repair/criterion state. filesystem/io.py is a weak generic failure/limit match. No target rank or recall loss.

- Fixed gold: `src/orqalis/core/repair.py`.
- Current index order: `src/orqalis/core/repair.py`, `web/src/types.ts`, `src/orqalis/domain/execution.py`, `src/orqalis/core/orchestrator.py`, `src/orqalis/persistence/filesystem/io.py`.
- Current matched-context order: `src/orqalis/core/repair.py`, `src/orqalis/core/vertical_plan.py`, `src/orqalis/domain/execution.py`, `web/src/types.ts`, `src/orqalis/core/orchestrator.py`.

### security: `ChangeGuardian test modification secret scope`

**Accept improvement with tail noise.** ChangeGuardian becomes first in context (was fifth), remains first in index. curated.py secret screening and vertical_plan.py scope are genuinely adjacent; graph/engine.py and web/src/types.ts are weaker scope/test terms. No new authorization bypass is inferred from retrieval ranking.

- Fixed gold: `src/orqalis/delivery/guardian.py`.
- Current index order: `src/orqalis/delivery/guardian.py`, `src/orqalis/memory/curated.py`, `src/orqalis/graph/engine.py`, `src/orqalis/core/vertical_plan.py`, `web/src/types.ts`.
- Current matched-context order: `src/orqalis/delivery/guardian.py`, `src/orqalis/graph/engine.py`, `src/orqalis/memory/curated.py`, `src/orqalis/core/vertical_plan.py`.

### resume: `recover interrupted tool invocation task attempt`

**Accept improvement.** orchestrator.py is newly in index top 5, behind an explicit interrupted-tool recovery memory. domain/execution.py and domain/task.py are directly involved in task attempts; context is unchanged. Indexing/service.py is a weaker task-history match.

- Fixed gold: `src/orqalis/core/orchestrator.py`.
- Current index order: `.orqalis/memory/records/MEM-20260926-0001.md`, `src/orqalis/core/orchestrator.py`, `src/orqalis/domain/execution.py`, `src/orqalis/domain/task.py`, `src/orqalis/indexing/service.py`.
- Current matched-context order: `src/orqalis/domain/execution.py`, `src/orqalis/core/orchestrator.py`, `src/orqalis/domain/task.py`.

### probe-tokenize: `_tokenize`

**Accept exact-symbol preservation.** Only indexing/service.py is returned by both channels in both revisions.

- Fixed gold: `src/orqalis/indexing/service.py`.
- Current index order: `src/orqalis/indexing/service.py`.
- Current matched-context order: `src/orqalis/indexing/service.py`.

### probe-camel: `ProjectContextBuilder`

**Accept definition-first plus caller/docs.** context/builder.py remains first. mcp/server.py imports/calls ProjectContextBuilder; docs/03-project-memory.md explains its Context Pack. These are useful usage/documentation paths for a broad search, though they reduce single-target precision.

- Fixed gold: `src/orqalis/context/builder.py`.
- Current index order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`.
- Current matched-context order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`.

### probe-natural-symbol: `project context builder`

**Accept improvement.** Natural words now find the same definition first with mcp/server.py as a direct user; unrelated memory records drop from index. Context is unchanged.

- Fixed gold: `src/orqalis/context/builder.py`.
- Current index order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`.
- Current matched-context order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`.

### probe-snake: `source_hashes`

**Accept exact definition with expansion noise.** curated.py source_hashes remains first after the occurrence-category fix. mcp/server.py calls it and freshness memory explains it. graph/engine.py/domain/execution.py/git/service.py arise from split source/hash/path words; those are weaker than an exact function lookup, but do not outrank the definition. Strict exact-symbol access is available separately.

- Fixed gold: `src/orqalis/memory/curated.py`.
- Current index order: `src/orqalis/memory/curated.py`, `src/orqalis/mcp/server.py`, `.orqalis/memory/records/MEM-20260926-0003.md`, `src/orqalis/graph/engine.py`, `src/orqalis/domain/execution.py`.
- Current matched-context order: `src/orqalis/memory/curated.py`, `src/orqalis/graph/engine.py`, `src/orqalis/domain/execution.py`, `src/orqalis/git/service.py`.

### probe-natural-snake: `source hashes`

**Accept improvement.** Natural source hashes now finds curated.py first in index where baseline omitted it. The same generic source/hash tail as the exact-snake query is expected from component-term expansion; preserve this case when evaluating any later exact-token preference.

- Fixed gold: `src/orqalis/memory/curated.py`.
- Current index order: `src/orqalis/memory/curated.py`, `src/orqalis/mcp/server.py`, `.orqalis/memory/records/MEM-20260926-0003.md`, `src/orqalis/graph/engine.py`, `src/orqalis/domain/execution.py`.
- Current matched-context order: `src/orqalis/memory/curated.py`, `src/orqalis/graph/engine.py`, `src/orqalis/domain/execution.py`, `src/orqalis/git/service.py`.

### probe-routing: `implementation_capabilities`

**Accept definition-first plus component matches.** vertical_plan.py implementation_capabilities remains first. domain/capabilities.py supplies vocabulary/contracts and mcp/server.py exposes planning capabilities. This lowers target-only precision without losing the exact definition.

- Fixed gold: `src/orqalis/core/vertical_plan.py`.
- Current index order: `src/orqalis/core/vertical_plan.py`, `src/orqalis/domain/capabilities.py`, `src/orqalis/mcp/server.py`.
- Current matched-context order: `src/orqalis/core/vertical_plan.py`, `src/orqalis/domain/capabilities.py`, `src/orqalis/mcp/server.py`.

### probe-scoped-routing: `implementation capabilities`

**Accept improvement.** Natural implementation capabilities newly retrieves vertical_plan.py first rather than only capabilities.py/server.py. Context retains the same three paths.

- Fixed gold: `src/orqalis/core/vertical_plan.py`.
- Current index order: `src/orqalis/core/vertical_plan.py`, `src/orqalis/domain/capabilities.py`, `src/orqalis/mcp/server.py`.
- Current matched-context order: `src/orqalis/core/vertical_plan.py`, `src/orqalis/domain/capabilities.py`, `src/orqalis/mcp/server.py`.

### probe-events: `Event event_type correlation_id`

**Accept definition-first; noisy context tail.** domain/events.py Event remains first. web/src/types.ts contains event_type and MetricsView consumes event telemetry; agents/service.py and delivery/guardian.py emit events. curated.py and graph/engine.py in context are weak generic type/id matches. No displaced exact Event definition; noise remains measurable.

- Fixed gold: `src/orqalis/domain/events.py`.
- Current index order: `src/orqalis/domain/events.py`, `web/src/types.ts`, `web/src/MetricsView.tsx`, `src/orqalis/agents/service.py`, `src/orqalis/delivery/guardian.py`.
- Current matched-context order: `src/orqalis/domain/events.py`, `src/orqalis/memory/curated.py`, `src/orqalis/graph/engine.py`, `web/src/types.ts`.

### probe-test-command: `ApprovedCommand timeout_seconds`

**Accept definition-first plus actual consumer.** domain/execution.py ApprovedCommand remains first; execution/commands.py consumes ApprovedCommand and enforces timeout_seconds. agents/service.py/evaluator.py also handle timeout but analytics.py seconds overlap is weaker. Context adds only the direct commands consumer.

- Fixed gold: `src/orqalis/domain/execution.py`.
- Current index order: `src/orqalis/domain/execution.py`, `src/orqalis/execution/commands.py`, `src/orqalis/observability/analytics.py`, `src/orqalis/agents/service.py`, `src/orqalis/execution/evaluator.py`.
- Current matched-context order: `src/orqalis/domain/execution.py`, `src/orqalis/execution/commands.py`.

### probe-usage: `ProviderUsage input_tokens output_tokens`

**Accept definition-first plus telemetry.** domain/provider.py ProviderUsage remains first; agents/service.py records provider usage and web/src/types.ts has input/output-token fields. indexing/service.py/context/builder.py are weaker input/token-related matches. Context remains the one exact definition path.

- Fixed gold: `src/orqalis/domain/provider.py`.
- Current index order: `src/orqalis/domain/provider.py`, `src/orqalis/agents/service.py`, `web/src/types.ts`, `src/orqalis/indexing/service.py`, `src/orqalis/context/builder.py`.
- Current matched-context order: `src/orqalis/domain/provider.py`.

### probe-permissions: `PermissionProfile allowed_tools`

**Accept definition-first plus actual usage.** domain/capabilities.py PermissionProfile remains first. MetricsView.tsx displays actor.session.allowed_tools; it is a real usage rather than the permissions definition. worker.py and skills/registry.py apply tool permissions, and the durable permissions fact is directly relevant. The prior occurrence-before-definition problem is corrected.

- Fixed gold: `src/orqalis/domain/capabilities.py`.
- Current index order: `src/orqalis/domain/capabilities.py`, `web/src/MetricsView.tsx`, `.orqalis/memory/records/MEM-20260926-0002.md`, `src/orqalis/execution/worker.py`.
- Current matched-context order: `src/orqalis/domain/capabilities.py`, `src/orqalis/execution/worker.py`, `src/orqalis/skills/registry.py`.

### probe-restore: `restore interrupted changes safely`

**Existing semantic recall limitation; no new P1.** Neither revision finds orchestrator.py for this paraphrase. The relevant repair/recovery vocabulary is not necessarily present in names/path terms; a full semantic or documentation-body search is not implemented. Some returned memory/IO paths concern interrupted writes rather than interrupted task execution. Keep the miss visible; do not add a one-query synonym rule.

- Fixed gold: `src/orqalis/core/orchestrator.py`.
- Current index order: `src/orqalis/delivery/guardian.py`, `.orqalis/memory/records/MEM-20260926-0003.md`, `.orqalis/memory/records/MEM-20260926-0001.md`.
- Current matched-context order: `src/orqalis/memory/curated.py`, `src/orqalis/persistence/filesystem/io.py`.

### probe-hub: `run project context task`

**Broad ambiguous query; existing miss.** Neither revision finds the labeled orchestrator.py. Query run project context task naturally matches builder.py, MCP and task types; orchestrator is not named and many project components use these words. The sparse single-target label cannot establish that all returned paths are irrelevant. Keep the unchanged miss.

- Fixed gold: `src/orqalis/core/orchestrator.py`.
- Current index order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `src/orqalis/indexing/service.py`, `.orqalis/memory/records/MEM-20260926-0003.md`, `.orqalis/memory/records/MEM-20260926-0002.md`.
- Current matched-context order: `src/orqalis/context/builder.py`, `src/orqalis/mcp/server.py`, `docs/03-project-memory.md`, `src/orqalis/domain/task.py`.

### probe-no-match: `zebracat astrophotography glacier`

**Accept explicit negative/orientation distinction.** Index returns no paths. Current matched-context paths are empty; orientation-only graph paths remain present and labeled. This is not an empty serialized context or zero returned bytes.

- Fixed gold: (negative case).
- Current index order: (none).
- Current matched-context order: (none).

### probe-substring-negative: `tification`

**Accept explicit negative/orientation distinction.** The non-word tification returns no index or matched-context paths. Centrality orientation remains labeled separately. No substring match is inferred merely from notification or similar tokens.

- Fixed gold: (negative case).
- Current index order: (none).
- Current matched-context order: (none).

## Evidence-backed follow-up boundaries

- **KEEP** definition/occurrence separation and current fixed labels. Exact-source-hash and permission declarations ranking first is the regression witness, rather than a globally tuned numeric penalty.
- **DEFER** broad scoring changes. The remaining exact-identifier tail noise is visible but does not displace the definition in this corpus. A new held-out set should specify whether the user requests an exact declaration, usages or broad concepts before judging a separate mode.
- **DEFER** section-aware Markdown search as a distinct feature. The memory and architecture documents are truly relevant; indexing only file metadata and limited summaries explains missing sections. Do not claim full-text documentation coverage from their presence in the graph.
- **KEEP visible** paraphrase and broad-hub misses. A lookup lacking lexical overlap is not solved by syntax parsing or graph provenance. No hardcoded synonyms, query-label routing or project-specific boosts are recommended.
- **REJECT** modifying gold paths after inspecting these results merely to improve metrics. If future exhaustive judgments are collected, version them as a separate dataset and retain this comparison.

This review inspected frozen source definitions, direct consumers and docs sections for the disputed paths, as well as all 29 baseline/current path lists. It did not run a live coding agent, infer task completion from recall, re-score the benchmark using new relevance labels, or qualify timings collected during parallel work.

---

## Final-source measured pairs and tradeoffs

Reviewed 2026-09-27 against current production fingerprint
`fece9d668365b0e853d84d6de4ebbe41417179dcf68dc00a293dc95e2a09e8c4`.
The fixed 29-query dataset and immutable v2.0.0 baseline were unchanged. These are
local deterministic fixtures, not autonomous coding-task success or machine-independent
performance claims. Raw order-1 [baseline](../evidence/baseline-quality-final-source-1.json),
[current](../evidence/current-quality-final-source-1.json), and
[comparison](../evidence/quality-comparison-final-source-1.json) are retained separately
from order-2 [baseline](../evidence/baseline-quality-final-source-2.json),
[current](../evidence/current-quality-final-source-2.json), and
[comparison](../evidence/quality-comparison-final-source-2.json). Each uses three timing
repeats, passing 86/86 source-bound v3 contracts, and stable source/dataset/helper inputs.
Order 1 measured baseline then current; order 2 measured current then baseline.

Both comparisons remain **REVIEW**, with zero failed hard invariants and the same exact
30 `(case, channel, metric)` losses. There are 25 labeled-target precision losses and
five other ranking losses: documentation index MRR/nDCG, memory index recall/nDCG, and
refactor index MRR. The per-case review above explains each and retains the real top-five memory-document miss. No labels or raw statuses were changed.
Mean positive-case index recall is 72.22% baseline versus 87.04% current; context recall
is 85.19% versus 87.04%. This bounded evidence supports the retrieval improvement,
while keeping the case-level tradeoffs open to future corpus expansion. It does not show
a new P1 correctness regression in the reviewed cases.

| Measure | Order 1 current/baseline | Order 2 current/baseline | Assessment |
| --- | ---: | ---: | --- |
| CLI startup median | 1.39x | 1.15x | Slower in both orders; three samples are too few for a stable tail claim. |
| MCP startup-to-response median | 1.30x | 1.23x | Slower in both orders; added surfaces have a measurable small-fixture cost. |
| Cold graph rebuild | 1.35x | 0.94x | Direction changes with order; no speed claim. |
| Unchanged graph refresh | 0.98x | 0.73x | No regression shown. |
| One-file graph refresh | 1.02x | 0.89x | No regression shown. |
| Graph disk bytes | 1.99x | 1.99x | More graph facts: 2,297 nodes versus 966; bytes per node fall about 16%. |
| Index disk bytes | 2.75x | 2.75x | Real persistent storage increase on this small corpus. |
| Total project-store bytes | 2.39x | 2.39x | Still below 10 MB on the fixed 30-path fixture; larger repos need separate evaluation. |
| One context-query Python allocation | 1.92x | 1.92x | About 13.5 MB versus 7.1 MB; excludes native/process RSS. |

The comparator records these increases and applies its documented timing/allocation
investigation budgets; neither pair crossed them. This is an explicit cost of added
syntax, graph and retrieval evidence, not a claim of zero overhead. On the separate
[one-CPU/256-MiB constrained fixture](../evidence/current-constrained-final-source-1.json),
current peak process commit was 49.6 MB versus 46.6 MB
[baseline](../evidence/baseline-constrained-final-source-1.json); both passed.

The [execution baseline](../evidence/baseline-execution-final-source-1.json) and
[current](../evidence/current-execution-final-source-1.json) each passed three full
parallel-read/tool/repair/review fixture repetitions. Median execution time was 70.0 s
versus 68.6 s; this is comparable behavior, not a speed guarantee. The
[UI baseline](../evidence/baseline-ui-final-source-1.json) and
[current](../evidence/current-ui-final-source-1.json) each passed six correlated
API/WebSocket/DOM transitions, with median request-to-DOM time 1.01 s versus 0.78 s.
[Memory](../evidence/current-memory-final-source-1.json) passed 45 exact-answer,
response-cap and history-retention samples; its selective-workflow comparison is within
the current version and cannot establish released-baseline memory speed.

**Disposition for this fixture:** no confirmed P0/P1 regression; 30 retrieval metric
losses, startup cost and storage/allocation cost remain transparently recorded.
The first iteration is not automatically release sign-off. A second complete audit loop,
all acceptance criteria, final package/docs identity and unsupported platform limits
must still be checked. Do not change the frozen corpus to hide these tradeoffs.

## 1,001-row history and bounded-graph probe

The [current-source scale evidence](../evidence/history-graph-scale-final-source-1.json)
uses 1,001 valid Task Capsules in an isolated Windows project and a synthetic
1,201-node / 1,200-edge star graph. All history IDs appeared exactly once in
11 pages of at most 100, in full-list order. First/median/maximum page reads
were 0.63/0.69/0.76 s. A full-list read took 1.84 s and serialized to
336 KB; the largest page serialized to 34 KB. The archived baseline's
full-list read on the same fixture took 2.12 s in one sample. These are
single-machine observations, not a stable speedup claim. Valid capsule
seeding took 230 s and is reported separately from read latency.

The bounded graph query returned 25 nodes and 8.7 KB with explicit
truncation, compared with 408 KB for the whole graph; a two-node shortest
path was found. This verifies bounded response size and correctness for
this shape, not graph-wide cursor pagination. History `page()` rebuilds
the index and re-reads all compact summaries for each page, so its response
size is bounded while its work remains proportional to the history size.
The roughly 0.7 s page latency warrants a larger-repo profile next
session. No source optimization or new P1 classification was made from
one scale point.


## Subsequent optimization comparison, 2026-10-02

The [optimization comparison](../evidence/optimization-quality-comparison-final.json)
passed against the frozen pre-optimization enhancement candidate: zero new per-case
metric losses, zero failed hard invariants, identical 87.04% index/context recall and
mean context response bytes. This does not close the 30 earlier losses against released
v2.0.0. [Methods and current cost table](../../../benchmarks/README.md#optimization-pass-2026-10-02)
are consolidated in the benchmark guide: CLI startup and derived storage improved;
Python peak allocation was nearly unchanged and the MCP/unchanged-graph timing batches
were slower. History timing remains inconclusive, with retained large outliers on both
sources in diagnostics. There is no claim of zero drawbacks or release sign-off.
