# Agent and Skill Model

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Core distinction

- Agent = role with responsibilities, authority, policies, and output contract.
- Skill = reusable task capability that can be dynamically loaded.
- Tool = executable action such as file read, shell command, test runner, Git diff, or memory query.
- Provider = execution backend such as Codex/OpenAI, Claude/Anthropic, local model, or external coding CLI.

These concepts must remain independent.

## 2. Initial agent catalog

### Requirements Agent
Transforms user intent into a goal, scope, constraints, acceptance criteria, and definition of done. It may identify ambiguities but V1 should prefer safe assumptions when the task is actionable.

### Architect Agent
Evaluates architecture impact, cross-module boundaries, compatibility constraints, and whether an ADR is required.

### Planner Agent
Produces a dependency DAG of typed tasks with expected artifacts, agent capability requirements, validation strategy, and estimated risk.

### Developer Agent
Implements code changes in the isolated workspace. It cannot approve its own work or push to Git.

### Test Agent
Adds/runs unit, integration, UI, static, build, or other deterministic validation as appropriate.

### Reviewer Agent
Evaluates implementation against acceptance criteria using evidence. Read-only by default.

### Change Guardian
Detects out-of-scope or suspicious changes and flags unrelated modifications, accidental deletions, generated files, secrets, or architecture drift.

### Root Cause/Repair Agent
Given failed criteria and evidence, proposes the smallest repair plan. It should not restart the full run unless the plan is invalidated broadly.

### Documentation Agent
Updates docs based on accepted implementation and actual diff.

### GitOps Agent/Service
Prepares a detailed commit message and performs commit/push after all gates pass. Prefer deterministic Git service with an agent generating commit text, rather than allowing an unconstrained Git agent.

### Memory Curator
Promotes durable knowledge from a successful run into project memory with provenance and confidence. It rejects transient implementation chatter.

## 3. Skill schema

Example metadata:

```yaml
id: android-compose
version: 1.0.0
description: Android development with Kotlin and Jetpack Compose
capabilities:
  - kotlin
  - compose
  - material3
  - responsive-layout
applicable_when:
  any:
    - android
    - kotlin
    - jetpack-compose
required_tools:
  - filesystem.read
  - filesystem.write
  - shell.run
  - test.run
constraints:
  - follow repository conventions
outputs:
  - code_changes
  - validation_evidence
```

Skills may include instructions, examples, validation recipes, tool declarations, compatibility constraints, and version metadata.

## 4. Dynamic routing

The Capability Router should operate in two stages:

1. Determine required capabilities from a task.
2. Match capabilities to agent role + skill set + allowed provider.

Selection factors:
- Capability fit.
- Repository/project policy.
- Provider availability.
- Cost/latency limits.
- Security restrictions.
- Historical quality score (later phase).
- Context-window requirements.

## 5. Typed inter-agent messages

Agents should coordinate through structured records rather than unrestricted free-form conversations.

```json
{
  "run_id": "ORQ-2026-001",
  "task_id": "T4",
  "from_role": "architect",
  "to_role": "developer",
  "type": "decision",
  "summary": "Keep sync orchestration centralized in SyncCoordinator.",
  "artifact_refs": ["ADR-014"],
  "requires_ack": true
}
```

Shared findings belong in run state/artifacts, not private conversation histories.

## 6. Provider abstraction

```python
class AgentProvider(Protocol):
    async def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        ...
```

`ProviderExecutionRequest` should contain role, task contract, context pack, selected skills, allowed tools, constraints, output schema, timeout/budget, and trace identifiers.

Provider adapters must normalize:
- Model/agent invocation.
- Tool-call representation.
- Structured outputs.
- Usage/cost metadata where available.
- Cancellation/timeouts.
- Provider errors.

## 7. Provider independence rule

No workflow node should contain logic such as `if provider == "openai"`. Provider-specific behavior is isolated behind adapters and capability metadata.

## 8. Runtime actor and observability contract

The Orchestrator and each sub-agent are visible runtime actors. The deterministic Orchestrator is the workflow owner; sub-agents are worker sessions created for roles/tasks. Each active actor must have a stable runtime/session ID and emit structured status transitions.

Canonical agent statuses: `STARTING`, `WORKING`, `WAITING_FOR_DEPENDENCY`, `IDLE`, `BLOCKED`, `FAILED`, `COMPLETE`, `CANCELLED`. Task statuses are defined in the workflow/data-model documents.

Every sub-agent session records, where available: role, provider/model, assigned task, loaded skills, allowed tools, start/end timestamps, working/waiting/blocked time, task attempts/outcomes, tool/test/LLM invocation counts, token usage, reliable provider cost, and artifact/evidence references.

Agents may emit concise structured `activity_summary`, `decision`, `finding`, `blocker`, and `result` records for coordination and UI display. These must describe observable work or conclusions and must never contain hidden chain-of-thought, scratch reasoning, secrets, or unredacted sensitive tool arguments.

## 9. Orchestrator visibility

The Orchestrator appears in Mission Control as a first-class actor showing current lifecycle state/UI phase, execution wave, ready/running/blocked/completed task counts, active parallel branches, repair iteration, policy/approval gates, elapsed/active/waiting time, and structured next-transition reason. It does not pretend to be another coding model; provider-backed reasoning used by Requirements/Planner/Repair agents remains represented as those agent sessions.
