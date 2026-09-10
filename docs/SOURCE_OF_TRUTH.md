# Orqalis Design & Codex Handoff Package

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This package supersedes the original and enhanced Orqalis packages produced earlier in this session.

Orqalis is a provider-agnostic, goal-driven multi-agent engineering orchestrator with durable Git-aware Project Memory, dynamic skills, evidence-based acceptance, bounded convergence, safe Git delivery, and a local browser Mission Control for live orchestration visibility.

## Source-of-truth and read order

1. `SIGNOFF.md` - approved scope, invariants, sequencing, and change-control authority.
2. `docs/00-product-design.md` - product vision, principles, personas, and user journeys.
3. `docs/01-system-architecture.md` - logical architecture, subsystems, deployment, and boundaries.
4. `docs/02-agent-and-skill-model.md` - specialized agents, skills, provider abstraction, and runtime observability contract.
5. `docs/03-project-memory.md` - persistent Project Brain, provenance, Git freshness, and Context Packs.
6. `docs/04-workflow-and-acceptance.md` - state machine, goals, acceptance, task DAG, repair, and delivery gates.
7. `docs/05-interfaces-and-integrations.md` - CLI, MCP, REST/WebSocket, Codex, Claude, Copilot, and local UI integration.
8. `docs/06-security-git-and-governance.md` - permissions, sandboxing, secrets, audit, UI security, and Git policy.
9. `docs/07-data-model-and-observability.md` - canonical persistence entities, event taxonomy, timing semantics, projections, and metrics.
10. `docs/08-features-and-roadmap.md` - consolidated V1/V1.5/V2/V3 feature roadmap.
11. `docs/09-implementation-plan.md` - authoritative phased build plan and PR sequence.
12. `docs/10-local-control-center.md` - Mission Control, orchestrator/agent/task visualization, timers, stats, Project Brain, and delivery UI.
13. `CODEX_HANDOFF.md` - implementation instructions for Codex after the architecture is understood.
14. `CONSOLIDATION_NOTES.md` - reconciliation notes and superseded inconsistencies.

## Product principle

Orqalis is not another coding assistant. It is the durable project-intelligence, orchestration, governance, observability, and delivery layer that coordinates Codex, Claude Code, GitHub Copilot, local models, and future assistants as interchangeable workers or clients.

## Canonical V1 success condition

A user can initialize a Git repository once, submit a task, and have Orqalis: synchronize Project Memory incrementally; create a versioned goal and measurable acceptance criteria; plan a dependency DAG; select specialized agents, skills, providers, and permitted tools; execute safely in an isolated workspace; collect deterministic evidence; review and perform bounded targeted repair; run Change Guardian and final policy gates; update documentation; commit and optionally push to the selected branch; finalize memory against the resulting commit; resume safely after interruption; and expose the entire live run in a local browser with authoritative orchestrator, agent, task, phase, acceptance, timing, telemetry, repair, and delivery state.

The CLI, MCP server, REST/WebSocket API, and Local Control Center are clients of one Orqalis Core. The browser never owns workflow state and never fabricates progress or timing.

## Implementation

Start with the detailed [user guide](../GUIDE.md) for setup, a first task, policies, the UI,
assistant integrations, and recovery.

See [implementation status](IMPLEMENTATION_STATUS.md) for completed capabilities and
[developer setup](DEVELOPMENT.md) for installation, migrations, CLI and checks.

For release artifacts and npm distribution, see [Publishing Orqalis](PUBLISHING.md).
Orqalis is licensed under the [MIT license](../LICENSE).
