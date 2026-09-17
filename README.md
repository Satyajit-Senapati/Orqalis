# Orqalis

Orqalis is a provider-neutral engineering orchestrator with durable project memory,
evidence-based review, repair loops, safe Git delivery, MCP integration, and a local
Control Center.

> Orqalis is a local-first, repo-native engineering orchestrator. Each initialized project
> owns its project intelligence and execution history through a structured `.orqalis/`
> directory located in the repository root. External database infrastructure is not
> required for standard operation.

## Install and start

Standard use requires Node.js 22+, Python 3.12+ with `venv` and `pip`, and Git. The npm
launcher creates a hash-verified per-user Python runtime on first use. Docker is optional:
it is used only when an execution policy selects container-isolated commands, never for
Orqalis persistence.

This checkout targets the local-first `2.0.0` release. Use the installation path that
matches the release state. To validate a reviewed, unpublished candidate, install its
exact local tarball:

```sh
npm install -g ./dist/orqalis-2.0.0.tgz
orqalis --version

cd /path/to/your/repository
orqalis init
orqalis doctor
orqalis status
```

After a release owner publishes 2.0.0, install the immutable registry version with
`npm install -g orqalis@2.0.0`. As of the 2026-09-16 candidate audit, public npm `latest`
still resolves to the historical database-backed 1.0.1 release. This repository task does
not publish 2.0.0.

On Windows, `orqalis.cmd` is available when PowerShell blocks the generated `.ps1` shim.
`orqalis init --repo PATH` selects an explicit repository root.

Configure a provider only when a workflow needs one:

```sh
export ORQALIS_OPENAI_MODEL="your-model"
export ORQALIS_OPENAI_API_KEY="..."
# or ORQALIS_ANTHROPIC_MODEL / ORQALIS_ANTHROPIC_API_KEY
```

Credentials stay in environment variables, an OS keychain, or assistant/provider
configuration. They must never be written to `.orqalis/`.

Prepare a run:

```sh
orqalis run "Add feature X" --repo .
orqalis runs
orqalis tasks
orqalis task show ORQ-YYYYMMDD-NNNN
orqalis ui --open
```

`run` persists the request and context before provider execution. Execution and delivery
remain governed by explicit policy documents:

```sh
orqalis execute RUN_ID --policy execution-policy.json --provider openai
orqalis finalize RUN_ID --policy delivery-policy.json
```

Use `orqalis run --help` for supervised gates, explicit goal contracts, branches, and
combined prepare/execute options.

## The project-local store

Initialization creates only useful files and directories. A populated store resembles:

```text
.orqalis/
|-- manifest.yaml
|-- config.yaml
|-- .gitignore
|-- project/
|   |-- identity.yaml
|   |-- summary.md
|   |-- tech-stack.yaml
|   |-- commands.yaml
|   |-- repository.yaml
|   `-- current-state.md
|-- memory/
|   |-- product.md
|   |-- architecture.md
|   |-- technology.md
|   |-- conventions.md
|   |-- domain.md
|   |-- workflows.md
|   |-- testing.md
|   |-- pitfalls.md
|   |-- records/
|   |-- staging/
|   |-- history/
|   `-- graph/
|-- tasks/
|   |-- index.json
|   `-- ORQ-YYYYMMDD-NNNN/
|-- index/
|-- runtime/
`-- cache/
```

The layout is schema-versioned. Files named `.yaml` currently contain formatted JSON,
which is valid YAML 1.2 and avoids a required YAML runtime dependency. Mutable structured
documents are written to temporary files, flushed, validated, and atomically replaced.
Project and task locks live under `.orqalis/runtime/locks/`.

### Canonical and derived data

Canonical data is the source of project continuity:

- `manifest.yaml`, `config.yaml`, and `project/` identity and durable project documents;
- curated memory records, decisions, provenance, and reviewed proposals;
- Task Capsules, including requests, goals, acceptance, execution snapshots, events,
  evidence, reviews, delivery state, and final summaries.

Derived data is disposable and reconstructable:

- repository graph files under `memory/graph/`;
- lexical/search indexes under `index/`;
- parser and ranking caches under `cache/`;
- graph HTML and other generated views.

Deleting `cache/` or `index/` does not delete task history or curated memory. Run
`orqalis rebuild-index --repo PATH` to rebuild graph and lexical index data from the
repository and canonical project records. Idempotent `orqalis init --repo PATH` also
restores missing bootstrap-derived data.

### Git tracking policy

The generated `.orqalis/.gitignore` ignores machine-local runtime state, locks, caches,
derived indexes, generated graph HTML, and raw event streams. Project documents, curated
memory, and durable Task Capsule summaries remain eligible for Git tracking. Configure the
policy in `.orqalis/config.yaml`:

```yaml
{
  "git": {
    "track_project_memory": true,
    "track_task_history": true,
    "track_execution_events": false,
    "track_generated_graph_html": false
  }
}
```

All data stays physically under the repository even when ignored by Git.

## Project root isolation

Every operation binds to one resolved root. Resolution order is:

1. an explicit CLI/API/MCP root (`--repo` or `--root`);
2. `ORQALIS_PROJECT_ROOT`;
3. the current Git root;
4. the current directory when it is not a Git worktree.

Explicit roots are authoritative and fail closed when invalid. Stored paths are
repository-relative where possible, and storage writes are contained under that root.
Run one MCP process per repository, for example:

```sh
orqalis mcp --root /path/to/repo-a --policy /absolute/path/to/mcp-policy.json
```

Another assistant can simultaneously use repo B with its own `--root`; neither process can
retrieve or write the other's `.orqalis/` state.

## Repository graph and local retrieval

