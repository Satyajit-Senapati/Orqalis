# Capability catalog

One decision per capability; [matrix](OSS_BENCHMARK_MATRIX.md) and [backlog](ENHANCEMENT_BACKLOG.md) are authoritative for selection and progress.
The user accepted cold graph-rebuild cost for2.1.0 and deferred optimization to PERF-COLD-01. All23 implementation statuses remain pending bounded per-ID evaluation; local whole qualification with an exception is separate from full capability convergence.

No upstream source has been copied. Referenced implementation patterns, exact revisions, evidence limits and licensing are recorded in the linked research sections.

## O01 - Orchestration: KEEP

Reference: **LangGraph; Microsoft Agent Framework; CrewAI**. Observed pattern: Explicit checkpoints and resumable executor state.

Current Orqalis: Atomic Task Capsule snapshots, journal recovery and controller leases. Baseline gap/risk: No replacement justified.

Disposition: Retain filesystem authority. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## O02 - Orchestration: KEEP

Reference: **Temporal; LangGraph**. Observed pattern: Separate durable workflow progress from side effects.

Current Orqalis: Request hashes, effect receipts and explicit uncertain-outcome recovery. Baseline gap/risk: No exactly-once guarantee.

Disposition: Keep bounded explicit recovery and completed-observation reuse. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## O03 - Coordination: KEEP

Reference: **Agent Framework; CrewAI; LangGraph**. Observed pattern: Typed dependencies and human checkpoints.

Current Orqalis: Typed DAG, parallel readers, one writer, fingerprinted approvals. Baseline gap/risk: No measured need for unrestricted peer routing.

Disposition: Retain deterministic ownership and scoped result handoffs. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## O04 - Recovery: ADD

Reference: **Temporal; LangGraph; Agent Framework**. Observed pattern: Restart at effect/checkpoint boundaries.

Current Orqalis: Eight real process-death barriers and owned cancellation polling that cannot block the event loop; worker/poll drain retains lease ownership. Baseline gap/risk: Process death skips finally blocks.

Disposition: Add deterministic child-process death/restart barriers across all phases. Value: High; scope: Medium.
Dependency implications: O02; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## O05 - Coordination: DEFER

Reference: **Agent Framework; OpenHands**. Observed pattern: Independent workstream isolation and typed mailboxes.

Current Orqalis: One worktree and one writer per run. Baseline gap/risk: Potential throughput opportunity, no workload proof.

Disposition: Defer parallel writers and general mailbox until conflict/throughput evaluation. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## O06 - Core architecture: REJECT

Reference: **Temporal; LangGraph; CrewAI**. Observed pattern: General distributed workflow frameworks.

Current Orqalis: One local Orchestrator and project store. Baseline gap/risk: Would duplicate state authority and add infrastructure.

Disposition: Reject wholesale framework/database replacement. Value: Negative; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Mixed permissive.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## X01 - Execution: ADAPT

Reference: **OpenHands SDK; SWE-agent; E2B**. Observed pattern: Explicit sandbox/session ownership and interruption.

Current Orqalis: Durable container receipts, exact daemon/label/ID ownership and fail-closed reconciliation. Baseline gap/risk: Orphan uncertainty and ignored cleanup failure.

Disposition: Persist exact ownership, inspect labels, reconcile before reuse/recovery; fail closed. Value: High; scope: Medium.
Dependency implications: O02; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## X02 - Execution: KEEP

Reference: **OpenHands; SWE-agent**. Observed pattern: Action/observation boundary and constrained runtime.

Current Orqalis: Exact approved argv, scrubbed env, time/output limits. Baseline gap/risk: No replacement justified.

Disposition: Retain typed tools, workspace scope and optional isolation. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## X03 - Execution: DEFER

Reference: **E2B; OpenHands; historical Daytona**. Observed pattern: Snapshots, remote lifecycle and capabilities.

