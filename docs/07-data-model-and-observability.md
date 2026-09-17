# Data model, persistence, and observability

> **Canonical local-first baseline - 2026-09-16.** Filesystem state replaces workflow
> tables as the standard persistence model. Earlier table/migration descriptions are
> historical.

## Domain model remains storage-neutral

Canonical workflow entities remain `Project`, `Run`, `GoalVersion`,
`AcceptanceCriterion`, `Task`, `TaskExecution`, `ActorSession`, `PhaseExecution`, `Event`,
`Evidence`, `Finding`, `Artifact`, provider/tool records, review records, change reports,
and Git delivery. They carry UUID identities and typed state but no ORM session, row ID,
PostgreSQL type, or database transaction concern.

## Filesystem aggregate mapping

Project-level identity/configuration is stored in `.orqalis/manifest.yaml`, `config.yaml`,
and `project/`. Each `Run` maps to one human-readable Task Capsule ID while preserving its
UUID internally:

```text
tasks/ORQ-YYYYMMDD-NNNN/
|-- task.yaml
|-- request.md
|-- context/
|-- goal/
|-- plan/
|-- execution/
|   |-- state.yaml
|   |-- events.jsonl
|   |-- phases/
|   |-- agents/
|   `-- subtasks/
|-- review/
|-- evidence/
|-- artifacts/
|-- changes/
|-- delivery/
`-- final/
```

Only reached stages exist.

## Snapshot plus events

`execution/state.yaml` is the authoritative current aggregate: run, all goal versions,
criteria, evidence, plans, tasks, actors, attempts, phases, approvals, and typed extension
state. Readers do not replay an unbounded log for ordinary access.

`execution/events.jsonl` is the one canonical append-only operational event stream. Events
carry run/project identity, contiguous sequence, type, timestamp, phase/task/actor/attempt
references, idempotency key, structured public payload, and optional trace ID. Hidden
chain-of-thought, prompts, arbitrary private diagnostics, and credentials are not events.

Snapshots are recoverable from relevant events where practical, while events are not used
as a substitute for a consistent current snapshot.

## Atomic transaction and recovery

One short-lived task lock protects a capsule commit. The writer prepares complete document
replacements and an event tail, records checksums in an internal transaction marker, then
rolls the transaction forward. The state snapshot is replaced last. Recovery validates
the marker, verifies document hashes, restores missing replacements, appends only the
contiguous event tail, and removes the marker. This makes retry idempotent after process or
machine interruption.

Mutable project YAML/JSON uses atomic replacement. JSONL append and shared index writes are
locked. A controller lease prevents two workers from driving the same run, while separate
projects proceed independently.

## Human-readable projections

Context, goals, plans, phases, agent sessions, subtasks, acceptance results, findings,
Change Guardian results, artifact metadata, changed files, commit/push state, and terminal
summaries are projections derived transactionally from `state.yaml`. Structured projection
files identify their source/generation; Markdown states that it is non-authoritative.
Corrupt or missing projections do not prevent restart and are regenerated on the next
authoritative commit.

Final projections are created only for `COMPLETED`, `FAILED`, and `CANCELLED`. `BLOCKED`,
`PAUSED`, and `HUMAN_REVIEW_REQUIRED` remain resumable states.

## Project-local indexes

`tasks/index.json` is a compact, rebuildable scan of Task Capsule metadata. The derived
project index contains versioned files, symbols, relations, terms, and task summaries with
artifact hashes and build measurements. It is never authoritative.

Graph/index measurements include files reprocessed, cache hits/misses, graph refresh
duration, document/term counts, and retrieval/context size. A one-file dirty change should
normally reparse that file rather than the repository.

## UI and live observability

The EventBus publishes an event only after persistence commits. A new WebSocket client
receives the authoritative run snapshot and selected historical events before live
subscription. Timing projections derive wall, active, waiting, blocked, idle, and queue
time from canonical phase/task/actor/event state rather than browser timers.

OpenTelemetry is optional and records operation names, outcome, duration, and safe trace
correlation. Console export is opt-in and uses stderr. It excludes request content,
commands, tool output, exception text, credentials, and private reasoning.

## Schema migration

The project manifest carries the filesystem schema version. A migration validates the old
schema, copies affected files to `.orqalis/backups/`, transforms, validates the new schema,
and atomically updates the manifest. Unsupported future schemas fail closed. Alembic is not
used for standard project-store migrations.

Legacy database tables and Alembic migrations are not shipped by the current product. They
do not define current canonical state, and no database exporter command is implemented.
