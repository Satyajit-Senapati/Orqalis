# Orqalis Consolidation Notes

This v1.2 package reconciles every Orqalis design/handoff artifact created earlier in this session: the original modular bundle, original consolidated DOCX, enhanced modular bundle, enhanced DOCX, Local Control Center additions, sign-off, and Codex handoff.

## Reconciled differences

- The enhanced package added Local Control Center and runtime telemetry requirements; v1.2 integrates them across product, architecture, agents, memory, workflow, interfaces, security, data model, roadmap, implementation plan, sign-off, and Codex handoff rather than leaving them as an addendum.
- Implementation sequencing is normalized. Durable events/timing/projections are Phase 4, thin Mission Control is Phase 5, agent runtime follows, and the full Control Center is Phase 13.
- The previous PR list accidentally placed observability after MCP even though the phase plan required it earlier. v1.2 moves the canonical event/timing foundation before the thin UI and agent execution.
- Duplicate entity terminology is removed: `Event` replaces `Event` + `RunEvent`; `ActorSession` replaces competing `AgentExecution` + `AgentSession`; `TaskExecution` represents attempts while `Task` remains the plan definition.
- The Orchestrator is explicitly modeled/visualized as a first-class runtime actor while remaining the deterministic workflow owner, not an unconstrained coding agent.
- Time semantics are defined for wall/active/waiting/blocked/queue time; nested LLM/tool/test durations are not incorrectly summed as wall time.
- UI progress is explicitly deterministic plan completion, not a model estimate, ETA, or browser simulation. Repair can revise the plan denominator.
- Project Memory now has explicit Project Brain visibility and metrics so the system can measure whether repository re-analysis decreases over time.
- UI security is integrated with the same Policy Engine, loopback-by-default networking, redaction, audit, and chain-of-thought exclusion requirements.

## Supersession rule

Only the files in this v1.2 consolidated package should be handed to Codex as active requirements. Earlier session ZIP/DOCX files are historical inputs and should not be placed beside the canonical package in the implementation repository.


## Owner-approved npm distribution amendment - 2026-09-10

The release owner selected global npm installation and requested removal of redundant
installation routes. ADR 0002, SIGNOFF, CODEX_HANDOFF, the architecture/interface/UI/
release-plan documents now carry this same amendment.
It supersedes earlier wheel/source installation guidance, while preserving Python Core,
SDK contributor setup and all signed-off runtime/security/acceptance invariants.

The original extraction manifest and generated combined Markdown export were removed after
implementation. Their frozen hashes and duplicated content no longer represented the
maintained repository. `SIGNOFF.md`, `CODEX_HANDOFF.md`, these reconciliation notes and the
numbered documents under `docs/` remain the active modular source of truth.
