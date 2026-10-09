# Harness, integrations, evaluation, and observability research

This combined guide preserves dated harness, evaluation, and the iteration-1 independent audit. For current acceptance and
release status, use the [enhancement status](../ENHANCEMENT_STATUS.md).

Audit date: 2026-09-26. Scope: master-plan sections 8–10, 18–20, 29–32, 60–61.
Baseline: immutable `b8506f7d9c471516fe4b21c9caa735a7a7909af6` (`v2.0.0`), plus the
working-tree portable-skills, graph-query, and provider-metrics changes inspected on this
date. This is an implementation audit and design comparison, not evidence of live native
Codex/Claude/Copilot sessions. No upstream implementation code was copied.

## Upstream refresh - 2026-10-03

[Current refresh disposition](../evidence/release-upstream-refresh-20261003-independent-disposition-v1.json)
records remote HEAD, metadata, exact-HEAD README and root-license checks for all40
linked references across the three research guides. It identifies no new confirmed
accepted P0/P1 gap; all23 accepted implementations remain pending evaluation and13
DEFER decisions remain. Portable format, approval allowlisting and MCP transport
references support the existing boundaries; they do not certify native assistant
sessions or require a locked-SDK migration. Changed upstream code and nested license
payloads were not comprehensively audited. The dated source inspections below remain
historical, and this metadata refresh supplies no candidate qualification credit.

## Evidence and revision ledger

Exact revisions below were resolved with public `git ls-remote ... HEAD` on 2026-09-26.
Pinned raw license files were read. GitHub's unauthenticated API returned HTTP 403 rate
limits, so no new commit-date or maintenance-frequency claim is made. The earlier
`docs/verification/open-source-projects-2026-09-26.json` records repository activity;
repository popularity is not an adoption criterion. A HEAD pin identifies inspected raw
files; separately linked official documentation is a dated live-documentation snapshot.

