# Data Model and Observability

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file replaces earlier duplicate `Event`/`RunEvent` and `AgentExecution`/`AgentSession` terminology.

## 1. Modeling rules

- Definitions and executions are separate: `Task` is planned work; `TaskExecution` is an attempt. Agent roles/definitions are configuration; `ActorSession` is runtime activity.
- `Event` is the one canonical append-only runtime event record. There is no separate `RunEvent` entity.
- The Orchestrator and sub-agents are runtime actors. `ActorSession.actor_type` is `ORCHESTRATOR` or `AGENT`.
- Durable workflow tables are canonical state; event/projector tables support audit, replay, telemetry, and UI projections.
- Every mutable/side-effecting record has IDs, timestamps, run/project linkage, and idempotency/audit metadata where relevant.

## 2. Core project and memory entities

### Project
`id, name, repo_uri, repo_root, default_branch, settings, created_at, updated_at`

### ProjectSnapshot
`id, project_id, indexed_commit_sha, created_at, status, repo_fingerprint`

### RepositoryFile
`id, project_id, path, language, role, content_hash, last_seen_commit, metadata`

### MemoryItem
`id, project_id, type, title, content, structured_data, confidence, status, source_commit, introduced_by_run, last_verified_at, superseded_by`

### MemorySource
`id, memory_item_id, source_type, source_ref, content_hash, commit_sha`

### ArchitectureEntity
`id, project_id, entity_type, name, source_refs, metadata`

### ArchitectureRelation
`id, project_id, source_entity_id, relation_type, target_entity_id, confidence, source_refs`

### Decision
`id, project_id, adr_key, title, status, decision, rationale, source_commit, introduced_by_run`

## 3. Run, goal, planning, and evidence entities

### Run
`id, project_id, request, target_branch, base_commit, current_goal_version_id, state, ui_phase, repair_iteration, max_repair_iterations, created_at, started_at, completed_at, last_event_sequence, settings_snapshot`

### GoalVersion
`id, run_id, version, goal, scope, out_of_scope, constraints, assumptions, definition_of_done, created_at, supersedes_goal_version_id`

### AcceptanceCriterion
`id, goal_version_id, key, description, priority, validator_type, validation_spec, status, attempt_count, last_validated_at`

### Task
`id, run_id, plan_version, parent_task_id, description, expected_outcome, status, risk, required_capabilities, preferred_role, provider_constraints, expected_artifacts, validation_method, work_weight`

### TaskDependency
`task_id, depends_on_task_id, dependency_type`

### TaskExecution
`id, run_id, task_id, attempt, assigned_actor_session_id, created_at, ready_at, started_at, completed_at, status, queue_ms, active_ms, waiting_ms, blocked_ms, result_ref`

### Evidence
`id, run_id, task_id, task_execution_id, criterion_id, evidence_type, artifact_ref, structured_data, status, created_at`

### Artifact
`id, run_id, task_id, type, path_or_uri, content_hash, metadata, created_at`

### Finding
`id, run_id, task_id, criterion_id, severity, category, summary, source_ref, status, created_at`

## 4. Runtime actor and invocation entities

### ActorSession
Represents the visible Orchestrator or one sub-agent session.

`id, run_id, actor_type, role, provider, model, status, current_task_id, started_at, completed_at, working_ms, waiting_ms, blocked_ms, tasks_attempted, tasks_completed, tasks_failed, activity_summary, metadata`

The Orchestrator normally has no provider/model. Provider-backed Requirements/Planner/Developer/Test/Reviewer/etc. work is represented by AGENT actor sessions.

### SkillBinding
`id, actor_session_id, task_id, skill_id, skill_version, loaded_at, unloaded_at`

### ProviderInvocation
`id, run_id, actor_session_id, task_execution_id, provider, model, started_at, completed_at, status, input_tokens, output_tokens, cached_tokens, reliable_cost, trace_ref, error_code`

### ToolInvocation
`id, run_id, actor_session_id, task_execution_id, tool_name, tool_class, started_at, completed_at, status, safe_command_summary, artifact_refs, error_code`

### TestExecution
`id, run_id, task_execution_id, suite_or_command, started_at, completed_at, status, passed, failed, skipped, evidence_ref`

### PhaseExecution
`id, run_id, phase, iteration, started_at, completed_at, status, active_ms, waiting_ms, blocked_ms`

## 5. Canonical Event

### Event
`id, project_id, run_id, sequence, event_type, occurred_at, phase, task_id, task_execution_id, actor_session_id, correlation_id, causation_id, status, payload, trace_id`

Properties:
- append-only;
- unique `(run_id, sequence)` with monotonically increasing sequence;
- persisted transactionally with/after the state transition it describes;
- safe to replay for projections/audit, while workflow state remains authoritative;
- payload contains concise structured summaries and references, not secrets or private chain-of-thought.

## 6. Required event taxonomy

Core run/phase: `RUN_CREATED`, `RUN_STARTED`, `RUN_PAUSED`, `RUN_RESUMED`, `RUN_BLOCKED`, `RUN_CANCELLED`, `RUN_FAILED`, `RUN_COMPLETED`, `PHASE_STARTED`, `PHASE_COMPLETED`.

