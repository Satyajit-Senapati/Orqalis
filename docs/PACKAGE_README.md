# Orqalis

Orqalis is a local, provider-neutral engineering orchestrator. It turns a task into
a versioned goal, acceptance criteria and dependency-aware plan, then coordinates
implementation, evidence-backed review, bounded repair, documentation and gated Git
delivery. Project Memory retains curated knowledge with Git-aware freshness checks.

The Python Core is shared by the SDK, CLI, REST API, event stream, MCP server and
React Local Control Center. Agents execute work; the persisted Orchestrator owns
workflow state.

## Install a release wheel

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install /path/to/orqalis-1.0.0-py3-none-any.whl
orqalis version
orqalis --help
```

Python 3.12+ is required. Wheels include the compiled UI, migrations and skills.
Configure Git, PostgreSQL with pgvector, Docker for execution sandboxes, and an
OpenAI or Anthropic provider/model for model-backed work. Then:

```sh
orqalis migrate
orqalis doctor
orqalis ui --open
```

The local UI normally uses http://localhost:7842. It displays persisted actors,
DAG tasks, timings, acceptance evidence, repair state and Project Memory.

The source distribution contains GUIDE.md with complete setup and usage instructions,
docs/OPERATIONS.md for recovery, and docs/MCP.md for assistant integration.
The separately prepared npm launcher exposes the same CLI through npm install -g orqalis
after that package is published. It still requires Python.

MIT licensed. Third-party dependencies retain their own licenses.
