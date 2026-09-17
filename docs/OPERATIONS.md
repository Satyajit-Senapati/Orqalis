# Local operation and recovery

Orqalis stores each project's durable intelligence and task history below that repository's
`.orqalis/` directory. Normal operation requires no external database.

## Initialize and inspect

```bash
cd /path/to/repository
orqalis init
orqalis status
orqalis doctor
```

Root resolution is explicit root, `ORQALIS_PROJECT_ROOT`, Git root, then current working
directory. Verify the reported root before operating from scripts, editors or MCP hosts.
Never share one server process across unrelated roots.

`doctor` validates the manifest, schema support, writable structure and project-local
derived data. `status` reports Git and Orqalis project state.

## Run, inspect and resume

```bash
orqalis run "Implement the requested change"
orqalis runs
orqalis runs show <run-uuid>
orqalis runs resume <run-uuid>
orqalis task show <task-id>
```

A request creates its Task Capsule immediately. If execution stops, restart from
`task.yaml`, `execution/state.yaml`, `execution/events.jsonl`, plan and review state. Do not
delete a capsule to clear a lock. Inspect `.orqalis/runtime/locks/`, verify no owner is
active, and use the supported recovery/control command. Run-control commands accept the run
UUID; use `task show` for an `ORQ-...` Task Capsule ID.

## Data ownership and backup

Back up or version the canonical files:

- `.orqalis/manifest.yaml` and `config.yaml`;
- `.orqalis/project/`;
- `.orqalis/memory/` except configured generated presentation;
- `.orqalis/tasks/` according to task-history policy; and
- acceptance evidence and durable delivery records.

`cache/`, `index/`, runtime locks/sessions and generated graph HTML are derived or
ephemeral. They need not be backed up. Removing cache or index content is safe for history;
run `orqalis rebuild-index --repo PATH` to regenerate it. Do not delete manifest, memory or
task capsules as a recovery shortcut.

## Git and branch changes

Task metadata records branch and starting commit. On branch change the graph service
compares manifest state, content hashes and dirty files, refreshes affected nodes, and marks
memory with changed provenance stale. Untracked relevant files participate in analysis.
Generated `.orqalis` content is excluded from repository scanning.

The default tracking policy keeps durable project/memory/task summaries trackable while
ignoring cache, index, runtime, locks, raw event streams and generated graph HTML. Review
`.orqalis/.gitignore` and `config.yaml` before changing policy.

## Memory operations

```bash
orqalis memory status
orqalis memory search "retry policy"
orqalis memory refresh
```

Treat `STALE` memory as a revalidation request, not a fact. Review staged durable proposals
under `.orqalis/memory/staging/` according to `auto`, `review` or `manual` policy. Never put
tokens, passwords, private keys or credential-bearing connection strings in a proposal.

## Control Center

`orqalis ui` or `orqalis serve` starts the project-bound application host. Reconnecting
clients load a snapshot and persisted events before subscribing live. A browser never needs
filesystem access and cannot select another root through a data request.

## Failure cases

- **Missing/invalid manifest:** stop and initialize or repair through schema-aware tools;
  do not guess a project identity.
- **Unsupported future schema:** upgrade Orqalis; never downgrade files in place.
- **Read-only repository:** no mutating operation is safe; copy or fix permissions.
- **Interrupted write:** atomic rename keeps the last valid snapshot; inspect temporary
  artifacts and event history before retrying.
- **Stale lock:** verify the owner/session before recovery.
- **Deleted cache/index:** regenerate; canonical history is unaffected.
- **Cross-project mismatch:** stop the process and relaunch with the intended explicit root.

## Historical database data

The current release contains no PostgreSQL adapter, Alembic schema command or exporter.
Keep legacy backups separate from active `.orqalis/` projects. If records must be recovered,
use the matching archived release or a reviewed one-time external export; never run a
database as a parallel source of truth.

Docker remains optional for isolated command execution. It is unrelated to persistence.