Current Orqalis: No cloud sandbox adapter. Baseline gap/risk: Useful for specialized deployments, adds egress/cost dependencies.

Disposition: Defer remote adapters and snapshots; Daytona core is no longer maintained. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT; Daytona mixed.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## S01 - Change Guardian: ADAPT

Reference: **Superpowers; SWE-agent; Semgrep concepts**. Observed pattern: Verification integrity before accepting implementation.

Current Orqalis: Conservative Python test assertion/skip/parse integrity checks with exact-hash review exceptions. Baseline gap/risk: Test weakening can pass the current deterministic guard.

Disposition: Detect conservative AST/diff signals; exact reviewed hash-bound exception. Value: High; scope: Medium.
Dependency implications: O03; no reference framework is a runtime requirement. License/reuse boundary: Original implementation; no Semgrep rules.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## S02 - Change Guardian: ADAPT

Reference: **OpenHands runtime; bounded resource patterns**. Observed pattern: Bound output/resources before allocation.

Current Orqalis: Pre-allocation size checks and bounded changed-file reads. Baseline gap/risk: Oversized changed file can exhaust controller memory.

Disposition: Stat and bounded reads before secret/diff analysis. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Original implementation.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## S03 - Security: DEFER

Reference: **Gitleaks; Semgrep**. Observed pattern: Broader secret and static-rule coverage.

Current Orqalis: Native redaction, path/root/command/approval checks. Baseline gap/risk: Additional scanner updates and license burden.

Disposition: Defer optional evidence-only scanner adapters until native reliability closes. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT Gitleaks; LGPL/rules-specific Semgrep.

[Implementation evidence and limitations](research/RUNTIME_RESEARCH.md). Status: **DECIDED**.

## G01 - Graph: ADAPT

Reference: **Graphify**. Observed pattern: Conservative resolution with evidence categories.

Current Orqalis: Extracted source occurrences separated from inferred Python binding candidates. Baseline gap/risk: Unknown receiver can bind to unrelated unique name.

Disposition: Separate extracted occurrences from inferred target bindings; invalidate cache. Value: High; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache-2.0 + retained MIT notices; concepts only.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## G02 - Graph: ADD

Reference: **Tree-sitter; Graphify; Aider**. Observed pattern: Language grammar capture with source locations.

Current Orqalis: Python AST plus bounded JS/TS/TSX Tree-sitter syntax facts and exact UTF-8 spans. Baseline gap/risk: Own frontend lacks symbol-level intelligence.

Disposition: Add native abstraction for pinned JS/TS/TSX grammars with declared limits. Value: High; scope: Medium.
Dependency implications: G01; no reference framework is a runtime requirement. License/reuse boundary: MIT binding and both grammar notices verified; locked dependency versions.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## G03 - Graph: KEEP

Reference: **Graphify; Tree-sitter**. Observed pattern: Versioned extraction cache.

Current Orqalis: Content hashes, parser identity, branch/dirty/delete refresh. Baseline gap/risk: No core replacement; total read/assembly cost needs measurement.

Disposition: Keep file-granularity cache and report reads separately from parsing. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## G04 - Graph navigation: ADD

Reference: **Graphify; Serena**. Observed pattern: Selective directed navigation with witnesses.

Current Orqalis: Bounded evidence-preserving impact and shortest-path queries in SDK/CLI/MCP. Baseline gap/risk: Baseline lacked impact/shortest-path surface.

Disposition: Retain Orqalis-owned bounded traversal in SDK/CLI/MCP. Value: High; scope: Low.
Dependency implications: G01; no reference framework is a runtime requirement. License/reuse boundary: Concepts only.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## G05 - Source tools: ADD

Reference: **Serena/SolidLSP; multilspy**. Observed pattern: Qualified symbolic access instead of guessed line slices.

Current Orqalis: Bounded hash-verified symbol discovery, outlines, exact bodies and static references. Baseline gap/risk: Useful source cannot be read precisely through graph contract.