| Project | Inspected revision | License observed at this revision | Inspected material |
| --- | --- | --- | --- |
| [Agent Skills](https://github.com/agentskills/agentskills) | `69ef37e9424c0a7ea9dd2293b559e43ec8176379` | [Apache-2.0](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/LICENSE) | Official specification; pinned license |
| [Awesome Copilot](https://github.com/github/awesome-copilot) | `6c4d33b9cfca967a28bb2962ef4d55e4a384c88c` | [MIT](https://github.com/github/awesome-copilot/blob/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c/LICENSE) | CONTRIBUTING.md, package.json, license |
| [Superpowers](https://github.com/obra/superpowers) | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` | [MIT](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/LICENSE) | writing-skills; testing-skills-with-subagents.md |
| [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python) | `36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6` | [MIT](https://github.com/anthropics/claude-agent-sdk-python/blob/36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6/LICENSE) | License and official hooks documentation |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | `f1b6589088534632fef92238ee9750951e3c0185` | [MIT](https://github.com/modelcontextprotocol/python-sdk/blob/f1b6589088534632fef92238ee9750951e3c0185/LICENSE) | README, protocol documentation, license |
| [MCP reference servers](https://github.com/modelcontextprotocol/servers) | `f46d9578190b476b3501923ea8977d899e8db2cb` | [Apache-2.0/MIT transition; documentation CC-BY-4.0](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/LICENSE) | README warning and component index; license |
| [OpenCode](https://github.com/anomalyco/opencode) | `b65de4d6943ef35337f8f2bfdbb369f6d25e7e9f` | [MIT](https://github.com/anomalyco/opencode/blob/b65de4d6943ef35337f8f2bfdbb369f6d25e7e9f/LICENSE) | Official MCP configuration and permission documentation; license |
| [Goose](https://github.com/block/goose) | `04ed836c8cde23e540cc77d256992e00be99298b` | [Apache-2.0](https://github.com/block/goose/blob/04ed836c8cde23e540cc77d256992e00be99298b/LICENSE) | using-extensions.md; license |
| [OpenHands](https://github.com/OpenHands/OpenHands) | `47a10808d78561546a02555d0d2c7fa96fa96300` | [MIT](https://github.com/OpenHands/OpenHands/blob/47a10808d78561546a02555d0d2c7fa96fa96300/LICENSE) | Current README architecture; license |
| [Langfuse](https://github.com/langfuse/langfuse) | `66f6226131714eb73cc88c3ccc4b851cd7b63c89` | [MIT outside excluded enterprise/third-party components](https://github.com/langfuse/langfuse/blob/66f6226131714eb73cc88c3ccc4b851cd7b63c89/LICENSE) | Official observation instrumentation and exploration docs; license |
| [OpenTelemetry specification](https://github.com/open-telemetry/opentelemetry-specification) | `cac5b81ebcfdecb272bb4e2d31f885b7142207d9` | [Apache-2.0](https://github.com/open-telemetry/opentelemetry-specification/blob/cac5b81ebcfdecb272bb4e2d31f885b7142207d9/LICENSE) | Official trace/span overview; license |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | `9110c25c495de6f43b40c9b22c900e819555f27c` | [MIT](https://github.com/promptfoo/promptfoo/blob/9110c25c495de6f43b40c9b22c900e819555f27c/LICENSE) | Official deterministic assertion/latency/cost documentation; license |

Codex behavior was checked using the OpenAI Docs skill and fetched official OpenAI
documentation, not inferred from a GitHub implementation revision. [Skills](https://learn.chatgpt.com/docs/build-skills),
[MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), and [hooks](https://learn.chatgpt.com/docs/hooks)
were retrieved on the audit date. Documentation licensing does not establish permission to
redistribute product implementation code. MIT reuse requires retaining copyright/license
notices; Apache reuse requires its notices and applicable attribution/change obligations.
For mixed or excluded components, inspect the exact component before reuse. This report
recommends Orqalis-native conceptual adaptations.

## Locally verified evidence

The targeted existing suite passed: **65 passed, 1 skipped in 82.16 seconds**:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_portable_skills.py tests/unit/test_provider_metrics.py tests/unit/test_planner_skills.py tests/integration/test_external_skill_selection.py tests/integration/test_mcp.py -q
```

The skipped test needs local permission to create a symlink. This run therefore does not
independently prove the symlink case on Windows. The tests include a real generic MCP stdio
process and two-client application continuation with a fixture reviewer. They are neither
live-provider task-quality measurements nor native assistant certification.

No P0 defect was demonstrated in this bounded audit. The principal P1 findings are missing
MCP lifecycle controls, incomplete skill-routing/efficiency evidence, and unused critical
path data in the UI. Bounded history/graph retrieval and export correlation need measured
workload qualification; they must not be represented as completed solely because models
or methods exist.

## Capability assessments

### H01 — Portable skill metadata and policy separation

- **PROJECT:** Agent Skills; Codex; Awesome Copilot.
- **SUBSYSTEM:** Skill Registry.
- **FEATURE:** Provider-neutral SKILL.md ingestion with explicit capability policy.
- **HOW IT WORKS:** Agent Skills defines frontmatter, instructions, and optional resource
  directories. Hosts select instructions from discoverable descriptions; host extensions
  are not guaranteed to have the same semantics.
- **WHY EFFECTIVE:** A small interchange surface enables reuse while leaving execution
  permission with the host.
- **ORQALIS CURRENT STATE:** `skills/markdown.py` validates names, descriptions, string
  metadata, size and tool requirements. `registry.py` rejects links, changed manifests,
  duplicates and exposed sensitive text. Existing TOML skills remain supported.
- **GAP:** No safety regression found. License and arbitrary upstream metadata are accepted
  but discarded from `SkillMetadata`; an operator cannot inspect their provenance through
  `list_skills`. Compatibility is text in `constraints`, not a validated environment check.
- **ADAPTATION:** Preserve optional source/license/compatibility metadata in an additive
  catalog projection. Keep unsupported scoped `allowed-tools` expressions fail-closed;
  document this strict profile, as current ecosystem documentation already does.
- **BENEFIT:** Better review and compatibility diagnostics without granting tools.
- **COST:** Small additive schema/UI change; no runtime dependency.
- **LICENSE:** Agent Skills Apache-2.0; Awesome Copilot MIT; no upstream code copied.
- **RISKS:** Treating a license declaration as proof of license, or treating compatibility
  text as executable configuration.
- **RECOMMENDATION:** **ADAPT, P2.** Existing permission behavior is sound; provenance is a
  follow-up, not grounds to import all upstream skills.
- **EVIDENCE:** [Agent Skills specification](https://agentskills.io/specification);
  `src/orqalis/skills/{markdown,registry}.py`; `domain/capabilities.py`;
  `tests/unit/test_portable_skills.py`; `docs/05-interfaces-and-integrations.md`.

### H02 — Progressive loading with measured context savings

- **PROJECT:** Agent Skills; Codex.
- **SUBSYSTEM:** Skill loading and context efficiency.
- **FEATURE:** Metadata discovery, selected body, on-demand references, deferred assets.
- **HOW IT WORKS:** Both references describe exposing a compact discovery catalog before
  loading selected instructions and optional resources. Codex also bounds its startup
  catalog and can shorten descriptions or omit entries when crowded.
- **WHY EFFECTIVE:** Selection need not inject every instruction/reference into each call.
- **ORQALIS CURRENT STATE:** `discover()` returns metadata, `load()` bodies, and
  `get_skill_resource` bounded UTF-8 content plus hashes. Discovery still reads the entire
  SKILL.md locally to parse/hash it; reduced model context is different from reduced disk I/O.
- **GAP:** Internal provider workers have no skill-resource tool. Resource-dependent skills
  can be selected but only MCP clients can fetch their references. No measured token/context
  reduction or quality non-regression is established by the new loader tests.
- **ADAPTATION:** Benchmark serialized catalog/body/resource bytes on fixed tasks. Either
  give internal workers a policy-checked resource capability, or reject/document those
  skills for that execution mode. Keep scripts/assets inert until a separately authorized
  execution capability exists.
- **BENEFIT:** Demonstrable context savings and honest portability guarantees.
- **COST:** Small deterministic benchmark; medium internal-worker resource integration.
- **LICENSE:** Agent Skills Apache-2.0; official OpenAI behavior documentation only.
- **RISKS:** Calling a byte proxy measured tokens; executing scripts merely because selected.
- **RECOMMENDATION:** **ADAPT, P1** for measurable loading/routing evidence; internal worker
  resource execution remains a separately scoped capability.
- **EVIDENCE:** [Codex skill loading](https://learn.chatgpt.com/docs/build-skills);
  `registry.py`, `mcp/server.py:get_skill_resource`, `execution/tool_definitions.py`,
  `providers/validation.py`; explicit internal-worker limitation in ecosystem docs.

### H03 — Skill routing and instruction-adherence evaluation

- **PROJECT:** Superpowers; Promptfoo; Awesome Copilot.
- **SUBSYSTEM:** Skill QA.
- **FEATURE:** Baseline-versus-skill evaluation, adversarial routing, deterministic checks.
- **HOW IT WORKS:** Superpowers evaluates discipline under realistic pressure before and
  after instructions. Promptfoo supports exact/custom assertions and latency/cost checks.
  Awesome Copilot separately validates package/frontmatter structure.
- **WHY EFFECTIVE:** Structural validity, routing correctness and behavioral quality are
  distinct failure classes.
- **ORQALIS CURRENT STATE:** Planner skill tests cover language/path applicability, permission
  subsets, selected versions, and repair retention. External selection has a documentation
  task integration test. The registry uses deterministic capability coverage, not semantic
  description matching.
- **GAP:** No stable confusion matrix for false positives/negatives, explicit-vs-automatic
  selection, or provider behavioral portability. Existing pytest success cannot establish
  that a skill improves a model's work.
- **ADAPTATION:** Add a local table of task/role/tools/tags/pins and exact expected skill IDs.
  Include ambiguous task descriptions, unsupported tools, negatives and multi-language
  scope. Separately run identical recorded tasks with/without skills against configured
  live providers; grade artifacts/tests deterministically where possible.
- **BENEFIT:** Routing improvements become reproducible; generic guidance can be removed
  if it adds context without measurable benefit.
- **COST:** Small fixture suite; medium optional live evaluation cost.
- **LICENSE:** Superpowers, Promptfoo and Awesome Copilot MIT.
- **RISKS:** Overfitting to current capability names; confusing fixture providers with model
  quality; storing hidden reasoning during pressure tests.
- **RECOMMENDATION:** **ADD, P1.** Use native pytest/JSON first; a mandatory Promptfoo runtime
  is unnecessary.
- **EVIDENCE:** [Superpowers skill testing](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/writing-skills/testing-skills-with-subagents.md),
  [Promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/),
  [Copilot validation scripts](https://github.com/github/awesome-copilot/blob/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c/package.json);
  `tests/unit/test_planner_skills.py`, `tests/integration/test_external_skill_selection.py`.

### H04 — Curated skill/plugin distribution

- **PROJECT:** Awesome Copilot; Superpowers.
- **SUBSYSTEM:** Skills/plugins.
- **FEATURE:** Package validation and curated, immutable imports.
- **HOW IT WORKS:** Awesome Copilot validates skill and plugin metadata and documents
  reviewed external-plugin intake. Its repository distinguishes portable skills from
  Copilot-specific package content.
- **WHY EFFECTIVE:** Distribution quality and provenance are checked before activation.
- **ORQALIS CURRENT STATE:** Explicit trusted roots and ID/version selection avoid silent
  repository-wide activation; instruction/resource hashes detect changes during use.
- **GAP:** No package installer, dependency resolver or marketplace exists. This is not
  required to make the current registry useful.
- **ADAPTATION:** Retain explicit roots. If imports are later added, require an immutable
  source pin, license record, dependency inventory and compatibility report.
- **BENEFIT:** Preserves a small, reviewable registry and reproducible instructions.
- **COST:** None for current policy; medium for a future importer.
- **LICENSE:** MIT; component licenses still need inspection.
- **RISKS:** Unbounded imports, conflicting instructions, host-specific hooks, mutable refs.
- **RECOMMENDATION:** **KEEP, current foundation.** Automated bulk installation is rejected
  as an implementation approach, not an accepted enhancement backlog item.
- **EVIDENCE:** [Pinned contributing policy](https://github.com/github/awesome-copilot/blob/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c/CONTRIBUTING.md);
  `SkillRegistry.__init__`, `SkillRegistry.select`, `docs/05-interfaces-and-integrations.md`.

### H05 — Provider-neutral lifecycle hooks

- **PROJECT:** Claude Agent SDK; Codex hooks.
- **SUBSYSTEM:** Harness hooks.
- **FEATURE:** Explicit lifecycle callbacks with trust and bounded effects.
- **HOW IT WORKS:** Claude SDK callbacks match lifecycle events and may return structured
  decisions. Event availability differs between Python and TypeScript. Codex requires trust
  for unmanaged hook definitions and may launch multiple matching commands concurrently.
- **WHY EFFECTIVE:** Clear events enable policy and instrumentation without prompt-only
  enforcement; explicit trust prevents repository hooks from silently becoming authority.
- **ORQALIS CURRENT STATE:** Core policy/approval/validation services and typed events already
  implement many desired uses. `ProjectEventBus` is a notification mechanism for committed
  events, not a permission callback registry.
- **GAP:** No supported external SessionStart/SessionEnd/UserPrompt hook mapping. Generic
  callbacks could bypass deterministic orchestration if added casually.
- **ADAPTATION:** Define an adapter mapping first. Treat post-event hooks as observational;
  gate before-actions through existing services. A future HookResult may request a bounded
  context reference or policy denial, never mutate global workflow state. Require exact
  handler hash trust, timeout, recursion limits and an auditable result.
- **BENEFIT:** Future host integration can reuse policy and telemetry rather than inventing
  hidden paths.
- **COST:** Medium/high for safe arbitrary command hooks.
- **LICENSE:** Claude SDK MIT; Codex product documentation not code-reuse evidence.
- **RISKS:** Hook loops, startup failures, private transcript export, widened permissions,
  provider event names mistaken for equivalent semantics.
- **RECOMMENDATION:** **DEFER, P2.** Current policy services satisfy core gating. Implement
  native hook execution only with a concrete tested host use case.
- **EVIDENCE:** [Claude SDK hooks and availability matrix](https://code.claude.com/docs/en/agent-sdk/hooks),
  [Codex hooks/trust](https://learn.chatgpt.com/docs/hooks); `domain/events.py`,
  `observability/event_bus.py`, `core/approvals.py`, `execution/tools.py`.

### H06 — Supported assistant contract and qualification

- **PROJECT:** Codex; Claude; GitHub Copilot; OpenCode; Goose.
- **SUBSYSTEM:** Assistant integrations.
- **FEATURE:** One project-bound MCP contract across host clients.
- **HOW IT WORKS:** Hosts configure MCP processes/transports and discover server tools.
  Their permission UI, skill discovery and interruption behavior differ; MCP alone does
  not certify equivalent native session behavior.
- **WHY EFFECTIVE:** A common service boundary preserves project knowledge across assistants.
- **ORQALIS CURRENT STATE:** Codex/Claude/VS Code stdio examples, explicit roots, policy-scoped
  high-level tools, SDK validation, and two-client continuation tests exist.
  `ExternalCLIProvider` requires an injected host transport and is not a native launcher.
- **GAP:** No dated native-host test record was found. OpenCode/Goose-specific configuration
  examples are absent. Existing generic tests cannot prove host cancellation or reconnect.
- **ADAPTATION:** Publish a support matrix separating configuration example, generic protocol
  verification, and native-host verification. Use the same deterministic task: discover,
  context, skill, claim work, disconnect, reconnect, inspect, report, independently review.
  Record client/version, root, OS, outcomes and unavailable scenarios.
- **BENEFIT:** Honest interoperable support with replaceable workers.
- **COST:** Small contract/docs work; medium client qualification.
- **LICENSE:** OpenCode MIT; Goose Apache-2.0; proprietary host availability is separate.
- **RISKS:** Accidentally attributing provider API success to native host support; treating
  host permission grants as authorization to exceed Orqalis policy.
- **RECOMMENDATION:** **ADAPT, P1** for a repeatable supported contract and accurate evidence.
- **EVIDENCE:** [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
  [GitHub MCP overview](https://docs.github.com/en/copilot/concepts/context/mcp),
  [OpenCode MCP](https://opencode.ai/docs/mcp-servers/),
  [Goose extensions](https://github.com/block/goose/blob/04ed836c8cde23e540cc77d256992e00be99298b/documentation/docs/getting-started/using-extensions.md);
  `tests/integration/test_mcp.py`, `providers/external_cli.py`, `docs/examples/`.

### H07 — MCP lifecycle control parity

- **PROJECT:** Official MCP SDK/protocol; existing Orqalis CLI/API.
- **SUBSYSTEM:** MCP continuation and interruption.
- **FEATURE:** Pause, resume, cancel, and explicitly acknowledged recovery through MCP.
- **HOW IT WORKS:** The protocol supports cancelling an in-flight request; cancellation is
  not the same as a durable application pause/cancel/recovery transition.
- **WHY EFFECTIVE:** Application lifecycle survives transport and assistant replacement.
- **ORQALIS CURRENT STATE:** SDK/API/CLI expose controls and an audited recovery service.
  At initial audit `mcp/server.py` exposed none of these four controls.
- **GAP:** An MCP-only assistant can inspect an interrupted task but cannot invoke the safe
  continuation operation. This is a concrete interface omission, not a native-launcher gap.
- **ADAPTATION:** Add four thin MCP tools calling the same services. Require server work
  permission, bound project/run validation and caller-supplied idempotency keys. Recovery
  must retain explicit uncertainty acknowledgement, non-secret reason and worker lease checks.
- **BENEFIT:** Completes the supported provider-neutral lifecycle without subprocess adapters.
- **COST:** Small; existing services and policies own the difficult semantics.
- **LICENSE:** Orqalis-native code; MCP SDK MIT.
- **RISKS:** Automatically acknowledging uncertain writes; permitting a read-only server to
  mutate; conflating transport interruption with a completed cancellation.
- **RECOMMENDATION:** **ADD, P1.** Implementation assigned after this audit; record its tests
  separately rather than retroactively treating the initial finding as absent.
- **EVIDENCE:** [MCP cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation),
  `mcp/server.py`, `mcp/policy.py`, `sdk.py:pause/resume/cancel`, `core/recovery.py`,
  `api/app.py:recover` and `tests/integration/test_run_controls.py`.

### H08 — Bounded MCP data and discovery

- **PROJECT:** Official MCP protocol/SDK; OpenCode.
- **SUBSYSTEM:** MCP payloads and scale.
- **FEATURE:** Bounded task-oriented retrieval with explicit continuation/truncation.
- **HOW IT WORKS:** MCP paginates protocol list operations with opaque cursors. Domain tool
  result pagination is an application design; MCP does not automatically bound graph JSON.
  OpenCode documents that many enabled tools consume significant context.
- **WHY EFFECTIVE:** Clients can retrieve relevant slices without whole-history exposure.
- **ORQALIS CURRENT STATE:** Context budgets, search limits, bounded impact/path queries and
  metadata-only skills exist. Full graph/architecture/run tools still return complete
  projections. `list_tasks(limit)` provides no continuation token.
- **GAP:** Older task history can be undiscoverable at a fixed limit; full graphs can exceed
  host output budgets. `get_skill_resource` caps each file but has no aggregate session quota.
- **ADAPTATION:** Preserve compatibility tools, add a compact graph catalog/neighborhood and
  stable task-page cursor tied to an index revision. Expose `has_more`/truncation and reject
  stale/cross-project cursors. Measure schemas as well as response bytes before adding tools.
- **BENEFIT:** Predictable context and memory use on large local repositories.
- **COST:** Medium; root/index cursor semantics need careful design.
- **LICENSE:** MCP SDK MIT; protocol/reference licensing must be checked per component.
- **RISKS:** Cursor leakage across projects, unstable sort order, treating the existing
  depth/node-bounded path/impact queries as missing.
- **RECOMMENDATION:** **ADAPT, P1** for large-history reachability and payload qualification.
  Do not add protocol pagination blindly to a fixed small tool list.
- **EVIDENCE:** [MCP pagination scope](https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination);
  `mcp/server.py:get_project_graph/list_tasks/get_run`, `tasks/history.py`,
  `graph/queries.py`, `context/builder.py`.

### H09 — Reference servers as examples, not infrastructure

- **PROJECT:** Official MCP reference servers.
- **SUBSYSTEM:** MCP architecture/dependencies.
- **FEATURE:** Protocol-compliant high-level services.
- **HOW IT WORKS:** The Everything/reference servers demonstrate protocol features; their
  README explicitly distinguishes educational examples from production solutions.
- **WHY EFFECTIVE:** They are useful conformance examples without dictating project authority.
- **ORQALIS CURRENT STATE:** The maintained SDK provides protocol framing/schema generation;
  Orqalis owns policy, project isolation and persistence.
- **GAP:** No evidence supports replacing Orqalis memory or task services with a reference
  server, or adding an external database to resemble one.
- **ADAPTATION:** Reuse protocol test cases conceptually; retain the current SDK boundary.
- **BENEFIT:** No extra service, duplicated state or mandatory infrastructure.
- **COST:** None for retaining architecture; small compatibility tests.
- **LICENSE:** Pinned servers license is transitioning MIT to Apache-2.0; documentation
  contributions are CC-BY-4.0. Do not record this repository as uniformly MIT.
- **RISKS:** Copying a component without checking original contributor/component terms.
- **RECOMMENDATION:** **REJECT** reference-server replacement/mandatory deployment.
- **EVIDENCE:** [Pinned README](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/README.md)
  and [license](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/LICENSE);
  `docs/SOURCE_OF_TRUTH.md`, `mcp/server.py`.

### H10 — Control Center as an event-backed projection

- **PROJECT:** OpenHands; existing Orqalis.
- **SUBSYSTEM:** Control Center state and reconnect.
- **FEATURE:** UI/client separated from authoritative agent services.
- **HOW IT WORKS:** The inspected OpenHands README now describes Agent Canvas consuming
  the Agent Server API through a TypeScript client; SDK/server owns conversations/events.
  Older assumptions about all runtime code living in the UI repository are stale.
- **WHY EFFECTIVE:** Presentation and execution can evolve without duplicate authority.
- **ORQALIS CURRENT STATE:** React consumes FastAPI/WebSocket snapshots. The event bus sends
  committed sequence notifications; clients can reconstruct from persisted capsule history.
  Backend subscribes before replay, avoiding the usual replay/live registration race.
- **GAP:** No architecture replacement is justified. Backend sends complete snapshots and
  reloads events at least once per second, including idle periods, so large-run cost is a
  measurement concern even though displayed rows are paged.
- **ADAPTATION:** Retain current authority; measure snapshot/serialization time and payload
  bytes at 1k/10k events before considering incremental caches or lighter refreshes.
- **BENEFIT:** Reliable offline/restart inspection without UI orchestration.
- **COST:** Small benchmark; medium optimization only if a budget is exceeded.
- **LICENSE:** OpenHands root MIT; no visual design or implementation copied.
- **RISKS:** Demo-only validation, quadratic projection work, adding a competing UI store.
- **RECOMMENDATION:** **KEEP** the boundary; record scale qualification under H08/H12.
- **EVIDENCE:** [Current OpenHands architecture](https://github.com/OpenHands/OpenHands/blob/47a10808d78561546a02555d0d2c7fa96fa96300/README.md);
  `observability/event_bus.py`, `observability/projections.py`, `api/app.py:stream`,
  `tests/e2e/test_local_control_center_filesystem.py`.

### H11 — Local trace hierarchy and optional export

- **PROJECT:** OpenTelemetry; Langfuse.
- **SUBSYSTEM:** Observability correlation.
- **FEATURE:** Run/phase/task/actor/model/tool navigation with explicit parent relationships.
- **HOW IT WORKS:** OpenTelemetry groups spans by trace and records parent/link context.
  Langfuse provides nested typed observations, including generations/tools, and supports
  explicit parenting for non-contiguous work.
- **WHY EFFECTIVE:** A slow or failed call can be traced back to the responsible task and
  evidence without reconstructing opaque conversations.
- **ORQALIS CURRENT STATE:** Local records already have run/task/actor IDs; ToolInvocation
  includes `provider_invocation_id`, so model-to-tool linkage exists. Operation spans,
  metrics and an opt-in stderr console exporter already exist. Events capture an active
  OTel trace ID where available.
- **GAP:** No durable span/parent-span hierarchy is exposed. `Event.correlation_id`,
  `Event.causation_id` and request `trace_id` have no production assignment found beyond
  declaration. Operation spans do not include allowlisted run/task/actor IDs. Provider and
  tool lists remain separate UI views rather than a full hierarchy.
- **ADAPTATION:** Derive a local trace projection from existing IDs first. Link resumed
  execution spans to durable run/task identities; do not keep one span open across process
  restarts. Add an allowlist of identifiers/status/usage to spans and an optional exporter
  interface after correlation tests. Keep payload capture disabled.
- **BENEFIT:** Better incident diagnosis and optional external observability without hosted
  dependency or canonical-state migration.
- **COST:** Medium; existing telemetry dependency reduces integration cost.
- **LICENSE:** OTel Apache-2.0; Langfuse MIT outside excluded enterprise/third-party portions.
- **RISKS:** Exporting prompts, tool arguments, hidden reasoning or secrets; lost async
  context; falsely treating operation latency as model latency.
- **RECOMMENDATION:** **ADAPT, P1** for locally useful trace correlation; network exporters
  may remain explicitly deferred P2.
- **EVIDENCE:** [OTel trace/span model](https://opentelemetry.io/docs/specs/otel/overview/),
  [Langfuse observations](https://langfuse.com/docs/observability/sdk/instrumentation);
  `domain/events.py`, `domain/execution.py:ToolInvocation`, `domain/provider.py`,
  `observability/instrumentation.py`, `persistence/filesystem/task_store.py`.

### H12 — Timeline, critical path and observed performance

- **PROJECT:** Langfuse; OpenHands; existing Orqalis.
- **SUBSYSTEM:** Control Center timeline/metrics.
- **FEATURE:** Drill down from measured intervals to task attempts, model calls and evidence.
- **HOW IT WORKS:** Observation explorers filter related operations and compare model
  latency. A workflow timeline should also distinguish waiting, blocking and repair attempts.
- **WHY EFFECTIVE:** Users can identify the actual bottleneck rather than a fabricated
  completion percentage or a misleading average.
- **ORQALIS CURRENT STATE:** Timeline uses persisted actor/task/phase intervals, pages tracks,
  and exposes interval timestamps/evidence. The new provider table reports outcome counts,
  nearest-rank p50/p95, usage/cost coverage and unknown values correctly. Backend computes
  `critical_path_task_ids` and working duration.
- **GAP:** No TSX consumer of critical-path fields was found. Model/tool intervals are absent
  from the timeline, and causal handoffs are not navigable. New metrics tests are sound but
  do not validate the UI against an actual multi-agent repair/interruption run.
- **ADAPTATION:** Display the backend critical path with its measured-working-time meaning;
  link intervals to model/tool records and task attempts using existing IDs. Test a real
  deterministic two-worker DAG with waiting, a failed review, repair and restart.
- **BENEFIT:** Makes existing backend intelligence useful without inventing frontend logic.
- **COST:** Small for critical-path display; medium for complete drill-down and workload QA.
- **LICENSE:** Langfuse component-dependent MIT; OpenHands MIT; conceptual adaptation only.
- **RISKS:** Calling historical working-time path a forecast; treating succeeded provider
  calls as accepted work; plotting missing duration as zero.
- **RECOMMENDATION:** **ADAPT, P1.** Keep provider metrics calculation; close the missing
  projection consumption and validate using runtime-produced records.
- **EVIDENCE:** [Langfuse observation exploration](https://langfuse.com/faq/all/explore-observations-in-v4);
  `observability/analytics.py`, `web/src/{Timeline,ProviderMetrics,MetricsView}.tsx`,
  `tests/unit/test_provider_metrics.py`, `web/src/ProviderMetrics.test.tsx`.

### H13 — Mandatory observability infrastructure

- **PROJECT:** Langfuse; OpenTelemetry.
- **SUBSYSTEM:** Distribution/dependency policy.
- **FEATURE:** Optional external observation sinks.
- **HOW IT WORKS:** External observation products receive telemetry; this is separate from
  authoritative workflow persistence.
- **WHY EFFECTIVE:** Decoupling sinks lets deployments choose operational tooling.
- **ORQALIS CURRENT STATE:** Local capsules and event history work without any external sink;
  console telemetry is opt-in.
- **GAP:** A network exporter is absent, but that does not justify mandatory infrastructure.
- **ADAPTATION:** Retain local-first defaults and design an optional adapter only after H11.
- **BENEFIT:** Preserves clean-clone, offline and constrained-machine operation.
- **COST:** None now; optional adapter cost later.
- **LICENSE:** Component-level license review required for any added exporter dependency.
- **RISKS:** Accidental telemetry egress or vendor-specific identifiers becoming authority.
- **RECOMMENDATION:** **REJECT** mandatory Langfuse/hosted observability adoption.
- **EVIDENCE:** `docs/SOURCE_OF_TRUTH.md`; `observability/instrumentation.py`;
  [Langfuse instrumentation](https://langfuse.com/docs/observability/sdk/instrumentation).

## Acceptance and benchmark proposals

| ID | Acceptance criteria | Deterministic tests | Benchmark/evidence |
| --- | --- | --- | --- |
| H02/H03 | Discovery returns no body/reference; exact routing decisions and version pins pass; internal-worker resource support is explicitly scoped | Positive/negative/ambiguous fixtures, multilang scope, denied tools, mutated manifest/resource, wrong pin, missing refs, Unicode/CRLF, native/legacy duplicates | Same corpus eager vs staged serialized bytes; report reduction, read counts, startup/selection latency; live provider token/quality data remains separately labeled |
| H06 | Support matrix accurately separates configuration, protocol test and native-host qualification | Parse committed examples; exercise one project-bound stdio contract and replacement-client continuation | Record OS/client/version, cold startup, discovery schema bytes, tool latency; native unavailable means unverified, not pass |
| H07 | Work-gated pause/resume/cancel/recover operate on bound runs with idempotent receipts; recovery never silently acknowledges uncertainty | Read-only denial, foreign/unknown run, repeat key, changed recovery request, active worker lease, wrong execution, missing acknowledgement, restart continuation | Runtime-generated event count/state checks; cancel latency where real owned command execution is used |
| H08 | Bounded graph/history pages have honest continuation and preserve old APIs | Empty/full pages, stable ties, stale cursor, root mismatch, >page-size history, result budgets | 100/1k/10k tasks and nodes; payload bytes, wall time, peak memory; measure tool schema catalog cost |
| H11 | Every tool maps to a provider/task/actor/run locally; resumed spans are linked; traces contain only allowlisted metadata | In-memory exporter + deterministic worker, failure/cancel/restart, no orphan links, secret/hidden-reasoning sentinel exclusion | Export disabled/enabled overhead; no-network default; identifiers survive local history reconstruction |
| H12 | UI displays backend critical path and correct attempts/repair/wait intervals | Backend-generated two-worker DAG; inspect task evidence and model/tool IDs; refresh and restart; no hardcoded metrics | Snapshot derivation p50/p95, WebSocket-to-render latency, payload bytes, frontend bundle delta; do not use static demo timing as acceptance |

Suggested first slice is H07 because it reuses proven services and closes a concrete
provider-neutral contract gap. Routing/context measurements can proceed independently.
For H08, first measure/history-test before extending schemas; a full graph compatibility
tool is not inherently wrong when an explicitly bounded alternative is available.
This stream does not certify convergence: live host qualification, workload benchmarks,
and two full clean iterations remain program-level evidence requirements.


## Implementation addendum - 2026-09-26

The findings above preserve the initial audit. The following approved P1 adaptations
were subsequently implemented in this shared working tree; they are not claims about
immutable v2.0.0 or live native assistant qualification.

- **H07:** `pause_run`, `resume_run`, `cancel_run`, `recover_task` now forward to Core
  with root/work policy checks, explicit bounded keys, durable receipts and uncertainty
  acknowledgement. Three actual generic-MCP lifecycle tests cover policy/root denial,
  waiting checkpoint requirements, active leases, changed recovery requests and client
  replacement. No host process-launch or host cancellation hook is implied.
- **H08:** New `list_task_page` preserves `list_tasks`. Pages contain up to 100 compact
  entries with deterministic timestamp/ID ordering. Continuation binds resolved root,
  project identity and exact index revision; copied roots and stale revisions fail.
  Four tests cover equal timestamps, restart continuation, invalid tokens/limits,
  stale/cross-root cursors, empty history and avoiding full stage enrichment. Backend
  index rebuilding still scans compact metadata; constant-time history access and full
  graph snapshot pagination remain separate scaling work. The existing bounded graph
  impact/path and new symbolic alternatives complement compatibility snapshot tools.
- **H11:** `RunSnapshot.trace` rebuilds stable run/phase/attempt/actor/model/tool
  identities. Phase/task event order and persisted actor/provider IDs supply parentage;
  unavailable historical parentage falls back to the run. Shared actors retain related
  attempt links. Existing OTel agent/tool spans carry only allowlisted UUID attributes;
  metrics receive no high-cardinality IDs. No network sink is configured. Local durable
  identities are not OTel trace IDs; cross-process distributed trace-context propagation
  remains deferred and is not required for restart reconstruction.
- **H12:** Timeline displays the backend measured critical path and operation trace,
  with 50-row pages, kind filters, parent ancestry and evidence/provider links. Unknown
  duration is explicit. A real persisted run supplies the ~113 KB frontend fixture:
  two context workers overlap, review fails, repair succeeds, and pause/resume occurs.
  Its trace is identical after reopening. No synthetic timings substitute for this
  integration evidence. Broader render/scale benchmarking remains program-level work.

Validation on this working tree: actual runtime trace/restart/OTel correlation test
**1 passed (64.85 s)**; lifecycle/history/instrumentation **8 passed (72.14 s)**;
existing MCP workflow/stdio/project-isolation regressions **2 passed (71.33 s)**;
historical/shared-session fallback **1 passed**; actual-snapshot React rendering
**3 passed**; Chrome keyboard ancestry/filter/mobile test **1 passed (4.5 s)**.
The final mobile screenshot was visually inspected. TypeScript compilation, targeted
ESLint/Ruff and mypy on seven changed Python contracts passed. The MCP memory and symbolic
adapters are coordinated with the knowledge stream's service/interface tests. These are
bounded deterministic tests, not native Codex/Claude/Copilot or exporter qualification.

---

## Evaluation and dependency research

Inspected 2026-09-26. This is source/documentation research and a native evaluation design,
not an upstream runtime performance contest. No reference implementation code was copied.

| Reference | Revision / component | Observed license | Evidence |
| --- | --- | --- | --- |
| Promptfoo | `9110c25c495de6f43b40c9b22c900e819555f27c`, configuration/assertions | MIT | [License](https://github.com/promptfoo/promptfoo/blob/9110c25c495de6f43b40c9b22c900e819555f27c/LICENSE), [configuration reference](https://www.promptfoo.dev/docs/configuration/reference/) |
| DeepEval | `385117c9c46e6935866422b7aa1f67e5e2824472`, evaluation/test cases | Apache-2.0 | [License](https://github.com/confident-ai/deepeval/blob/385117c9c46e6935866422b7aa1f67e5e2824472/LICENSE.md), [single-turn evaluation](https://deepeval.com/docs/evaluation-end-to-end-single-turn) |

### EV01: versioned comparisons and deterministic gates ? ADD (E01)

PROJECT: Promptfoo, DeepEval. SUBSYSTEM: evaluation. FEATURE: explicit datasets, expected
outputs, assertions, repeat counts and named metrics. HOW IT WORKS: configured cases run
through selected providers or stored outputs; deterministic assertions and optional judges
produce separate measurements. WHY EFFECTIVE: stable inputs and explicit metric definitions
make regressions attributable. ORQALIS CURRENT: strong pytest contracts without a fixed
cross-subsystem quality/performance dataset. GAP: no trustworthy differential measurement
for the first feature wave. ADAPTATION: native JSON dataset plus isolated source processes,
independent labels and raw reports; retain pytest for actual persisted execution contracts.
BENEFIT: reproducible evidence without a second agent framework. COST: medium. LICENSE:
MIT/Apache concepts only. RISKS: tiny synthetic fixtures, cached outputs, biased labels and
conflating retrieval recall with coding success. RECOMMENDATION: ADD native suite; distinguish
engineering categories from held-out retrieval probes and label all unmeasured model metrics.
EVIDENCE: [Promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/),
[test-case repeats/cache](https://www.promptfoo.dev/docs/configuration/test-cases/).

### EV02: evidence-based review ? KEEP (E02)

PROJECT: Superpowers, SWE-agent, mini-swe-agent. SUBSYSTEM: acceptance/repair. FEATURE:
independent verification and recorded task outcomes. HOW IT WORKS: explicit tests or review
criteria decide whether implementation satisfies a task. WHY EFFECTIVE: a plausible narrative
cannot replace executable evidence. ORQALIS CURRENT: criterion-linked validators, independent
reviewer, exact tree digest, bounded targeted repairs, delivery gates. GAP: the verified
Guardian and crash-coverage gaps are tracked separately, not a missing acceptance engine.
ADAPTATION: keep the architecture and extend adversarial/restart fixtures. BENEFIT: preserves
current strengths. COST: low. LICENSE: MIT concepts; no skill prose copied. RISKS: passing
fixture reviewers do not demonstrate live model judgment quality. RECOMMENDATION: KEEP.
EVIDENCE: runtime/harness research and `tests/integration/test_repair.py`,
`test_external_findings.py`, `test_supervised_delivery_repair.py`.

### EV03: optional model judges ? DEFER (E03)

PROJECT: Promptfoo, DeepEval. SUBSYSTEM: live model quality. FEATURE: model-graded task and
instruction adherence. HOW IT WORKS: user-selected models grade outputs or traces against
criteria. WHY EFFECTIVE: can measure qualities without a deterministic oracle. ORQALIS CURRENT:
provider schemas, deterministic fake-provider contracts and telemetry exist. GAP: live Codex/
Claude behavioral quality is not measured. ADAPTATION: keep a future budgeted, opt-in layer
using the same labeled task IDs. BENEFIT: comparative behavior evidence. COST: variable paid
model usage and repeat sampling. LICENSE: MIT/Apache. RISKS: sensitive prompts, non-determinism,
judge bias and retaining private reasoning. RECOMMENDATION: DEFER mandatory live judging;
never substitute fake-provider results for live-model success, or persist hidden reasoning.
EVIDENCE: [DeepEval single-turn contract](https://deepeval.com/docs/evaluation-end-to-end-single-turn).

### Dependency decisions (E04)

A handwritten general YAML parser would create an unsafe, incompatible interchange format;
PyYAML is used only through bounded safe parsing with strict keys, tags and alias rejection.
Tree-sitter avoids regex pretending to understand TSX, generics or nested declarations.
Adopt only the Python binding and JS/TS grammars, not a large all-language pack. Existing
Python `ast` remains. No service, GPU, network runtime or database is added. Python package
metadata, pinned upstream license text and published wheel sizes are recorded in
[dependency evidence](../evidence/dependency-research.json). Platform wheel presence is a
packaging observation, not a claim that this Windows session ran on every OS.

The parser binding, JS grammar and TS grammar each have MIT notices. Runtime dependencies
must retain their distributed notices through package tooling. No upstream parser source is
vendored or modified. Verify installed wheel metadata as well as upstream HEAD notices;
record exact lock versions and test grammar ABI compatibility. Measure startup/footprint
before accepting the integration. Current-generation grammars are lazy-loaded for source
parsing, not executable project plugins.


### Prequalification source refresh

The 2026-09-26 [DeepEval refresh](../evidence/evaluation-upstream-audit-1.json)
observed unchanged HEAD `385117c9c46e6935866422b7aa1f67e5e2824472`, an unarchived
repository with recent push activity, and the same pinned Apache-2.0 notice. Its official
single-turn documentation still distinguishes explicit test cases and evaluation metrics.
E01 remains an original local deterministic harness; E03 live model judging remains
optional/deferred because fake providers cannot qualify model judgment or task quality.
Promptfoo's refreshed evidence is maintained in the separate harness audit. Neither
upstream's activity warrants a mandatory runtime/service dependency. This refresh is part
of prequalification, not a clean convergence iteration.

---

## Harness audit: iteration 1

Audit date: 2026-09-26. Upstream metadata captured at `2026-09-26T16:21:58.217965+00:00`.
Baseline remains immutable `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / `v2.0.0`.
This bounded follow-up covers skills, assistant/MCP integrations, hooks, Control Center,
observability and evaluation integrity. It does not establish global convergence, live
assistant qualification, live-model quality, or comparative performance. Original failed
captures remain evidence; new compatibility or harness versions do not erase them.

### Fresh upstream revision and maintenance ledger

The [machine-readable ledger](../evidence/harness-upstream-iteration-1.json) records public
`git ls-remote HEAD`, successful unauthenticated GitHub repository/commit responses, and
pinned raw license hashes. Unlike the earlier rate-limited audit, this pass obtained commit
dates and archive flags. All twelve repositories report `archived=false` and `disabled=false`.
A latest commit date is evidence of observed activity, not a maintenance guarantee or SLA.

| Project | Exact HEAD / primary commit evidence | Commit date UTC | License inspected |
| --- | --- | --- | --- |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | [`69ef37e9424c0a7ea9dd2293b559e43ec8176379`](https://github.com/agentskills/agentskills/commit/69ef37e9424c0a7ea9dd2293b559e43ec8176379) | 2026-08-09T20:36:04Z | [Apache-2.0](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/LICENSE) |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | [`6c4d33b9cfca967a28bb2962ef4d55e4a384c88c`](https://github.com/github/awesome-copilot/commit/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c) | 2026-09-25T01:58:01Z | [MIT](https://github.com/github/awesome-copilot/blob/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c/LICENSE) |
| [obra/superpowers](https://github.com/obra/superpowers) | [`8ca22dba9a94f28898bbce59f2537ff4d87c747d`](https://github.com/obra/superpowers/commit/8ca22dba9a94f28898bbce59f2537ff4d87c747d) | 2026-09-25T18:06:27Z | [MIT](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/LICENSE) |
| [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) | [`36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6`](https://github.com/anthropics/claude-agent-sdk-python/commit/36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6) | 2026-09-25T22:32:23Z | [MIT SDK; host terms separate](https://github.com/anthropics/claude-agent-sdk-python/blob/36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6/LICENSE) |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | [`f1b6589088534632fef92238ee9750951e3c0185`](https://github.com/modelcontextprotocol/python-sdk/commit/f1b6589088534632fef92238ee9750951e3c0185) | 2026-09-23T08:50:55Z | [MIT](https://github.com/modelcontextprotocol/python-sdk/blob/f1b6589088534632fef92238ee9750951e3c0185/LICENSE) |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | [`f46d9578190b476b3501923ea8977d899e8db2cb`](https://github.com/modelcontextprotocol/servers/commit/f46d9578190b476b3501923ea8977d899e8db2cb) | 2026-09-22T14:30:15Z | [Apache-2.0 / retained MIT; docs CC-BY-4.0](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/LICENSE) |
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | [`a42f393c850bec0c0f395fb91bf19b1ee8b31666`](https://github.com/anomalyco/opencode/commit/a42f393c850bec0c0f395fb91bf19b1ee8b31666) | 2026-09-26T15:55:17Z | [MIT](https://github.com/anomalyco/opencode/blob/a42f393c850bec0c0f395fb91bf19b1ee8b31666/LICENSE) |
| [block/goose](https://github.com/block/goose) | [`04ed836c8cde23e540cc77d256992e00be99298b`](https://github.com/block/goose/commit/04ed836c8cde23e540cc77d256992e00be99298b) | 2026-09-25T17:09:27Z | [Apache-2.0](https://github.com/block/goose/blob/04ed836c8cde23e540cc77d256992e00be99298b/LICENSE) |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | [`47a10808d78561546a02555d0d2c7fa96fa96300`](https://github.com/OpenHands/OpenHands/commit/47a10808d78561546a02555d0d2c7fa96fa96300) | 2026-09-26T02:04:45Z | [MIT](https://github.com/OpenHands/OpenHands/blob/47a10808d78561546a02555d0d2c7fa96fa96300/LICENSE) |
| [langfuse/langfuse](https://github.com/langfuse/langfuse) | [`66f6226131714eb73cc88c3ccc4b851cd7b63c89`](https://github.com/langfuse/langfuse/commit/66f6226131714eb73cc88c3ccc4b851cd7b63c89) | 2026-09-26T11:50:20Z | [MIT except enterprise and third-party components](https://github.com/langfuse/langfuse/blob/66f6226131714eb73cc88c3ccc4b851cd7b63c89/LICENSE) |
| [open-telemetry/opentelemetry-specification](https://github.com/open-telemetry/opentelemetry-specification) | [`cac5b81ebcfdecb272bb4e2d31f885b7142207d9`](https://github.com/open-telemetry/opentelemetry-specification/commit/cac5b81ebcfdecb272bb4e2d31f885b7142207d9) | 2026-09-23T14:44:26Z | [Apache-2.0](https://github.com/open-telemetry/opentelemetry-specification/blob/cac5b81ebcfdecb272bb4e2d31f885b7142207d9/LICENSE) |
| [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | [`9110c25c495de6f43b40c9b22c900e819555f27c`](https://github.com/promptfoo/promptfoo/commit/9110c25c495de6f43b40c9b22c900e819555f27c) | 2026-09-26T09:28:23Z | [MIT](https://github.com/promptfoo/promptfoo/blob/9110c25c495de6f43b40c9b22c900e819555f27c/LICENSE) |

Only OpenCode moved since the initial harness audit: one documentation commit changes an
ecosystem product link across translations. The [exact comparison](https://github.com/anomalyco/opencode/compare/b65de4d6943ef35337f8f2bfdbb369f6d25e7e9f...a42f393c850bec0c0f395fb91bf19b1ee8b31666)
contains no MCP or permission implementation change. The other eleven inspected HEADs are
unchanged. No dependency adoption is justified solely by these activity signals.

Licenses were reviewed at these pins, not inferred from repository badges. MCP reference
servers explicitly retain MIT contributions lacking relicensing consent while new code is
Apache-2.0; documentation has separate terms. Langfuse excludes `ee/`, `web/src/ee/`,
`worker/src/ee/` and third-party components from its general MIT grant. This work uses
conceptual comparisons; it does not copy implementation code from these repositories.

### Refreshed capability decisions

#### HA1: Skills and activation evidence

- **PROJECT:** Agent Skills, Codex, Awesome Copilot, Superpowers.
- **SUBSYSTEM:** Skill registry and evaluation (matrix H01-H04).
- **FEATURE:** Portable metadata, progressive disclosure, independent activation tests.
- **HOW IT WORKS:** The skill specification separates discovery metadata, body and resources.
  OpenAI guidance tests direct, indirect, incomplete, negative and edge-case activation.
  Copilot has separate skill/plugin validators; Superpowers compares behavior before and
  after instructions. These establish distinct structural and behavioral test layers.
- **WHY EFFECTIVE:** Valid metadata alone does not prove correct routing or better work.
- **ORQALIS CURRENT STATE:** Trusted roots and pinned body/resource hashes; deterministic
  routing witnesses, role/pin denial checks and staged byte measurements exist.
- **GAP:** Live behavioral improvement and internal-worker reference execution remain unmeasured.
- **ADAPTATION:** Retain the explicit registry and deterministic evidence; keep optional live
  model comparisons separate from routing and serialized-byte measurements.
- **BENEFIT:** Reproducible activation evidence without silently expanding tool authority.
- **COST:** Low for local fixtures; live evaluation adds provider cost and repeatability work.
- **LICENSE:** Apache-2.0 Agent Skills; MIT Copilot/Superpowers; official OpenAI docs are
  behavior references rather than a product-code license.
- **RISKS:** Calling bytes tokens; treating experimental `allowed-tools` syntax as permission.
- **RECOMMENDATION:** **KEEP/ADAPT current accepted work; DEFER H03 richer provenance and
  internal-worker resource execution, P2.** Bulk plugin installation remains **REJECT**.
- **EVIDENCE:** [Agent Skills specification](https://agentskills.io/specification),
  [OpenAI skill testing](https://developers.openai.com/plugins/build/skills),
  [pinned Copilot validators](https://github.com/github/awesome-copilot/blob/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c/package.json),
  [pinned Superpowers test procedure](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/writing-skills/testing-skills-with-subagents.md).

#### HA2: Hooks are host adapters, not Orqalis authority

- **PROJECT:** Codex and Claude Agent SDK.
- **SUBSYSTEM:** Hooks/native harness (H05, I04).
- **FEATURE:** Lifecycle callbacks and tool interception.
- **HOW IT WORKS:** Codex documents command and MCP-tool hooks with trust requirements.
  MCP hooks use an existing connection; unavailable servers/tools and hook errors do not
  block the operation. Claude documents event and decision contracts with host-specific behavior.
- **WHY EFFECTIVE:** Adapters can observe or request bounded actions at explicit boundaries.
- **ORQALIS CURRENT STATE:** Application policies, approvals, typed events and MCP work gates
  enforce authority; `external_cli` remains a host transport contract, not a native launcher.
- **GAP:** No tested native event/permission/cancellation mapping exists.
- **ADAPTATION:** Any future hook can call scoped services or add bounded context; it must
  not bypass the existing approval and recovery services.
- **BENEFIT:** Preserves one auditable workflow authority across changing host features.
- **COST:** Medium/high to qualify event ordering, failure behavior and executable trust.
- **LICENSE:** Claude SDK MIT; native products and documentation have separate terms.
- **RISKS:** Host fail-open errors, concurrent hooks and different cancellation semantics.
- **RECOMMENDATION:** **DEFER H05/I04, P2**, until one concrete host workflow has full tests.
- **EVIDENCE:** [OpenAI hooks](https://learn.chatgpt.com/docs/hooks),
  [Claude Agent SDK hooks](https://code.claude.com/docs/en/agent-sdk/hooks).
  OpenAI sources were searched and fetched using the OpenAI Docs workflow.

#### HA3: Supported assistant contract and bounded continuation

- **PROJECT:** MCP SDK, Codex, VS Code/Copilot, OpenCode and Goose.
- **SUBSYSTEM:** Assistant integrations and lifecycle (I01-I03).
- **FEATURE:** Root-bound discovery, read/work policy and durable continuation.
- **HOW IT WORKS:** Hosts configure MCP transports, discover tools and apply their own trust
  and permission UI. VS Code workspace server trust now follows Workspace Trust; other
  sources may have separate server decisions. MCP protocol pagination uses opaque cursors.
- **WHY EFFECTIVE:** A shared service contract separates assistant UX from durable project state.
- **ORQALIS CURRENT STATE:** Generic stdio and replacement-client contracts, scoped lifecycle
  controls and task-history paging exist. Direct-factory scope guards now cover decision
  memory and configured skill/catalog reads, including SDK-A/policy-B denial tests.
- **GAP:** Native Codex/Claude/Copilot/OpenCode/Goose sessions have not been qualified.
- **ADAPTATION:** Continue contract tests for read-only denial, explicit work authority,
  idempotency, uncertain-outcome recovery, stale/cross-root cursor rejection and client replacement.
- **BENEFIT:** Reusable integration semantics without importing multiple native launchers.
- **COST:** Low for generic MCP; medium for each actual host/version qualification.
- **LICENSE:** MCP SDK/OpenCode MIT; Goose Apache-2.0; product licenses separate.
- **RISKS:** Protocol-level pagination must not be confused with `list_task_page` application
  cursors, whose root/revision contract deliberately survives reopening unchanged state.
- **RECOMMENDATION:** **KEEP/ADAPT I01-I03, P1 evidence pending; DEFER native host launchers.**
- **EVIDENCE:** [OpenAI MCP configuration](https://developers.openai.com/learn/docs-mcp),
  [VS Code MCP trust](https://code.visualstudio.com/docs/agent-customization/mcp-servers),
  [MCP pagination](https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination),
  [OpenCode MCP](https://opencode.ai/docs/mcp-servers/),
  [Goose extensions at pin](https://github.com/block/goose/blob/04ed836c8cde23e540cc77d256992e00be99298b/documentation/docs/getting-started/using-extensions.md),
  `tests/unit/test_mcp_project_scope.py`, `tests/integration/test_mcp_lifecycle.py`.

#### HA4: Trace identity, UI ancestry and exporter scope

- **PROJECT:** OpenHands, Langfuse, OpenTelemetry.
- **SUBSYSTEM:** Control Center and telemetry (T01-T06).
- **FEATURE:** Backend-owned state, inspectable operations and correlated timing.
- **HOW IT WORKS:** OpenHands separates Agent Canvas, Agent Server and SDK responsibilities.
  Langfuse exposes typed nested observations; OTel defines span/trace context and links.
- **WHY EFFECTIVE:** Per-operation identity makes omissions and misleading aggregation visible.
- **ORQALIS CURRENT STATE:** Durable run/phase/attempt/actor/model/tool ancestry, local safe
  span attributes, keyboard navigation and critical-path cues use actual persisted fixture data.
- **GAP:** No network exporter or native-host trace propagation has been qualified.
- **ADAPTATION:** Keep local projection tests. A future exporter must distinguish a tool
  caused by a completed model call from a temporally nested child span. Local UUID-prefixed
  hierarchy IDs are not automatically W3C trace/span IDs.
- **BENEFIT:** Honest causal inspection without external storage as a prerequisite.
- **COST:** Local UI already implemented; export mapping adds medium testing/privacy work.
- **LICENSE:** OpenHands MIT; OTel Apache-2.0; Langfuse has explicit component exclusions.
- **RISKS:** Raw private reasoning export, estimated cost presented as reported cost, or
  summing concurrent activity into elapsed time. Generic upstream payload-capture guidance
  does not override Orqalis data minimization.
- **RECOMMENDATION:** **KEEP/ADAPT T01-T04; DEFER T05 exporters, P2; REJECT mandatory hosted
  telemetry and private reasoning storage (T06).**
- **EVIDENCE:** [Pinned OpenHands component boundaries](https://github.com/OpenHands/OpenHands/blob/47a10808d78561546a02555d0d2c7fa96fa96300/README.md),
  [Langfuse trace structure](https://langfuse.com/docs/observability/best-practices),
  [Langfuse data model](https://langfuse.com/docs/observability/data-model),
  [OTel trace concepts](https://opentelemetry.io/docs/concepts/signals/traces/),
  `web/src/fixtures/runtime-trace.json`, `web/e2e/trace.spec.ts`.

#### HA5: Evaluation integrity before improvement claims

- **PROJECT:** Promptfoo, Superpowers; Orqalis native evidence pipeline.
- **SUBSYSTEM:** Evaluation (E01, H02).
- **FEATURE:** Frozen inputs, explicit semantics and independent outcome witnesses.
- **HOW IT WORKS:** Deterministic assertions and fixed comparisons qualify specific behavior;
  behavioral model evaluation is a separate experiment.
- **WHY EFFECTIVE:** An improved-looking aggregate cannot hide missing records or changed inputs.
- **ORQALIS CURRENT STATE:** Source-isolated quality and execution harnesses, raw JUnit,
  held-out/engineering partitions, negative cases and strict per-case comparisons.
- **GAP:** Full final-source comparative captures remain pending; original captures contain
  unresolved failures and earlier provenance limitations.
- **ADAPTATION:** Preserve raw failures; freeze explicit compatibility profiles; bind helper,
  source, dataset, test and environment hashes; join invocation IDs to persisted events.
- **BENEFIT:** Reviewable engineering evidence without declaring fake-provider runs model success.
- **COST:** Modest local test/capture time; no paid model or hosted service required.
- **LICENSE:** Promptfoo/Superpowers MIT concepts; native harness implementation.
- **RISKS:** Post-hoc label changes, implicit waivers, single-run timing and weakened counters.
- **RECOMMENDATION:** **ADAPT/ADD E01/H02, P1; DEFER paid judge studies (E03).** No global
  or per-workload improvement claim is made by this audit.
- **EVIDENCE:** [Promptfoo assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/),
  [benchmark reproduction guide](../../../benchmarks/README.md),
  `tests/unit/test_quality_comparison.py`, `tests/unit/test_execution_benchmark.py`.

### Concrete local findings and verification

1. **P1, fixed with focused regression:** MCP `get_decisions`, capability catalog and skill
   body/resource reads omitted project binding in a direct programmatic factory. SDK-A /
   policy-B now fails before data access. Focused MCP regression: 1 passed; Ruff/mypy clean.
2. **P1, fixed in benchmark:** one successful model record could satisfy the execution
   check despite the nine-call fixture. Canonical record/projection UUID uniqueness, exact
   start/terminal-event correspondence, status/time/actor/run/attempt consistency, expected
   model role counts (architect 2, developer 4, repair 1, reviewer 2), and two developer
   write/tool-parent witnesses are now checked. 33 focused tests passed. Baseline smoke-v2
   passed; its timing remains explicitly unqualified. Current smoke awaits source preflight.
3. **P1, fixed in contract provenance:** the runner previously recorded its own hash without
   the imported quality-helper hash. Contract schema 2 compiles exact captured helper bytes,
   records their hash and checks helper/runner/dataset stability. Comparator rejects old
   helperless or mismatched captures. 40 tests passed, including an actual helper mutation
   that retains JUnit and produces failed stability evidence. The old runner is archived
   as `contract-runner-before-helper-binding.py.txt`; old active captures remain preflight.
4. **Harness environment failure, fixed:** isolating Git configuration exposed repository
   ownership mismatch in the immutable-corpus `git show` command (exit 128). Only that
   read-only command now trusts the exact resolved repository through command-scoped
   `-c safe.directory=...`. No global/wildcard trust was written. Bytes match the immutable
   export; 30 quality tests passed immediately after that isolated correction.
5. **Explicit compatibility change, retained evidence:** baseline graph tests equated all
   CALLS/EXTENDS targets with extracted certainty. Shared compatibility-v1 pins legacy vs
   source-ast-v4 semantics and strengthens source/target/evidence witnesses. Compatibility-v2
   separately pins source-ast-v5 after the parser byte-position correction. Both versions
   preserve original structural/cache assertions, dataset labels and selected declarations.
   Each amended graph node passed on both isolated sources; no skips or xfails. Generator
   tests: 17 passed. Frozen collect-only contains 86 nodes across 14 files.
6. **P1 discovered during root quality preflight, not closed by this audit:** native parser
   crash in the real MetricsView/types corpus led to a source-ast-v5 byte/LF correction.
   Root owns the reproducer and regression qualification. Old current full-suite captures
   crossing that edit cannot establish final-source stability.
7. **P2 retained limit:** bounded MCP responses do not bound total local backend work.
   Symbol discovery refreshes the graph before query validation; memory navigation can parse
   complete canonical records before response truncation. Do not claim constant I/O or RAM.
8. **P2 measurement qualification:** `--mode capture` represents externally coordinated quiet
   execution; it is not an automatic machine-idleness measurement. Smoke timings and the
   single repair fixture cannot establish a general latency or autonomous-success improvement.
9. **Harness environment failure, fixed without weakening assertions:** original baseline
   contracts finished with 84 passes and 2 failures. One failed committed-file assertion
   observed Windows CRLF after user Git configuration was removed. The quality/contract
   helper now sets process-scoped `core.autocrlf=input`; a real committed CRLF fixture test
   proves LF Git blob bytes, unchanged worktree bytes, and no local/global config mutation.
   Inherited Git overrides remain scrubbed. The other original failure is a cancellation
   monitor/state-lock timeout; runtime diagnosis remains separate. Original JUnit is retained.
10. **Strict script gate, fixed:** all 12 scripts now pass strict mypy with explicit types
    and no filewide ignores. Timed callables preserve result types; dynamic JSON boundaries
    are explicit, optional contract evidence is narrowed, and child-launch interception
    remains covered by actual subprocess tests. Ruff check/format and 40 quality tests pass.

### Required next evidence and defer review

Keep original failing full captures and compatibility-v1 captures as raw preflight. After
production source and scripts freeze, both revisions must use the same compatibility-v2
root and helper-bound runner. Resolve unrelated failures normally; a graph-semantic
amendment cannot excuse runtime/evidence-policy failures. Then perform quiet comparative
captures and inspect per-case regressions before claiming improvement. Do not run qualified
timing captures while the full suites are active.

The refreshed references do not justify reopening deferred arbitrary hooks, native launchers,
marketplace installation, hosted exporters or paid model judging. Each still needs its own
concrete workload, authority/privacy contract and qualification evidence. No deferred item
is represented as implemented or silently removed from the registry.

---

### Final scoped audit: harness and interfaces

Audit date: 2026-09-26. **No new P0/P1 implementation defect found in this bounded harness review.**
This is a candidate audit, pending global qualification. It does not count as one of the
required clean full iterations while final regression, shared compatibility-v2 contracts,
quiet comparative measurements, and cross-subsystem findings remain unresolved.

The inspected production fingerprint is
`a37dda9e2ca4d37e58ffc6fcab606324df31e16b02dc1261a3371cd44792a757`, matching the
provisional source freeze at 16:50:12 UTC. Baseline remains immutable
`b8506f7d9c471516fe4b21c9caa735a7a7909af6` / `v2.0.0`.
The [input ledger](../evidence/final-audit-1-harness-inputs.json) binds the package inventory,
individual inspected backend/frontend/harness files, frozen dataset and upstream revisions.
No production source was changed during this audit.

#### Accepted capability review

| Capability / decision | Concrete acceptance evidence reviewed | Candidate assessment and qualification boundary |
| --- | --- | --- |
| H01 portable skills / ADAPT | `markdown.py`, `registry.py`, portable-skill tests: strict frontmatter, trusted roots, tool requirements, metadata/body separation, hash pins, bounded text resources | Implemented. Tool names constrain selection; they cannot grant permissions. Scripts and remote resources are not executed. Windows symlink privilege skip remains explicit below. |
| H02 skill evaluation / ADD | `benchmark_quality.py`, `compare_quality.py`, frozen routing/selection expectations, portable body/resource equivalence and actual serialized disclosure bytes | Deterministic routing and content/budget evidence exists. Final comparative capture pending; no model instruction adherence, token or engineering-success claim. |
| I01 supported assistant contract / ADAPT | Root/policy-bound MCP configuration, capability discovery, typed errors, separate clients reopening the same project store; child-import guard for contract tests | Generic MCP interface is supported. No native Codex, Claude Code or Copilot launch certification. Installed-package qualification is separate from source-injected CLI tests. |
| I02 lifecycle controls / ADD | Work policy, bound run/project, nonblank bounded idempotency keys, Core pause/resume/cancel/recovery calls; all three lifecycle integration tests passed at this source | Repeated transitions preserve event counts; conflicting keys, wrong project, readonly policy, active lease and missing uncertainty acknowledgement deny. Recovery never replays an uncertain effect. |
| I03 bounded discovery / ADAPT | Compact task pages, exact root/index-revision cursors, stable timestamp/ID ordering, malformed/stale/cross-root rejection; graph traversal budgets and typed witnesses | Four history tests passed. Pagination bounds responses; it does not remove index rebuilding or guarantee constant backend work. Old tools remain available. |
| T01 local correlation / ADAPT | Persisted run/phase/attempt/actor/model/tool identities; event-based phase attribution; UUID-only span annotations; shared-session and historical fallback test | Implemented causal projection with explicit missing durations. Prior actual parallel/repair fixture test validates restart and in-memory span IDs. No network-export or W3C propagation claim. |
| T02 trace/critical-path UI / ADAPT | `TraceView`, `Timeline`, backend path IDs, actual persisted fixture, component tests, keyboard/mobile browser test | UI projects backend facts. Existing browser trace test routes a saved actual snapshot; it is not evidence of live HTTP/WebSocket latency. Final live correlation benchmark is separately pending. |
| T03 provider metrics / ADAPT | Provider/model grouping, every invocation outcome, nearest-rank p50/p95, usage/cost coverage and zero-versus-unknown tests | Missing values remain unknown; counts and latency have recorded coverage. Provider success is not acceptance success. No invented prices or tokens. |
| E01 evaluation integrity / ADD | Full source/resource inventory, helper/runner/dataset stability, environment/dependency comparability, frozen corpus, per-case ranking and negative witnesses, JUnit accounting, event/record identity joins | Hardened harness is ready for final captures. 40 quality tests, 33 execution accounting tests and 17 compatibility-generator tests are earlier focused evidence, not a summed unique full-regression count. |

`get_decisions`, capability and skill reads now validate the configured project before
returning data. The direct SDK-A/policy-B test passed against this freeze. Memory proposals
remain governed by the server work policy and configured review policy; MCP exposes no
operator approval tool. Symbol bodies require discovered hashes and exact IDs; reference
results explicitly describe static candidates. Knowledge-specific correctness is covered
by the independent knowledge audit.

#### Fresh verification and its limits

The [isolated focused run](../evidence/final-audit-1-harness-tests.json) completed **30 passed,
1 skipped**, with unchanged source fingerprint before/after. Raw [JUnit](../evidence/final-audit-1-harness-tests.junit.xml)
and [log](../evidence/final-audit-1-harness-tests.log) are retained. It covers portable skills,
MCP project isolation, four task-history cursor cases, historical trace fallback and all
three MCP lifecycle integration tests. Its skipped test is
`test_skill_symlink_parent_is_rejected`: this Windows account cannot create symlinks.
The JUnit aggregate correctly remains `passed=false` when a skip exists; the skip is not
silently counted as coverage or converted to a successful contract result.

A separate [real Windows junction probe](../evidence/final-audit-1-harness-junctions.json)
verified refusal of both a junction trusted root and a resource parent junction, at the
same stable source. The probe created only owned temporary paths and removed only its
junctions. This confirms the Windows reparse-point path in use; it does not relabel the
separate symlink-privilege skip as a pass.

The scripts pass strict mypy with explicit types and no filewide ignores; Ruff check and
format verification passed. The unchanged original Git failure passed on both isolated
sources under the explicit process-scoped `core.autocrlf=input` policy. Its
[focused evidence](../evidence/git-fixture-policy.json) binds test/helper/source hashes.
The corpus read trusts only the exact repository through command-scoped `safe.directory`;
no global Git policy or wildcard trust is written.

Execution accounting now requires exactly nine model invocations with independent role
counts (architect 2, developer 4, repair 1, reviewer 2), two developer file writes, unique
persisted IDs, matching projections and exact started/completed event correspondence.
The baseline strengthened smoke passed; quiet final-source execution capture has not yet
run. Its prior one-record false-PASS case is retained as a negative unit test.

#### Upstream refresh and deferrals

At **16:51:54 UTC**, all twelve public `git ls-remote HEAD` results matched the previous
16:21:58 audit. The fresh GitHub metadata calls returned HTTP 403, so this refresh makes
no new maintenance-flag assertion. The earlier successful metadata, exact commit dates
and pinned license hashes remain available in the
[iteration-1 ledger](../evidence/harness-upstream-iteration-1.json), at the same immutable commits.

- [agentskills/agentskills](https://github.com/agentskills/agentskills/commit/69ef37e9424c0a7ea9dd2293b559e43ec8176379): `69ef37e9424c0a7ea9dd2293b559e43ec8176379` ? unchanged.
- [github/awesome-copilot](https://github.com/github/awesome-copilot/commit/6c4d33b9cfca967a28bb2962ef4d55e4a384c88c): `6c4d33b9cfca967a28bb2962ef4d55e4a384c88c` ? unchanged.
- [obra/superpowers](https://github.com/obra/superpowers/commit/8ca22dba9a94f28898bbce59f2537ff4d87c747d): `8ca22dba9a94f28898bbce59f2537ff4d87c747d` ? unchanged.
- [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python/commit/36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6): `36f95486ee9fc49d8ee1ed56811f07b5e8e23ac6` ? unchanged.
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk/commit/f1b6589088534632fef92238ee9750951e3c0185): `f1b6589088534632fef92238ee9750951e3c0185` ? unchanged.
- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/commit/f46d9578190b476b3501923ea8977d899e8db2cb): `f46d9578190b476b3501923ea8977d899e8db2cb` ? unchanged.
- [anomalyco/opencode](https://github.com/anomalyco/opencode/commit/a42f393c850bec0c0f395fb91bf19b1ee8b31666): `a42f393c850bec0c0f395fb91bf19b1ee8b31666` ? unchanged.
- [block/goose](https://github.com/block/goose/commit/04ed836c8cde23e540cc77d256992e00be99298b): `04ed836c8cde23e540cc77d256992e00be99298b` ? unchanged.
- [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands/commit/47a10808d78561546a02555d0d2c7fa96fa96300): `47a10808d78561546a02555d0d2c7fa96fa96300` ? unchanged.
- [langfuse/langfuse](https://github.com/langfuse/langfuse/commit/66f6226131714eb73cc88c3ccc4b851cd7b63c89): `66f6226131714eb73cc88c3ccc4b851cd7b63c89` ? unchanged.
- [open-telemetry/opentelemetry-specification](https://github.com/open-telemetry/opentelemetry-specification/commit/cac5b81ebcfdecb272bb4e2d31f885b7142207d9): `cac5b81ebcfdecb272bb4e2d31f885b7142207d9` ? unchanged.
- [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo/commit/9110c25c495de6f43b40c9b22c900e819555f27c): `9110c25c495de6f43b40c9b22c900e819555f27c` ? unchanged.

The prior [structured project comparison](#harness-audit-iteration-1) retains capability,
adaptation, cost, license and risk details. Primary host boundaries remain the
[Codex skills specification](https://developers.openai.com/plugins/build/skills),
[Codex hooks documentation](https://learn.chatgpt.com/docs/hooks),
[Claude Agent SDK hooks](https://code.claude.com/docs/en/agent-sdk/hooks),
[VS Code MCP trust model](https://code.visualstudio.com/docs/agent-customization/mcp-servers),
[MCP pagination specification](https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/pagination),
and [OpenTelemetry trace concepts](https://opentelemetry.io/docs/concepts/signals/traces/).
Host trust and interruption behavior remain distinct from Orqalis application authority.

Deferred H03 metadata/environment polish, H05 arbitrary hooks, I04 native subprocess
workers, I05 remote issue/PR writes, T05 exporters and E03 paid judge evaluation remain
**DEFER**. Each still needs a concrete workload and its own policy/qualification contract.
Rejected bulk installation, implicit script execution, mandatory hosted telemetry and
private-reasoning storage remain **REJECT**. Fresh upstream HEADs provide no evidence
that justifies changing those decisions. No third-party implementation was copied.

#### Retained failures and global blockers

Original full contracts finished 84 passed / 2 failed on each source. Baseline failures
were cancellation-poll lock contention and Git CRLF; current failures were Git CRLF and
the old graph-certainty assertion. The strict shared compatibility-v2 amendment records
both declared parser profiles and preserves structural/cache assertions and frozen labels.
It does not waive the separate runtime failure.

The stale compatibility-v1 baseline completed naturally with **84 passed / 2 failed** in
2845.62 seconds: the `missing_text` external-finding case hit a state-lock timeout and the
Git CRLF assertion failed. Its runner changed, so it has raw JUnit and an
[unqualified summary](../evidence/baseline-contracts-v1.raw-summary.json), not valid comparison JSON.
The stale current v1 process was stopped after explicit owned-tree verification; its
[incomplete summary](../evidence/current-contracts-v1.raw-summary.json) preserves the observed
failure marker and unknown final counts. No JUnit or PASS was manufactured. The
[process ledger](../evidence/contracts-v1-owned-process-trees.json) and
[stop verification](../evidence/contracts-v1-stop-verification.json) show the exact roots,
creation times and absence of remaining recorded descendants. No broad process-name kill
was used; baseline finished before its termination guard and was not killed.

Root's broad current preflight completed with a separate concurrency lock-gate timeout.
Runtime diagnosis is still active. Therefore this bounded harness review cannot declare
global convergence, close that failure, or authorize a clean full-iteration count. Final
baseline/current contracts must use the identical compatibility-v2 tree and stable schema-2
helper/runner, followed by coordinated quiet measurements and per-case acceptance review.
No heavy job remains running from this audit.

Remaining P2 limitations are explicit: output bounds do not bound all graph/memory/index
backend work; local causal IDs are not W3C span IDs; causal tool ancestry can extend beyond
a model call's wall interval; small timing samples do not establish tail guarantees; and
primary-path precision labels are not exhaustive relevance judgments. None is presented
as a completed deferred feature or a broad model-quality improvement.
