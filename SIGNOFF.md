# Orqalis Architecture and Product Design Sign-Off

**Status:** APPROVED CANONICAL BASELINE FOR IMPLEMENTATION  
**Baseline:** Consolidated End-to-End Design v1.2  
**Date:** 2026-09-10  
**Supersedes:** Original Orqalis handoff package and Enhanced v1.1 package from this session.

## 1. Approved product scope

Orqalis is a provider-agnostic, goal-driven multi-agent engineering orchestrator and durable project-intelligence layer. The canonical scope includes Git-aware Project Memory/Context Packs; versioned goals and measurable acceptance criteria; dependency-aware planning/scheduling; specialized agents with dynamic skills; provider abstraction; deterministic Orchestrator-owned state; resumable execution; evidence-based review; bounded targeted repair; Change Guardian; documentation; gated commit/optional push; memory curation; CLI/MCP/REST/WebSocket interfaces; cross-assistant continuity; durable telemetry; and a local browser Control Center.

## 2. Approved Local Control Center scope

The Local Control Center is a core observability/operating surface and a client of Orqalis Core. It must expose:
- the Orchestrator as a visible first-class runtime actor;
- all active/queued/completed/blocked sub-agent sessions, providers/models where known, loaded skills, current tasks, dependencies, and structured activity;
- authoritative run/phase/task/agent wall, active, waiting, blocked, and queue timing;
- deterministic plan completion, phase state, task counts, attempts, blockers, parallelism, critical path, and repair loops;
- acceptance criteria, validators, evidence, failures, and targeted repair linkage;
- tool/test/provider usage, tokens and reliable cost when available;
- Project Brain memory freshness, Context Pack retrieval, provenance, invalidation, and promotion;
- Git diff/documentation/change-guardian/final-validation/commit/push/memory-finalization state;
- historical replay and project/run statistics derived from persisted state/events.

The browser must never simulate workflow truth, fabricate timers/progress, expose private model chain-of-thought, or bypass policy/Git gates.

## 3. Canonical architectural invariants

1. The Orchestrator owns canonical workflow state and state transitions.
2. Agents are specialized workers that return typed results/proposals; they cannot bypass state, evidence, security, or delivery gates.
3. Goals/acceptance criteria are explicit and versioned; material changes after execution begins create a new goal version.
4. PASS requires evidence. Deterministic validation is preferred over model judgment when possible.
5. Repair is targeted, bounded, auditable, and escalates when convergence fails.
6. Project Memory is advisory; source code, Git state, deterministic tools, and validation remain authoritative.
7. Durable memory has provenance, confidence/status, and Git commit association; stale knowledge is incrementally invalidated.
8. Provider and interface independence are architectural requirements. CLI, MCP, REST, UI, Codex, Claude, Copilot, and future clients use one core.
9. External side effects are permissioned, idempotent where feasible, auditable, and behind testable services.
10. Git delivery is gated; force push, protected-branch bypass, destructive cleanup, and secret commits are denied by default.
11. Runtime telemetry is typed, durable, replayable, sequence-ordered per run, privacy-safe, and the sole source for authoritative UI timing/status.
12. The UI is optional for headless execution and cannot become a second workflow engine.
13. Private chain-of-thought/scratch reasoning and secrets are never persisted in memory, events, logs, artifacts, or UI.
14. Process restart/resume is designed from the beginning; completed non-repeatable side effects are not duplicated.

## 4. Canonical implementation sequence

0. Repository/domain/persistence foundation.  
1. Safe Git/project initialization and isolated workspace.  
2. Project Memory MVP and Context Packs.  
3. Versioned goals and acceptance engine.  
4. Planner/DAG/scheduler plus durable event/timing/projection foundation.  
5. Thin Local Mission Control.  
6. Agent/skill/provider framework.  
7. Developer/Test/Reviewer vertical execution slice.  
8. Bounded repair/convergence.  
9. Change Guardian, docs, final validation, commit/push.  
10. Memory curation/finalization.  
11. MCP server.  
12. Cross-assistant/external provider integrations.  
13. Full Control Center.  
14. Security/scale/reliability hardening and release gate.

This ordering is intentional: events/timing are built before the thin UI; the thin UI arrives early enough to observe the runtime; advanced visualization follows a working orchestration vertical slice.

## 5. Canonical terminology decisions

- Use **Event** as the single durable append-only runtime-event entity; do not create a parallel `RunEvent` model.
- Use **ActorSession** for runtime Orchestrator/sub-agent sessions; do not maintain competing `AgentExecution` and `AgentSession` entities.
- Use **Task** for planned work and **TaskExecution** for each attempt.
- Use **GoalVersion** for immutable/versioned execution goals.
- UI percentage means **plan completion**, not ETA or model-estimated confidence.

## 6. Implementation authority

`docs/` and this `SIGNOFF.md` are the architecture source of truth. `docs/09-implementation-plan.md` is the authoritative phase/PR sequence. `CODEX_HANDOFF.md` tells Codex how to execute the plan. `docs/10-local-control-center.md` is the authoritative browser UX/runtime-visualization contract. `docs/07-data-model-and-observability.md` is the authoritative runtime entity/event/timing contract.

## 7. Change control

Material changes to state ownership, goal/acceptance versioning, evidence gates, repair bounds, memory provenance, provider independence, security/Git gates, event/timing semantics, UI truthfulness, or chain-of-thought/privacy policy require an explicit ADR/design amendment before implementation. Ordinary implementation details can evolve within these constraints.