Disposition: Add bounded native outline/body/reference reads with source-hash checks. Value: High; scope: Medium.
Dependency implications: G01; G02; no reference framework is a runtime requirement. License/reuse boundary: GPL app not reused; MIT library concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## G06 - Source tools: DEFER

Reference: **Serena; multilspy; SCIP**. Observed pattern: Semantic bindings and symbol replacement.

Current Orqalis: No LSP edit or SCIP ingestion service. Baseline gap/risk: Large dependency/runtime surface without demonstrated demand.

Disposition: Defer LSP/SCIP and symbol writes; preserve read-only abstraction. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: GPL/MIT/Apache per component.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## G07 - Graph: DEFER

Reference: **Graphify**. Observed pattern: Communities and heterogeneous inferred relations.

Current Orqalis: Shallow docs/config nodes, no communities. Baseline gap/risk: Benefit unmeasured; inference can invent architecture.

Disposition: Defer clustering/multimodal/model extraction. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## G08 - Graph: REJECT

Reference: **Graphify; Graphiti**. Observed pattern: Rich semantic graph runtime.

Current Orqalis: No mandatory graph database or inference. Baseline gap/risk: Conflicts with simple offline authority.

Disposition: Reject mandatory graph/model service. Value: Negative; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## R01 - Retrieval: ADAPT

Reference: **Aider; Agent-Memory**. Observed pattern: Identifier and ranked lexical signals.

Current Orqalis: Shared identifier-aware terms and lexical-v3 indexes; references are typed separately and definitions win equal-score ties. Baseline gap/risk: Baseline inconsistent tokenization misses identifier parts.

Disposition: Use shared whole-word/snake/camel terms; invalidate lexical index version. Value: High; scope: Low.
Dependency implications: E01; no reference framework is a runtime requirement. License/reuse boundary: Original implementation.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## R02 - Retrieval: ADAPT

Reference: **Aider**. Observed pattern: Personalized ranking and compact maps.

Current Orqalis: Bounded context with match reasons, explicit orientation, and declaration-first selection excluding call occurrences as primary seeds. Baseline gap/risk: No evidence yet that changing ranker beats existing one.

Disposition: Measure held-out gold and negative context; change only on demonstrated benefit. Value: High; scope: Medium.
Dependency implications: E01; no reference framework is a runtime requirement. License/reuse boundary: Apache concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## R03 - Retrieval: DEFER

Reference: **Agent-Memory; Graphiti; Mem0**. Observed pattern: BM25, embedding and reciprocal-rank fusion.

Current Orqalis: No mandatory BM25/vector fusion service. Baseline gap/risk: Potential zero-overlap recall; no accepted workload justifies runtime.

Disposition: Defer new retrieval dependency and fusion pending labeled evidence. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT per component.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## M01 - Project Memory: KEEP

Reference: **Serena; MCP memory; Agent-Memory**. Observed pattern: Human-readable durable knowledge and cross-assistant access.

Current Orqalis: Project-local records, source hashes, staged review and secret checks. Baseline gap/risk: No store replacement justified.

Disposition: Keep distinct graph/memory/history authorities and scoped proposals. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Concepts only.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## M02 - Project Memory: ADAPT

Reference: **Graphiti; Mem0; coding-agent-memory-mcp**. Observed pattern: Explicit replacement/history without deleting evidence.

Current Orqalis: Immutable reviewed successors with atomic canonical lifecycle transitions and historical reads. Baseline gap/risk: Contradictory predecessors remain eligible; stale proposal race.

Disposition: Reviewed digest-bound supersession with atomic lifecycle metadata. Value: High; scope: Medium.
Dependency implications: M01; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## M03 - Project Memory: ADAPT

Reference: **Serena; current Letta; MCP memory**. Observed pattern: Metadata/core orientation then selected detail.

