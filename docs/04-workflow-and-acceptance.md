# Workflow, Acceptance, and Convergence

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Run lifecycle

```text
RECEIVED
  -> CONTEXT_SYNC
  -> ANALYZING
  -> GOAL_DEFINED
  -> PLANNED
  -> EXECUTING
  -> INTEGRATING
  -> TESTING
  -> REVIEWING
      -> REPAIR_PLANNING -> EXECUTING (bounded loop)
      -> CHANGE_GUARD
  -> DOCUMENTING
  -> DELIVERY_VALIDATION
  -> COMMITTING
  -> PUSHING
  -> MEMORY_FINALIZATION
  -> COMPLETED
```

Additional terminal/intermediate states:
- BLOCKED
- HUMAN_REVIEW_REQUIRED
- FAILED
- CANCELLED
- PAUSED


## 1.1 UI phase projection

The detailed state machine remains canonical. Mission Control projects it into stable user-facing phases:

```text
CONTEXT -> GOAL -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> REPAIR -> DOCS -> DELIVER
```

`REPAIR` appears only while a repair loop is active. `DELIVER` covers final validation, commit, optional push, and memory finalization. The UI phase is a projection; it does not replace detailed workflow states.

## 1.2 Runtime status and progress semantics

Canonical task statuses: `PENDING`, `READY`, `RUNNING`, `WAITING`, `BLOCKED`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `SKIPPED`. Attempt state is recorded separately so repair attempts remain visible.

Overall progress must be derived from persisted task/phase state. V1 should use deterministic plan weights/work units (default equal task weights unless the Planner supplies validated weights) and explicit phase gates. A displayed percentage means plan completion, not an ETA or probability of success. If repair adds work, the plan version/denominator is updated and the UI explains the revision rather than faking monotonic progress.

Wall, active, waiting, and blocked durations are derived from timestamps/status events. LLM/tool/test durations are breakdowns that may overlap with actor working time and must not be naively summed into wall time.

## 2. Goal contract

A goal must include:
- User intent.
- In-scope behavior.
- Explicit out-of-scope behavior when material.
- Constraints.
- Risks/assumptions.
- Acceptance criteria.
- Definition of done.
- Goal version.

Once implementation begins, the goal cannot be silently changed. Material scope changes create a new goal version and are audited.

## 3. Acceptance criterion schema

```json
{
  "id": "AC-003",
  "description": "Application build succeeds.",
  "priority": "required",
  "validator": "command",
  "validation_spec": {
    "command": "./gradlew build",
    "expected_exit_code": 0
  },
  "status": "pending",
  "evidence_refs": []
}
```

Validator types should include command, test-suite, static-analysis, file/diff assertion, structured agent review, manual/human evidence, and later visual/browser validation.

## 4. Planning contract

A task contains:
- ID and parent goal.
- Description and expected outcome.
- Dependencies.
- Required capabilities.
- Suggested role/provider constraints.
- Relevant context references.
- Allowed tool classes.
- Files/modules likely involved.
- Expected artifacts.
- Validation method.
- Risk score.
- Status and attempts.

The planner produces a DAG. Scheduler executes only dependency-ready tasks. Independent tasks may run concurrently when workspace conflict risk is acceptable.

## 5. Integration model

Parallel agents should not blindly write into the same working tree. V1 may serialize write tasks while allowing read/review tasks concurrently. Later phases can use per-task worktrees/patches and an Integrator to merge results.

## 6. Review contract

Reviewer output must be structured:

```json
{
  "overall": "FAIL",
  "criteria": [
    {
      "id": "AC-001",
      "status": "PASS",
      "evidence_refs": ["ev-10"]
    },
    {
      "id": "AC-002",
      "status": "FAIL",
      "reason": "Hard-coded color remains in SettingsScreen.kt:143",
      "evidence_refs": ["ev-11"]
    }
  ],
  "blocking_findings": ["AC-002"],
  "non_blocking_findings": []
}
```

## 7. Repair loop

On failure:

1. Identify only failed criteria and blocking findings.
2. Determine root cause and affected dependency area.
3. Create targeted repair tasks.
4. Re-run affected validations plus required regression checks.
5. Review again.
6. Increment repair iteration.
7. Escalate after configured maximum (default proposal: 5).

The original goal remains stable unless the system enters explicit goal-revision flow.

## 8. Change Guardian gate

After criteria pass, compare actual diff with planned scope. Flag:
- unrelated modules/files;
- deletion spikes;
- lockfile/dependency changes not justified by task;
- generated/binary files;
- secret-like content;
- build/CI/security policy modifications;
- architecture boundary violations;
- test removal/reduction.

A blocking unexpected change returns the run to repair/review.

## 9. Documentation and delivery gates

Documentation runs only after functional acceptance. Before Git delivery, Orqalis re-runs configured final validations on the complete final tree and confirms clean policy state.

## 10. Idempotency and resume

Every state transition and external side effect should have an idempotency key. A process restart must resume from persisted state without duplicating commits, re-running successful non-repeatable actions, or losing evidence.

## 11. Runtime event requirements

Every consequential lifecycle transition must emit a durable event after/with the state transaction. Events use a monotonic per-run sequence for replay. UI reconnect loads a snapshot and resumes from the last sequence. Event payloads contain typed IDs, statuses, timestamps, evidence/artifact references, and concise structured summaries; they never contain private chain-of-thought or secrets.