`orqalis init` performs a deterministic repository scan. Python source uses AST extraction
for files, modules, classes, functions, methods, tests, imports, calls, and inheritance.
Configuration, documentation, and other supported source files receive typed file nodes.
Edges distinguish `EXTRACTED` facts from `INFERRED` relationships and carry confidence and
evidence.

The graph manifest records branch, HEAD, content hashes, parser version, schema version,
and last indexed time. Refresh compares Git state and file hashes, handles dirty and
untracked relevant files, reparses only changed content, and removes deleted or renamed
paths. Parser results are cached by SHA-256 under `.orqalis/cache/parser/`.

The derived project index writes `files.jsonl`, `symbols.jsonl`, `relations.jsonl`,
`terms.json`, and `task-index.json`. Retrieval combines lexical terms, symbol and path
matches, graph relationships, memory, Git state, and related Task Capsule summaries. No
embedding provider or vector database is required.

## Curated project memory

Repository graph facts, curated knowledge, and task history are separate:

- the graph describes observable repository structure;
- curated memory records why the system is built this way, conventions, terminology,
  constraints, pitfalls, and decisions;
- Task Capsules describe what Orqalis was asked to do and what happened.

Durable memory records carry source paths and hashes, verified commit, originating task,
confidence, and verification time. A record becomes `STALE` when its provenance no longer
matches the repository. Durable updates support `auto`, `review`, and `manual` policy;
reviewed proposals live under `memory/staging/` before promotion. Candidate memory is
scanned for credentials and private diagnostic material before persistence.

Current memory commands are:

```sh
orqalis memory status --repo .
orqalis memory refresh --repo .
orqalis memory search "retry policy" --repo .
orqalis memory graph --repo .
orqalis context "change offline retry" --repo .
orqalis rebuild-index --repo .
```

`memory refresh` explicitly revalidates approved stale records against the current Git
commit; use repeated `--record MEM-...` options to limit revalidation to selected records.

## Task Capsules and recovery

Each request immediately receives `.orqalis/tasks/ORQ-YYYYMMDD-NNNN/`. Its
`execution/state.yaml` is the authoritative current snapshot and
`execution/events.jsonl` is the append-only operational history. Stage projections are
human-readable, recoverable views of the snapshot; they are not competing state.

A mature capsule can contain:

```text
request.md                 task.yaml
context/                   goal/                 plan/
execution/state.yaml       execution/events.jsonl
execution/phases/          execution/agents/     execution/subtasks/
review/                    evidence/             artifacts/
changes/                   delivery/             final/
```

Only reached stages are created. Terminal final files are emitted for completed, failed,
or cancelled runs; blocked, paused, and human-review runs remain resumable. A new process
loads the snapshot, event cursor, DAG, review state, and extensions from files. It does not
need the previous assistant conversation or a database recovery process.

Useful inspection and control commands include:

```sh
orqalis runs --json
orqalis runs show RUN_ID --json
orqalis tasks --json
orqalis task show ORQ-YYYYMMDD-NNNN --json
orqalis runs pause RUN_ID
orqalis runs resume RUN_ID
orqalis runs cancel RUN_ID
orqalis runs recover RUN_ID EXECUTION_ID --reason "..." --acknowledge-uncertainty
orqalis doctor --repo .
```

## Interfaces

CLI, Python SDK, MCP, FastAPI, WebSocket, and the React Control Center share the same
application services and filesystem-backed unit of work. The frontend never reads
`.orqalis/` directly. On connection, the API supplies a persisted snapshot and historical
events, then the EventBus broadcasts live events.

The loopback UI is terminal-owned:

```sh
orqalis ui --open
# or
orqalis serve
```

Closing a browser tab does not stop the host; `Ctrl+C` does. No service or autostart entry is
installed. See [MCP setup](docs/MCP.md), [operations](docs/OPERATIONS.md), and the
[Control Center contract](docs/10-local-control-center.md).

## Security and execution isolation

Orqalis never stores hidden model chain-of-thought. Persisted events are structured
operational records. Requests, context, memory, event payloads, and Task Capsule state are
checked for credential patterns and private diagnostic markers.

Execution permissions are explicit: repository-relative write paths, exact command argv,
timeouts, tool limits, and delivery policy. `trusted_local` runs approved commands on the
host. `docker` provides an optional stronger command sandbox with no network, a read-only
root, dropped capabilities, and resource limits; its image must already exist locally.
Docker is not required for initialization, memory, graph, task persistence, MCP, API, or UI.

## Backup, migration, and upgrades

Back up or commit the durable portions of `.orqalis/` with the repository. Never rely on
`cache/`, `index/`, or `runtime/` as the only copy of important information. Filesystem
schema migrations validate the old manifest, preserve affected source files under
`.orqalis/backups/`, transform and validate the new layout, then atomically update the
manifest.

PostgreSQL, SQLAlchemy, Alembic, psycopg, and pgvector are not part of the current runtime
or package. The former SQL adapters and `orqalis migrate` command have been removed. A
PostgreSQL-to-filesystem exporter is not implemented; preserve legacy data separately and
use the matching historical Orqalis release if a bespoke export is required.

## Development and release

Source contributors should read [DEVELOPMENT.md](docs/DEVELOPMENT.md). Architecture and
ownership rules are in [SOURCE_OF_TRUTH.md](docs/SOURCE_OF_TRUTH.md),
[SIGNOFF.md](SIGNOFF.md), and [ADR 0001](docs/adr/0001-runtime-implementation.md).
Publishing instructions are in [PUBLISHING.md](docs/PUBLISHING.md). Dated verification
records describe the architecture tested at that date and are historical evidence, not
current setup instructions.

Orqalis is licensed under the [MIT License](LICENSE).