Current Orqalis: Bounded memory previews/body pages, stable explicit references and provider context previews. Baseline gap/risk: Large useful records may be omitted by context budget.

Disposition: Bounded excerpts/discovery and explicit ID references; fetch detail on demand. Value: High; scope: Medium.
Dependency implications: M02; E01; no reference framework is a runtime requirement. License/reuse boundary: GPL concept only; Apache/MIT mixed refs.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## M04 - Project Memory: ADD

Reference: **Agent-Memory; Serena**. Observed pattern: Explicit corruption/drift diagnostics.

Current Orqalis: Bounded memory schema/lifecycle/reference integrity report through CLI/SDK/MCP. Baseline gap/risk: New lifecycle and references require inspectable integrity.

Disposition: Shared integrity report and CLI/MCP projection. Value: High; scope: Medium.
Dependency implications: M02; M03; no reference framework is a runtime requirement. License/reuse boundary: Original implementation.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## M05 - Project Memory: DEFER

Reference: **Serena; Graphiti; Letta**. Observed pattern: Taxonomy, read-only modes, valid-time queries.

Current Orqalis: No tag taxonomy, protected mutable records or bitemporal query. Baseline gap/risk: No supported task requires full semantics.

Disposition: Defer extra taxonomy/protection modes/bitemporal inference. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: GPL/Apache concepts.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## M06 - Project Memory: REJECT

Reference: **Mem0; Graphiti; Letta; MCP reference memory**. Observed pattern: Alternative complete memory/harness systems.

Current Orqalis: Repo store remains canonical. Baseline gap/risk: Would split authority or auto-persist uncontrolled conversation.

Disposition: Reject replacement SDK/store, silent deletion and fuzzy rewrite as authority. Value: Negative; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Mixed.

[Implementation evidence and limitations](research/KNOWLEDGE_RESEARCH.md). Status: **DECIDED**.

## H01 - Skills: ADAPT

Reference: **Agent Skills; Codex; Awesome Copilot**. Observed pattern: Portable metadata and progressive activation.

Current Orqalis: Trusted-root portable SKILL.md adapter, bounded resource reads and content-pinned activation. Baseline gap/risk: Baseline TOML-only; native body/resource support added.

Disposition: Retain explicit trusted roots, hashes and tool requirements as constraints. Value: High; scope: Medium.
Dependency implications: E01; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT; per-skill notices.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## H02 - Skills: ADD

Reference: **Superpowers; Promptfoo; Codex**. Observed pattern: Positive/negative task tests and budgeted activation.

Current Orqalis: Source-isolated routing, typed-roundtrip, content-pin and progressive-byte measurements. Baseline gap/risk: No stable routing confusion matrix or disclosure measurements.

Disposition: Versioned routing/portability evaluation; model quality explicitly unknown without paid runs. Value: High; scope: Medium.
Dependency implications: E01; H01; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## H03 - Skills: DEFER

Reference: **Agent Skills; Claude SDK**. Observed pattern: Compatibility and explicit provenance fields.

Current Orqalis: Metadata provenance is partly discarded; resources exposed over MCP. Baseline gap/risk: Useful polish; bundled internal skills self-contained.

Disposition: Defer richer provenance/environment validation and provider-worker resource execution. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Per-component.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## H04 - Skills: KEEP

Reference: **Superpowers; Awesome Copilot**. Observed pattern: Curated packages and validation.

Current Orqalis: Explicit trusted roots, pinned versions and own registry. Baseline gap/risk: No need for automatic marketplace dependency.

Disposition: Keep explicit installation boundary. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache/per-skill.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## H05 - Hooks: DEFER

Reference: **Claude hooks; Codex hooks**. Observed pattern: Typed lifecycle callbacks.

Current Orqalis: Policy/telemetry already have explicit service checkpoints. Baseline gap/risk: Generic executable hooks risk hidden orchestration.