Context/memory: `MEMORY_SYNC_STARTED`, `MEMORY_SYNC_COMPLETED`, `MEMORY_RETRIEVED`, `MEMORY_INVALIDATED`, `MEMORY_PROMOTED`, `CONTEXT_PACK_CREATED`.

Goal/plan: `GOAL_VERSION_CREATED`, `ACCEPTANCE_CREATED`, `PLAN_CREATED`, `PLAN_REVISED`, `TASK_CREATED`, `TASK_READY`, `TASK_STARTED`, `TASK_WAITING`, `TASK_BLOCKED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_CANCELLED`.

Actors/skills/providers/tools: `ACTOR_STARTED`, `ACTOR_STATUS_CHANGED`, `ACTOR_COMPLETED`, `AGENT_ASSIGNED`, `SKILL_LOADED`, `PROVIDER_INVOCATION_STARTED`, `PROVIDER_INVOCATION_COMPLETED`, `TOOL_STARTED`, `TOOL_COMPLETED`.

Validation/review/repair: `TEST_STARTED`, `TEST_COMPLETED`, `EVIDENCE_RECORDED`, `REVIEW_STARTED`, `REVIEW_COMPLETED`, `CRITERION_PASSED`, `CRITERION_FAILED`, `REPAIR_REQUESTED`, `REPAIR_STARTED`, `REPAIR_COMPLETED`, `CHANGE_GUARD_COMPLETED`.

Delivery: `DOCUMENTATION_UPDATED`, `FINAL_VALIDATION_COMPLETED`, `COMMIT_CREATED`, `PUSH_COMPLETED`, `DELIVERY_BLOCKED`.

Security/human actions: `POLICY_DENIED`, `APPROVAL_REQUESTED`, `APPROVAL_RECORDED`.

## 7. Timing semantics

All timers derive from persisted timestamps/status events. Browser timers may interpolate display seconds from a known server timestamp, but refresh/reconnect must recompute from persisted state.

- **Wall time:** elapsed real time from start to end/now.
- **Active time:** intervals in a working/running state.
- **Waiting time:** intervals intentionally waiting for dependencies, provider/tool response, scheduling, or approval as classified by the runtime.
- **Blocked time:** intervals where progress cannot continue without remediation/decision.
- **Queue time:** task `ready_at -> started_at`.
- **LLM/tool/test time:** nested breakdowns; these can overlap with actor/task active time and must not be added to wall time as independent components.

## 8. Progress semantics

Progress is not model-estimated. Each plan version assigns `work_weight` to tasks (equal weight by default). A run's plan-completion percentage is the accepted/succeeded weight divided by total current-plan weight, with explicit handling for skipped/cancelled tasks according to policy. Phase status is derived from workflow state. Repair-generated tasks create a new/revised plan denominator and the UI displays the revision; progress is not forced to remain monotonic.

The UI must label this as **plan completion**, not estimated time remaining or probability of success.

## 9. Projections for API/UI

Maintain query projections/materialized views for:
- run snapshot/header and phase timeline;
- Orchestrator/agent roster with current task and timers;
- task DAG, attempts, blockers, dependencies, and critical path;
- acceptance/evidence/repair linkage;
- timeline/Gantt;
- live activity feed;
- tools/tests/provider usage;
- Git/delivery state;
- Project Brain/memory health;
- historical run/project metrics.

The Local Control Center reads projections through REST and streams new `Event`s via WebSocket/SSE. It never directly mutates projection tables.

## 10. Derived metrics

Run: success rate, wall/active/waiting/blocked time, first-pass acceptance, repair count/time, plan revisions, completion status.

Task: counts by state, queue/active/waiting/blocked/wall durations, first-attempt rate, rework, longest/shortest/average duration, critical-path membership.

Actor/agent: working/waiting/blocked/idle time, utilization, tasks attempted/completed/failed, current task, concurrency.

Parallelism: peak/average active agents, critical-path duration, parallel efficiency, blocked dependency time.

Provider/model: invocations, task outcomes, latency, token usage, reliable cost, errors; later success/cost/repair rate by task type.

Tools/tests: invocation counts, errors, duration, test pass/fail/skip counts.

Memory: hit rate, retrieval latency, context-pack size, repository re-analysis percentage, invalidations, indexed commit freshness, promotions.

Git/delivery: files changed, insertions/deletions, Change Guardian findings, commit/push status.

## 11. Tracing and logging

All operations include `trace_id`, `run_id`, and relevant task/actor/invocation IDs. Provider and tool calls are child spans. Use structured logs correlated to events; do not log secrets, full credentials, or private chain-of-thought. Raw provider prompts/responses are off by default and require explicit local debugging policy plus redaction.

## 12. Retention

Operational events, traces, provider/tool details, and run artifacts have configurable retention. Durable accepted project knowledge, ADRs, provenance, and required audit records follow longer project policy. Retention must not break source provenance for surviving memory items.
