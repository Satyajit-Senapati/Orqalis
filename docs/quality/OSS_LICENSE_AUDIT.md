# Open-source license audit

Inspected 2026-09-26. This records component notices and Orqalis reuse decisions. A public
repository is not blanket permission to redistribute its code. **No upstream implementation
code or skill prose has been copied into Orqalis.** Adaptations are original implementations
of architectural patterns. Dependency wheels retain upstream licensing separately.

## Reference-license refresh - 2026-10-03

[Current refresh disposition](evidence/release-upstream-refresh-20261003-independent-disposition-v1.json)
and its pinned license supplement record exact-HEAD README/root-license checks for
all40 linked references. Mixed component notices remain distinct; Agent Skills code
and documentation have different licenses, and historical Daytona has no current
root license and is archived/unmaintained. These concept-only references add no copied
implementation or skill prose. Changed source and every nested component were not
comprehensively audited. This reference refresh does not replace the separate fresh
installed wheel/npm dependency, bundled-notice and advisory gates for candidate2.1.0.

## Release installer payload - 2026-10-02

The npm release bundles the unmodified, hash-locked `pip-26.2.1-py3-none-any.whl`
for an offline installer upgrade before network use. Its distribution metadata declares
MIT and its complete wheel retains upstream and vendored copyright/license payloads
(44 license/copying paths). [Exact payload inventory](evidence/release-bootstrap-license-payload.json)
binds the wheel and notices. This is an installer dependency; the concept-only rule
for the compared orchestration/memory/framework repositories remains unchanged.

## Reuse rules applied

| Observed terms | Source reuse status for this program | Notices / boundary |
| --- | --- | --- |
| MIT | Permissive source reuse possible after exact component review; none copied | Retain copyright and permission notice in substantial copies/distributions |
| Apache-2.0 | Permissive source reuse possible after exact component review; none copied | Preserve license, applicable NOTICE/attribution and modification notices |
| GPL / AGPL / LGPL components | Conceptual adaptation only in this program | No application code, linking choice or redistribution approved by this audit |
| Mixed / unclear / source-available / commercial | Conceptual comparison only | Review exact component/product terms before any reuse; SDK license does not license the host |
| CC-BY-4.0 documentation | Paraphrased design observations with source links | Code license and documentation license are distinct; no substantial doc excerpts copied |

## Pinned reference component register

Each row below is the inspected component scope, with revision and primary notice evidence.
Unless explicitly described as an installed dependency, the reuse decision is **concepts only**.
The original research records explain activity/maintenance and narrower inspection limits.

### Runtime and security

[Detailed evidence](research/RUNTIME_RESEARCH.md).

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

### Graph and memory

[Detailed evidence](research/KNOWLEDGE_RESEARCH.md).