Disposition: Defer arbitrary external hooks until one concrete supported host use case. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Host-specific; concepts only.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## H06 - Skills: REJECT

Reference: **Anthropic skills; Awesome Copilot**. Observed pattern: Large reusable catalogs.

Current Orqalis: No automatic bulk installation. Baseline gap/risk: License/policy drift and irrelevant context.

Disposition: Reject bulk skill/plugin installation and implicit execution of bundled scripts. Value: Negative; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Per-skill; some source-available.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## I01 - Assistant integrations: ADAPT

Reference: **Codex; Claude Code; Copilot; OpenCode; Goose**. Observed pattern: Host-specific MCP configuration and lifecycle.

Current Orqalis: Documented root/policy-bound MCP assistant configuration and generic stdio contracts. Baseline gap/risk: Generic MCP evidence must not imply native-host certification.

Disposition: Document and evaluate supported config/root/discovery/continuation/error contract. Value: High; scope: Medium.
Dependency implications: I02; H02; no reference framework is a runtime requirement. License/reuse boundary: Host licenses separate from SDKs.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## I02 - MCP: ADD

Reference: **MCP SDK; OpenCode; Goose**. Observed pattern: Assistant can continue interrupted project work.

Current Orqalis: MCP pause/resume/cancel/recovery through existing application policies and leases. Baseline gap/risk: Missing pause/resume/cancel/recover interface.

Disposition: Expose existing services behind server work policy and root binding. Value: High; scope: Low.
Dependency implications: O04; X01; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## I03 - MCP: ADAPT

Reference: **MCP SDK; GitHub MCP server**. Observed pattern: Bounded discovery and continuation.

Current Orqalis: Bounded task-history responses with root/revision-bound page cursors. Baseline gap/risk: Old history unreachable; large payloads costly.

Disposition: Add root/revision-bound pagination and bounded graph discovery while preserving old tools. Value: High; scope: Medium.
Dependency implications: G04; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## I04 - Native harness: DEFER

Reference: **Codex; Claude SDK; OpenCode**. Observed pattern: Native host tools/session lifecycle.

Current Orqalis: ExternalCLIProvider transport abstraction only. Baseline gap/risk: Host policy mapping not equivalent to Orqalis enforcement.

Disposition: Defer native subprocess workers; supported MCP pathway closes current interoperability need. Value: Medium; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Apache/MIT SDK; Claude Code commercial.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## I05 - Integrations: DEFER

Reference: **GitHub MCP server**. Observed pattern: Scoped remote repository operations.

Current Orqalis: No external issue/PR writes. Baseline gap/risk: Useful optional workflow, no current requested remote destination.

Disposition: Defer connector ingestion/PR delivery until scoped token/idempotency contract. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT.

[Implementation evidence and limitations](../OPEN_SOURCE_REVIEW.md). Status: **DECIDED**.

## T01 - Telemetry: ADAPT

Reference: **OpenHands; OTel; Langfuse**. Observed pattern: Navigable trace parentage and safe attributes.

Current Orqalis: Persisted run/phase/attempt/agent/model/tool ancestry and safe span correlation. Baseline gap/risk: Declared trace fields not assigned; UI separates call lists.

Disposition: Project existing parent IDs into local trace hierarchy and allowlisted spans. Value: High; scope: Medium.
Dependency implications: I02; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache; Langfuse component exclusions.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## T02 - Control Center: ADAPT

Reference: **OpenHands; Langfuse**. Observed pattern: Critical path and causal execution inspection.

Current Orqalis: Keyboard-accessible local trace ancestry and measured critical-path navigation. Baseline gap/risk: Timeline omits model/tool intervals and critical path cues.

Disposition: Consume backend projections; test actual multi-agent/repair snapshots. Value: High; scope: Medium.
Dependency implications: T01; no reference framework is a runtime requirement. License/reuse boundary: Concepts only; no visual clone.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## T03 - Telemetry: ADAPT

