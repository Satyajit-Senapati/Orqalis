# Open-source comparison and enhancement

Reviewed 2026-09-26 against the immutable local-first `v2.0.0` baseline
(`b8506f7d9c471516fe4b21c9caa735a7a7909af6`). Work in this checkout is post-release
and remains under validation. [Current status](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md).

## How references were selected

The initial [23-project GitHub snapshot](verification/open-source-projects-2026-09-26.json)
records observed stars, maintenance metadata, and repository license identifiers. Stars
helped discover candidates; active maintenance, actual capabilities, licensing, and fit with
Orqalis determined decisions. The expanded review pins relevant source revisions and
component notices in the [license audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/OSS_LICENSE_AUDIT.md).

The [50-capability matrix](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/OSS_BENCHMARK_MATRIX.md),
[capability catalog](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/OSS_CAPABILITY_CATALOG.md), and
[accepted backlog](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_BACKLOG.md) are the authoritative decisions.
Each bounded capability receives exactly one KEEP, ADAPT, ADD, REJECT, or DEFER decision.
This is not an exhaustive market ranking or a security audit of every upstream codebase.

## Comparison by use case

| Use case | References and their useful strengths | Orqalis adaptation |
| --- | --- | --- |
| Durable orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) checkpoints; [Temporal](https://github.com/temporalio/temporal) durable execution; [Agent Framework](https://github.com/microsoft/agent-framework) typed workflows | Retain the existing deterministic Orchestrator, Task Capsules, effect receipts, and approval gates. Add real process-death/restart fixtures at eight phase/effect boundaries. |
| Execution isolation | [OpenHands](https://github.com/OpenHands/OpenHands), [SWE-agent](https://github.com/SWE-agent/SWE-agent), [E2B](https://github.com/e2b-dev/E2B) separate agent work from execution environments | Durable local Docker ownership receipts, daemon/label/full-ID checks, and fail-closed cleanup/reconciliation. Remote execution remains deferred. |
| Skills and harnesses | [Agent Skills](https://github.com/agentskills/agentskills) portable format; [Superpowers](https://github.com/obra/superpowers) scoped verification; [Codex](https://github.com/openai/codex) and [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) host contracts | Strict trusted-root SKILL.md adapter, bounded progressive reads, pinned activation content, and existing deterministic tool/role permissions. No bulk skill installation or host instruction takeover. |
| Repository intelligence | [Graphify](https://github.com/Graphify-Labs/graphify) inspectable graph relationships; [Aider](https://github.com/Aider-AI/aider) compact repository context; [Tree-sitter](https://github.com/tree-sitter/tree-sitter) syntax parsing; [Serena](https://github.com/oraios/serena) symbolic navigation | Python AST plus JS/TS/TSX grammars, conservative edge provenance, bounded impact/path queries, hash-verified exact symbol reads, and visible extraction limits. No replacement graph store or LSP write surface. |
| Project memory | [Graphiti](https://github.com/getzep/graphiti) temporal provenance; [Mem0](https://github.com/mem0ai/mem0) selective recall; [Letta Code](https://github.com/letta-ai/letta-code) durable context; [Agent Memory](https://github.com/xChuCx/agent-memory) local recall/drift checks | Reviewed immutable successors, atomic lifecycle transitions, historical reads, bounded discovery/body pages, explicit references, and integrity checks in the existing local store. |
| MCP and assistant continuity | [MCP](https://github.com/modelcontextprotocol/python-sdk), [OpenCode](https://github.com/anomalyco/opencode), [Goose](https://github.com/block/goose) common tool transports | Root-bound lifecycle controls, compact history pages with revision cursors, graph/memory/skill tools through shared services. Native Codex/Claude subprocess workers remain deferred; generic MCP tests do not qualify live hosts. |
| Observability and Control Center | [Langfuse](https://github.com/langfuse/langfuse), [OpenTelemetry](https://github.com/open-telemetry/opentelemetry-specification), [OpenHands](https://github.com/OpenHands/OpenHands) correlated execution visibility | Local run/phase/attempt/agent/model/tool ancestry, critical-path navigation, per-provider/model outcomes and latency/usage coverage. React remains an API projection. No network exporter is enabled. |
| Evaluation and review | [Promptfoo](https://github.com/promptfoo/promptfoo) repeatable comparisons; [DeepEval](https://github.com/confident-ai/deepeval) explicit assertions; verification-first agent workflows | Frozen provider-free engineering queries, deterministic contract evidence, source-isolated baseline/current measurements, honest unknowns, and strengthened test-weakening checks with exact-hash reviewed exceptions. |

Detailed primary-source evidence and acceptance criteria are in the
[runtime/security](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/RUNTIME_RESEARCH.md),
[knowledge/retrieval](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/KNOWLEDGE_RESEARCH.md),
[harness/MCP/telemetry](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/HARNESS_RESEARCH.md), and
[evaluation](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/HARNESS_RESEARCH.md#evaluation-and-dependency-research) reports.

The independent iteration-1 checks are now sections of those same guides:
[harness audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/HARNESS_RESEARCH.md#harness-audit-iteration-1),
[knowledge audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/KNOWLEDGE_RESEARCH.md#knowledge-audit-iteration-1),
and [runtime audit](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/RUNTIME_RESEARCH.md#runtime-independent-audit-iteration-1).
The [ranking and cost review](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/RANKING_REVIEW.md) remains separate
because it evaluates measured outcomes rather than upstream candidates.

## What stays authoritative

Orqalis already has explicit goals, a typed DAG, serialized writers, digest-bound approvals,
criterion-linked acceptance evidence, bounded repair, and durable side-effect records.
Replacing those services with another agent framework would add competing state and policy.
The `.orqalis/` filesystem remains the source of truth; indexes and graphs stay derived.
No mandatory database, vector backend, hosted memory service, or telemetry service is added.

## Dependency and license boundaries

Implementation concepts are adapted independently; upstream project source is not vendored.
New runtime dependencies are PyYAML plus the Tree-sitter Python binding and JavaScript /
TypeScript grammar wheels. Each was checked independently as MIT, including installed
notices and size evidence. See the [dependency register](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/OSS_LICENSE_AUDIT.md#installed-dependency-register).

Repository badges do not grant blanket reuse permission. Serena's application is
GPL-3.0-or-later while SolidLSP is MIT; Langfuse excludes enterprise components; Graphify
retains historical MIT notices within its Apache-2.0 tree; MCP reference servers have a
license transition; Anthropic skills have per-skill terms; Claude Code is commercial despite
its public repository. The Claude SDK's MIT license does not license or qualify its host.

## Limits and further opportunities

Syntax graphs are not whole-program type analysis. Memory supersession is not Graphiti's
bitemporal graph. Standard assertion-loss checks are not a proof that tests are semantically
equivalent. Fake Docker transport checks and process-death fixtures do not qualify a real
Docker daemon. Deterministic retrieval/contract evaluations do not establish live-model task
success, token savings, or a universal performance improvement.

Native assistant workers, remote execution, parallel writers, network trace export,
semantic/vector retrieval, LSP source edits, and remote GitHub write workflows remain
explicit DEFER decisions with entry criteria in the catalog. No remote write or release
publication is part of this enhancement work.

See [usage and limits](05-interfaces-and-integrations.md) and
[recorded validation](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md). Final convergence requires all accepted
P0/P1 items closed and two consecutive clean full benchmark/audit iterations; intermediate
focused tests alone do not establish completion.
