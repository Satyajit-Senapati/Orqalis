# ADR 0001: Durable runtime implementation choices

Status: accepted for workflow/runtime semantics; persistence decision superseded by ADR 0003.
Date: 2026-09-10.

The signed-off architecture remains authoritative. These decisions fill implementation
details without changing its workflow, provider boundary or acceptance contract. As of
2026-09-16, ADR 0003 replaces the PostgreSQL authority and locking details below with the
repository-local filesystem store. They are retained here as historical context.

- **Superseded persistence choice:** PostgreSQL formerly stored canonical Run, GoalVersion,
  Task, TaskExecution, ActorSession, PhaseExecution, Event, Evidence, Finding and Artifact
  records. Current authority is the owning repository's `.orqalis/` Task Capsules and
  filesystem stores.
- **Superseded concurrency mechanism:** row locks and PostgreSQL advisory leases formerly
  serialized writers. Current mutable structured files use atomic replacement and
  project/task filesystem locks; provider/tool work still runs outside short state writes.
- Task.plan_version records the introduction version. Zero identifies preparatory
  Requirements work before a goal exists. Such tasks use the same actor/attempt/event
  models and join the first implementation DAG after the goal is accepted.
  The plan_tasks relation preserves stable task identities across repair/delivery plans.
- The first execution driver uses a deterministic developer/test/reviewer vertical DAG.
  Independent context tasks execute in bounded parallel waves; workspace writers remain
  serialized. Tasks are ordered by DAG dependencies rather than database row order.
- Unknown provider/tool outcomes are not automatically replayed. Explicit recovery
  records acknowledgment and a reason, retires the old attempt, and queues a new attempt
  under the project attempt limit. Goal definitions and old evidence remain unchanged.
- Cancellation propagates to providers and owned command threads. The execution lease
  remains held until cleanup reaches a checkpoint. Windows commands are started suspended,
  placed in an owned kill-on-close job and resumed; POSIX commands use an owned session.
  Docker is an optional isolation boundary; trusted_local is an explicit development
  fallback. Neither is required for persistence.
- Reviewer commands may use a read-only Docker workspace when configured. The independent deterministic
  Change Guardian checks actual scope and hashes before and after documentation.
- Git delivery persists the author identity, tree, message and timestamp before creating
  a commit object. A compare-and-swap update attaches only that commit to the run branch.
  Project policy and delivery policy must both permit a push.
- Provider invocation identity binds committed context facts and permissions, excluding
  worktree dirtiness/confidence hints that change during an attempt. Execution inspects the
  run worktree commit even when the original repository advances to another commit.
- Structured Project Memory is always available. Optional embedding adapters support
  semantic retrieval; absence of embeddings never substitutes an invented relevance score.
- OpenTelemetry exports operation metadata only. Persisted events supply UI statistics.
  Console telemetry is opt-in and writes to stderr, preserving MCP stdout framing.

Current persisted events are structured JSONL inside Task Capsules plus authoritative
snapshots. SQLAlchemy sessions, database transaction types and pgvector do not enter domain
contracts or the shipped implementation; historical SQL adapters have been removed.

No remote UI mode is enabled. Future remote hosting must add authentication and
authorization rather than relax the loopback policy.