Reference: **Langfuse; AgentOps**. Observed pattern: Outcome, latency and usage breakdowns.

Current Orqalis: Per-provider/model outcome, latency and usage coverage in API and Control Center. Baseline gap/risk: Baseline lacked provider grouping.

Disposition: Keep nearest-rank p50/p95 and coverage counts sourced from invocations. Value: High; scope: Low.
Dependency implications: E01; no reference framework is a runtime requirement. License/reuse boundary: MIT/concepts; no hosted SDK.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **IMPLEMENTED_PENDING_EVAL**.

## T04 - Control Center: KEEP

Reference: **OpenHands; Langflow**. Observed pattern: Inspect real runtime and graph.

Current Orqalis: React projects backend state; existing events/reconnect/run comparison. Baseline gap/risk: No evidence justifies replacing UI authority.

Disposition: Keep backend-derived state and avoid visual workflow authoring engine. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## T05 - Observability: DEFER

Reference: **Langfuse; AgentOps; OpenTelemetry**. Observed pattern: Optional external tracing.

Current Orqalis: Local telemetry is sufficient for default operation. Baseline gap/risk: Network sinks require configuration and privacy policy.

Disposition: Defer OTLP/hosted exporters. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache/component-specific.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## T06 - Observability: REJECT

Reference: **Langfuse; AgentOps**. Observed pattern: Managed trace infrastructure.

Current Orqalis: No hosted observability dependency. Baseline gap/risk: Would violate default local-first behavior.

Disposition: Reject mandatory hosted service or private reasoning storage. Value: Negative; scope: High.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: Component-specific.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md). Status: **DECIDED**.

## E01 - Evaluation: ADD

Reference: **Promptfoo; DeepEval; Agent-Memory**. Observed pattern: Versioned test inputs, deterministic assertions and comparisons.

Current Orqalis: Frozen engineering/held-out query corpus, isolated contract runner and strict raw-report comparator. Baseline gap/risk: Improvement claims lack reproducible baseline.

Disposition: Source-isolated 14-category corpus plus held-out retrieval/routing/contract suite. Value: High; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research). Status: **IMPLEMENTED_PENDING_EVAL**.

## E02 - Acceptance/repair: KEEP

Reference: **Superpowers; SWE-agent**. Observed pattern: Separate specification/quality checks and non-rationalized evidence.

Current Orqalis: Independent reviewer, criterion evidence, exact digest and bounded repair. Baseline gap/risk: No need to replace existing authoritative acceptance.

Disposition: Keep independent review and repair; add weakening/crash fixtures. Value: High; scope: Low.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT concepts.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research). Status: **DECIDED**.

## E03 - Evaluation: DEFER

Reference: **Promptfoo; DeepEval**. Observed pattern: Model judges and red-team generation.

Current Orqalis: No mandatory judge/model calls. Baseline gap/risk: Cost/non-determinism/data egress not needed for native correctness.

Disposition: Defer paid live model quality study; keep a provider-neutral optional future layer. Value: Medium; scope: Medium.
Dependency implications: None; no reference framework is a runtime requirement. License/reuse boundary: MIT/Apache.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research). Status: **DECIDED**.

## E04 - Distribution/performance: ADAPT

Reference: **Existing Orqalis; Tree-sitter/PyYAML dependency audit**. Observed pattern: Portable wheels and reproducible package verification.

Current Orqalis: Pinned dependency notices/advisories, installed wheel smoke and measured startup/footprint pipeline. Baseline gap/risk: New parser/skill dependencies need measured footprint.

Disposition: Verify licenses, wheel availability, startup/bundle/disk and offline contracts. Value: High; scope: Medium.
Dependency implications: G02; H01; E01; no reference framework is a runtime requirement. License/reuse boundary: Dependency-specific.

[Implementation evidence and limitations](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research). Status: **IMPLEMENTED_PENDING_EVAL**.