| Project | Inspected revision | Commit date | License and activity observation |
|---|---|---|---|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify/tree/4139885a1212956cf69a76946fbde0d181ab85e9) | `4139885a1212956cf69a76946fbde0d181ab85e9` | 2026-09-26 | Apache-2.0; `NOTICE` preserves pre-relicensing MIT portions and `LICENSE-MIT`. Current extraction, cache, query and resolution tests. The search result `mbilalnust/Graphify` is an older fork, not the current reference. |
| [Aider-AI/aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | 2026-05-22 | Apache-2.0. Substantial repo-map tests; default-branch commit several months old at inspection, not proof of abandonment. |
| [oraios/serena](https://github.com/oraios/serena/tree/7a2968335f2198b966864de1ce3655c8e485a653) | `7a2968335f2198b966864de1ce3655c8e485a653` | 2026-09-24 | **Application GPL-3.0-or-later; SolidLSP MIT.** Active v2 transition. `src/serena`, its tools/memory manager, application tests and docs are GPL. `src/solidlsp`, `test/solidlsp`, `test/resources` are MIT. Combined distribution is GPL. The license names v1.7.0 / `74c38a65f03fc0764d7ee4b3016ef6a07572ed64` as last MIT release/commit. Do not infer current terms from stale search snippets. |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter/tree/dcdc8cc55e5dfedfc858080835f153999a29ec40) | `dcdc8cc55e5dfedfc858080835f153999a29ec40` | 2026-09-24 | MIT core; grammar and binding licenses require separate checks. Active source and API tests. |
| [microsoft/multilspy](https://github.com/microsoft/multilspy/tree/b9a0ef1bc221e5575787be80493059b01f03c37a) | `b9a0ef1bc221e5575787be80493059b01f03c37a` | 2026-08-20 | MIT client library; language servers have independent terms/runtime dependencies. |
| [sourcegraph/scip](https://github.com/sourcegraph/scip/tree/08b592d981d675d46de9301b50c66ed9064dc759) | `08b592d981d675d46de9301b50c66ed9064dc759` | 2026-09-25 | Apache-2.0 protocol/tooling; language-specific indexers must be assessed separately. |
| [nova-land/coding-agent-memory-mcp](https://github.com/nova-land/coding-agent-memory-mcp/tree/efa89c0e9f2765a71b0e9e31a7127588644fd36a) | `efa89c0e9f2765a71b0e9e31a7127588644fd36a` | 2026-05-30 | MIT; compact TypeScript implementation with `src/test/store.test.ts`; several months since default-branch commit. |
| [xChuCx/agent-memory](https://github.com/xChuCx/agent-memory/tree/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2) | `4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2` | 2026-09-25 | Apache-2.0; actual intended Agent-Memory candidate is named explicitly because the generic name is ambiguous. Active Go implementation, drift/archive/security tests and labeled retrieval eval. |
| [official MCP memory reference](https://github.com/modelcontextprotocol/servers/tree/f46d9578190b476b3501923ea8977d899e8db2cb/src/memory) | `f46d9578190b476b3501923ea8977d899e8db2cb` | 2026-09-22 | Root notice describes transition: new code Apache-2.0, unconsented historical contributions MIT, non-spec documentation CC-BY-4.0. Do not label the entire current tree MIT. Atomic-save, graph and resource tests exist. |
| [letta-ai/letta](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) | `5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a` | 2026-09-10 | Apache-2.0 pointer repository; README explicitly directs current development to letta-code; retired v1 server is on `archive`. |
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code/tree/5e420db9f2871bc3106ba14372d4f8d94c5e63ae) | `5e420db9f2871bc3106ba14372d4f8d94c5e63ae` | 2026-09-26 UTC | Apache-2.0; active current harness with filesystem memory, constraints, conflict, worktree and Windows tests. Local backend exists; cloud is README default. |
| [getzep/graphiti](https://github.com/getzep/graphiti/tree/ba4a9cb32495b6864160616f8dfa2b898f4a500c) | `ba4a9cb32495b6864160616f8dfa2b898f4a500c` | 2026-09-25 | Apache-2.0 current license. Active temporal graph and retrieval implementation. README requires a graph backend and inference/embedding provider; Kuzu adapter is deprecated. |
| [mem0ai/mem0](https://github.com/mem0ai/mem0/tree/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd) | `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd` | 2026-09-25 | Apache-2.0. Active OSS memory SDK with configurable vector backend and SQLite history; hosted product is separate. Current add path uses additive extraction; do not repeat historical blanket claims that every add automatically updates/deletes older facts. |

### Skills, integrations and telemetry

[Detailed evidence](research/HARNESS_RESEARCH.md).

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

### Evaluation

[Detailed evidence](research/HARNESS_RESEARCH.md#evaluation-and-dependency-research).

| Reference | Revision / component | Observed license | Evidence |
| --- | --- | --- | --- |
| Promptfoo | `9110c25c495de6f43b40c9b22c900e819555f27c`, configuration/assertions | MIT | [License](https://github.com/promptfoo/promptfoo/blob/9110c25c495de6f43b40c9b22c900e819555f27c/LICENSE), [configuration reference](https://www.promptfoo.dev/docs/configuration/reference/) |
| DeepEval | `385117c9c46e6935866422b7aa1f67e5e2824472`, evaluation/test cases | Apache-2.0 | [License](https://github.com/confident-ai/deepeval/blob/385117c9c46e6935866422b7aa1f67e5e2824472/LICENSE.md), [single-turn evaluation](https://deepeval.com/docs/evaluation-end-to-end-single-turn) |

## Breadth shortlist with narrower evidence

The first [23-project snapshot](../verification/open-source-projects-2026-09-26.json) also
contains AgentOps, Langflow, Anthropic skills, Codex, Claude Code and GitHub MCP Server.
AgentOps/Langflow/GitHub MCP identify MIT at repository level; Codex identifies Apache-2.0.
Those metadata observations are not a component audit. Claude Code is a commercial product;
its public repository is not equivalent to an open-source host. Anthropic skills must be
checked per skill, including source-available document skills. No source reuse from these
breadth-only entries is accepted. Current official host behavior is linked in harness research.

## Installed dependency register

[Machine-readable wheel/notice research](evidence/dependency-research.json) records PyYAML,
tree-sitter, tree-sitter-javascript and tree-sitter-typescript independently. All inspected
upstream notices are MIT. [Installed distribution evidence](evidence/installed-dependencies.json)
records exact lockfile versions, wheel notices, and installed size: the three parser
packages occupy 3,564,038 bytes on the inspected Windows environment. Runtime advisory
results are recorded in [the Python dependency audit](evidence/python-dependency-audit.json).
Platform wheel availability is metadata evidence, not an executed Linux/macOS qualification. No entire skill catalog, agent framework, database, hosted
observability SDK or semantic graph service is introduced.

## Corrections to stale assumptions

- Serena's current application is GPL-3.0-or-later; its SolidLSP component is MIT.
- Graphify's current Apache-2.0 tree retains notices for earlier MIT portions.
- MCP reference servers have a license transition with MIT historical contributions,
  Apache-2.0 new code and CC-BY-4.0 documentation.
- AutoGen's root documentation license does not replace its MIT code license.
- Daytona's public core is historical and no longer maintained; client component terms differ.
- Langfuse excludes enterprise/third-party components from its general MIT grant.
- Letta's current development moved to letta-code; historical server assumptions are obsolete.

Remaining ambiguity never authorizes copying. Re-pin notices if a component is later reused.
