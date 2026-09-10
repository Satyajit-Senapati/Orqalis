# Orqalis

Orqalis coordinates engineering work through durable goals, dependency-aware plans,
specialized agents, evidence-backed review, bounded repair, Git delivery and Project Memory.

## Install

After this release is published to npm:

```sh
npm install -g orqalis
orqalis version
orqalis --help
```

Requires **Node.js 22+ and Python 3.12+ with venv/pip**. This npm package bundles the
Python application, migrations, skills and compiled Local Control Center. First launch
creates an isolated per-user Python environment and installs hash-locked binary
dependencies from PyPI. An internet connection is required for that initial setup.
No npm install lifecycle script runs; installation also works with `--ignore-scripts`.

Use `orqalis.cmd` on Windows if PowerShell blocks the npm-generated `.ps1` shim.
Set `ORQALIS_PYTHON` to a Python executable path when automatic discovery fails.
Set `ORQALIS_RUNTIME_HOME` to an absolute directory to choose where runtimes are stored.

Normal commands forward directly to the Python CLI. Working directory, arguments,
stdin/stdout and exit status are preserved. Bootstrap diagnostics go to stderr,
so MCP and JSON output remain usable.

## Configure and start

Git, PostgreSQL with pgvector, and Docker for sandboxed execution are still required.
Installation does not start a database, change its schema or configure provider credentials.
Follow the included **GUIDE.md** for database setup, provider keys, a complete task
walkthrough, MCP configuration, acceptance/review gates and troubleshooting.

Once the database is configured:

```sh
orqalis migrate
orqalis doctor
orqalis ui --open
```

The browser UI normally runs at http://localhost:7842 and projects persisted Core state.

## Upgrade and cache

```sh
npm install -g orqalis@latest
```

Each bundle gets a separate runtime. Run database migrations and follow GUIDE.md's backup
instructions before using a newer application against existing data.

Default runtime locations:
- Windows: `%LOCALAPPDATA%/Orqalis/runtimes`
- Linux/macOS: `${XDG_CACHE_HOME:-~/.cache}/orqalis/runtimes`

Python must remain installed; virtual environments depend on their base interpreter.
If that interpreter is removed, stop Orqalis processes, remove the affected runtime
directory and launch again with an installed Python selected.
After interrupted first-time setup, retry. If the launcher reports a stale setup lock,
confirm its owner PID is no longer running, remove only that named `.lock` directory,
then retry. Uninstalling the npm package retains runtime caches and project/database data;
remove old runtime directories only after their processes have stopped.

MIT licensed. Third-party dependencies retain their own licenses.
