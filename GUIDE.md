# Orqalis User Guide

This guide explains how to use **Orqalis 1.0.0** as a local engineering application.
The signed-off architecture baseline is v1.2; that is a separate version identifier.

Orqalis coordinates work in an isolated Git worktree. It defines a versioned goal,
executes scoped implementation, gathers validation evidence, reviews acceptance, repairs
failures within a budget, checks the diff independently, documents and commits the result,
and curates Project Memory.

The normal workflow has three steps:

1. **Prepare:** define and inspect the goal and acceptance criteria.
2. **Execute:** implement, test, review, and perform targeted repairs.
3. **Finalize:** pass delivery gates, document, commit, optionally push, and update memory.

A prepared goal is not a finished implementation. A passing review is not yet a delivered
commit. Inspect the persisted run state after each command.

## Contents

- [1. Installation and first launch](#1-installation-and-first-launch)
- [2. Configuration and providers](#2-configuration-and-providers)
- [3. Register a project](#3-register-a-project)
- [4. First task walkthrough](#4-first-task-walkthrough)
- [5. Goals and acceptance](#5-goals-and-acceptance)
- [6. Execution and delivery policies](#6-execution-and-delivery-policies)
- [7. Mission Control](#7-mission-control)
- [8. Project Memory](#8-project-memory)
- [9. Control, recovery, and goal revisions](#9-control-recovery-and-goal-revisions)
- [10. Coding assistants and MCP](#10-coding-assistants-and-mcp)
- [11. Python SDK and local API](#11-python-sdk-and-local-api)
- [12. Skills and capabilities](#12-skills-and-capabilities)
- [13. Data, backups, and upgrades](#13-data-backups-and-upgrades)
- [14. Troubleshooting](#14-troubleshooting)
- [15. Command reference](#15-command-reference)

## 1. Installation and first launch

### Requirements

| Component | Purpose |
| --- | --- |
| Python 3.12+ | Core and CLI |
| Git | Repository discovery, worktrees, branches, and delivery |
| PostgreSQL with pgvector | Durable state and Project Memory |
| Docker | Database through Compose and isolated validation commands |
| Node.js 24 and npm | Frontend builds when installing from source |
| OpenAI or Anthropic key plus explicit model | Orqalis-driven requirements, implementation, and model review |

The release wheel includes the compiled frontend, migrations, and skills. Node.js is not
required merely to run that wheel.

Browsing existing runs, searching structured memory, and preparing an explicit goal contract
do not require an LLM key. Model-backed work does. Native assistants can implement through
MCP, but the independent reviewer still needs its configured provider.

### Existing Windows checkout

Open PowerShell:

~~~powershell
Set-Location S:\Orqalis
$orqalis = 'S:\Orqalis\.venv\Scripts\orqalis.exe'

& $orqalis version
docker compose up -d --wait
& $orqalis migrate
& $orqalis doctor
& $orqalis ui --open
~~~

This checkout already has an installed environment and built frontend. A fresh source
checkout needs these steps first:

~~~powershell
npm.cmd ci --prefix web
npm.cmd run build --prefix web
uv sync --frozen
~~~

Use npm.cmd if PowerShell blocks npm.ps1. If uv is not on PATH, this workspace has an
ignored local copy at S:\Orqalis\.tools\uv\uv.exe. Other installations do not need that
development directory.

Later PowerShell examples assume $orqalis points to the installed executable. Set it
again when opening a new terminal. There is no need to activate the environment when
using its absolute executable path.

### Source installation on another machine

From the Orqalis source directory:

~~~sh
npm ci --prefix web
npm run build --prefix web
uv sync --frozen
docker compose up -d --wait
uv run orqalis migrate
uv run orqalis doctor
uv run orqalis ui --open
~~~

Run uv from the Orqalis checkout and identify your target project with --repo. Running uv
inside another Python project may select that project's environment instead.

### Wheel installation

For example:

~~~powershell
py -3.12 -m venv C:\Tools\orqalis-env
C:\Tools\orqalis-env\Scripts\python.exe -m pip install S:\Orqalis\dist\orqalis-1.0.0-py3-none-any.whl
$orqalis = 'C:\Tools\orqalis-env\Scripts\orqalis.exe'
& $orqalis migrate
& $orqalis doctor
~~~

Start PostgreSQL first. The wheel does not start a database. Use the source repository's
compose.yaml or provision PostgreSQL separately, then configure its connection URL.

doctor checks Git availability and database connectivity. It does not authenticate
providers or validate your project-specific Docker image.

## 2. Configuration and providers

Settings come from ORQALIS_ environment variables in the invoking process. Repository
.env files are **not automatically loaded**.

### Configure one provider

For OpenAI:

~~~powershell
$env:ORQALIS_OPENAI_MODEL = 'YOUR_AVAILABLE_MODEL_ID'
$env:ORQALIS_OPENAI_API_KEY = Read-Host 'OpenAI API key' -MaskInput
& $orqalis capabilities
~~~

For Anthropic:

~~~powershell
$env:ORQALIS_ANTHROPIC_MODEL = 'YOUR_AVAILABLE_MODEL_ID'
$env:ORQALIS_ANTHROPIC_API_KEY = Read-Host 'Anthropic API key' -MaskInput
& $orqalis capabilities
~~~

Read-Host -MaskInput requires PowerShell 7.1+. On older shells, supply the variable
through your terminal or secret manager's environment support. Do not commit real keys
in configuration files or put them in task descriptions.

Replace model placeholders with actual models your account can use. Models are not chosen
automatically. capabilities reports local configuration, not a successful network login.

Commands default to openai. Setting Anthropic variables does not change that default;
pass --provider anthropic to run, execute, and define-goal when using Anthropic.

For a Bash-like shell, export the same environment variables before invoking the installed
orqalis executable.

### Configuration reference

| Variable | Default / behavior |
| --- | --- |
| ORQALIS_DATABASE_URL | postgresql+psycopg://orqalis:orqalis@127.0.0.1:5432/orqalis |
| ORQALIS_HOST | 127.0.0.1; loopback hosting only |
| ORQALIS_PORT | 7842 |
| ORQALIS_OPENAI_MODEL / ORQALIS_OPENAI_API_KEY | Unset |
| ORQALIS_ANTHROPIC_MODEL / ORQALIS_ANTHROPIC_API_KEY | Unset |
| ORQALIS_SKILL_ROOTS | Optional JSON array of trusted skill directories |
| ORQALIS_MAX_REPAIR_ITERATIONS | 5; copied into newly initialized projects |
| ORQALIS_TELEMETRY_CONSOLE | false; true enables operation telemetry on stderr |

Compose also reads ORQALIS_POSTGRES_PASSWORD for database initialization. If changed,
set a matching ORQALIS_DATABASE_URL. Changing the Compose variable does not rotate the
password stored in an existing PostgreSQL volume.

To use another local UI port:

~~~powershell
$env:ORQALIS_PORT = '7843'
& $orqalis ui --open
~~~

Existing servers retain their original environment. Restart the server you own after
configuration changes, or start the new configuration on another loopback port. The MCP
process must receive its configuration from the assistant client's launch environment.

## 3. Register a project

Choose an existing Git repository on a named branch, with at least one commit:

~~~powershell
$repo = 'S:\Projects\example-app'
& $orqalis init --repo $repo
& $orqalis status --repo $repo
& $orqalis memory status --repo $repo
~~~

Replace the example path with your actual repository. init records project identity,
detects languages/manifests, and indexes committed knowledge.

Repeated initialization returns the existing project. It does not overwrite that project's
persisted settings with new environment defaults.

Dirty source files remain untouched. They are not silently committed or included in the
run's starting commit. If existing changes must be part of the starting point, review and
commit them yourself before creating the run.

Execution creates a new branch and owned worktree outside the source checkout. Existing
branches are not repurposed. Protected branches such as main and master cannot be used
as run delivery targets. The source checkout remains on its original branch.

To obtain the project UUID for MCP or API configuration:

~~~powershell
$projectState = & $orqalis status --repo $repo --json | ConvertFrom-Json
$projectId = $projectState.project.id
~~~

## 4. First task walkthrough

This example assumes a small Python repository containing main.py and tests/test_main.py.
The task is to implement normalize so it strips surrounding whitespace and preserves the
name's letter case. Adapt paths and expected behavior to your project.

### A. Store operator policies outside the worktree

~~~powershell
$policyDir = 'S:\OrqalisPolicies\example-app'
New-Item -ItemType Directory -Force $policyDir | Out-Null
$goalFile = Join-Path $policyDir 'goal.json'
$executionPolicy = Join-Path $policyDir 'execution-policy.json'
$deliveryPolicy = Join-Path $policyDir 'delivery-policy.json'
$workspaces = 'S:\OrqalisWorktrees'
~~~

Save the following examples in that directory. The default workspace root, if omitted,
is .orqalis/workspaces under the current user's home directory. Use the same custom
--workspaces value when continuing an existing run.

### B. Save goal.json

~~~json
{
  "goal": "Normalize names by removing surrounding whitespace",
  "scope": ["main.py", "tests/test_main.py", "README.md"],
  "out_of_scope": ["Dependency changes", "Unrelated public API changes"],
  "constraints": ["Preserve the original name's letter case"],
  "definition_of_done": [
    "The normalization assertion passes",
    "The existing test suite passes",
    "Independent review and final delivery checks pass"
  ],
  "criteria": [
    {
      "key": "AC-1",
      "description": "Normalization removes surrounding whitespace",
      "validation_spec": {
        "kind": "command",
        "argv": ["python", "-B", "-c", "from main import normalize; assert normalize(' Ada ') == 'Ada'"],
        "timeout_seconds": 60
      }
    },
    {
      "key": "AC-2",
      "description": "The repository test suite passes",
      "validation_spec": {
        "kind": "test_suite",
        "argv": ["python", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        "timeout_seconds": 60
      }
    }
  ]
}
~~~

An explicit contract avoids the requirements provider call. Implementation and independent
model review still require a configured provider.

### C. Build a test image

Create a Dockerfile in the external policy directory:

~~~dockerfile
FROM python:3.12-slim
RUN python -m pip install --no-cache-dir pytest
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
~~~

Build it explicitly:

~~~powershell
docker build -t orqalis-example-tests:local $policyDir
~~~

This image is sufficient for the minimal example. A real project needs an image containing
its pinned test dependencies and required system libraries. Orqalis mounts the worktree
at /workspace. Sandboxed commands have no network, so dependencies must already be installed.

### D. Save execution-policy.json

~~~json
{
  "write_paths": ["main.py", "tests/test_main.py", "README.md"],
  "commands": [
    {
      "id": "normalize",
      "argv": ["python", "-B", "-c", "from main import normalize; assert normalize(' Ada ') == 'Ada'"],
      "timeout_seconds": 60
    },
    {
      "id": "tests",
      "argv": ["python", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
      "timeout_seconds": 60
    }
  ],
  "command_mode": "docker",
  "container_image": "orqalis-example-tests:local",
  "max_parallel_tasks": 4,
  "max_provider_turns": 12,
  "max_tool_calls": 40
}
~~~

The argv arrays match the goal validators exactly. python -B and the disabled pytest cache
help prevent generated files from appearing in the delivery diff.

### E. Save delivery-policy.json

~~~json
{
  "documentation_path": "README.md",
  "approved_sensitive_paths": [],
  "push": false
}
~~~

README.md is in the goal and write scope so finalization can add its accepted-change report.
Configure Git user.name and user.email before delivery, or supply both author_name and
author_email in this policy.

### F. Prepare and inspect the run

~~~powershell
& $orqalis run "Normalize names safely" --repo $repo --branch feature/normalize-names --contract $goalFile --open
~~~

Copy the printed run UUID:

~~~powershell
$runId = 'REPLACE_WITH_PRINTED_RUN_UUID'
& $orqalis goal show $runId
& $orqalis runs show $runId --json
~~~

The expected state is GOAL_DEFINED. Open the printed /runs/RUN_UUID URL in Mission Control.

For a new run, machine-readable creation is also available:

~~~powershell
$prepared = & $orqalis run "Normalize names safely" --repo $repo --contract $goalFile --json | ConvertFrom-Json
$runId = $prepared.run.id
~~~

That is an alternative creation command: it creates another run. To recover an existing
run ID, use runs --json instead of submitting the request again.

### G. Execute through review

~~~powershell
& $orqalis execute $runId --policy $executionPolicy --provider openai --workspaces $workspaces
& $orqalis runs show $runId --json
~~~

The Developer modifies the isolated worktree. Validators record evidence. The Reviewer
checks the contract independently. Failed acceptance can trigger targeted repair and another
validation/review cycle.

On success, the result normally stops at REVIEWING with a passing review. Inspect the
returned state and review; a structured command result does not always mean the run succeeded.

### H. Finalize

~~~powershell
& $orqalis finalize $runId --policy $deliveryPolicy
~~~

Finalization runs independent Change Guardian checks, documentation, final validation,
commit creation, optional push, and memory curation. Successful output contains COMPLETED
and commit_sha. This example leaves pushed=false.

The source checkout stays on its original branch. Inspect the delivered feature branch and
commit, then use your normal merge or pull-request process. Orqalis does not merge into main.

### Natural-language requirements and combined execution

Next time, omit --contract to use a Requirements actor:

~~~powershell
& $orqalis run "Normalize names safely and preserve existing behavior" --repo $repo --provider openai --open
~~~

Inspect the generated goal before execution. Generated validator commands must match the
approved execution policy.

When the contract and policy are already approved, preparation and execution can be combined:

~~~powershell
& $orqalis run "Normalize names safely" --repo $repo --contract $goalFile --policy $executionPolicy --provider openai --workspaces $workspaces --open
~~~

This still ends through review. Finalize remains a separate operation.

## 5. Goals and acceptance

A goal includes scope, constraints, assumptions, definition of done, and uniquely identified
criteria. At least one criterion must be required. An LLM assertion alone cannot pass it.

| Validation kind | Meaning |
| --- | --- |
| command | Exact argv and expected exit code, default zero |
| test_suite | Approved test command with captured results |
| static_analysis | Approved analysis command |
| file | File existence/absence and optional text containment |
| diff | Text containment in a file's Git diff against a specified base commit |
| review | Independent review with verifiable source assertions |
| manual | Human-dependent validation; V1 never automatically approves it |

File existence does not prove behavior. Choose evidence that measures the actual outcome.
Inspect evidence in the Acceptance tab or JSON snapshot.

An individual diagnostic validation can be invoked explicitly:

~~~powershell
& $orqalis goal validate $runId AC-1 --workspace 'S:\OrqalisWorktrees\ACTUAL_RUN_DIRECTORY' --idempotency-key diagnostic-1 --allow-configured-commands --json
~~~

Use the actual workspace path from execute output. --allow-configured-commands enables
**trusted-local** execution of contract commands for this diagnostic; it does not apply
the Docker execution policy. Without the flag, command validators are denied. Source-only
validators do not require it.

An idempotency key identifies one recorded result. Use a new key for a changed tree.
Diagnostic validation does not bypass independent review or final checks.

The lower-level goal create command stores a contract at RECEIVED. Prefer run --contract
for the normal workflow; it also synchronizes context. Use runs prepare RUN_ID to continue
a contract created at RECEIVED.

## 6. Execution and delivery policies

### Execution policy

| Field | Default / constraint |
| --- | --- |
| write_paths | Required nonempty repository-relative patterns |
| commands | Empty by default; unique command IDs and exact argv |
| command_mode | docker; trusted_local is an explicit fallback |
| container_image | Required for configured Docker commands |
| max_parallel_tasks | 4; range 1–16 |
| max_provider_turns | 12; range 1–100 |
| max_tool_calls | 40; range 1–500 |
| max_file_bytes | 200,000; maximum 1,000,000 |
| Command timeout_seconds | 60; range 1–600 |

Use forward slashes in scope paths even on Windows. Absolute paths, backslashes, and
parent-directory traversal are rejected. Patterns use fnmatch-style matching: an asterisk
can match across separators, so explicit paths are clearer for small tasks.

An argv array is not a shell expression. Pipes and redirects do not gain shell semantics
automatically. Validator argv must exactly match an approved command, and the policy timeout
cannot exceed the validator timeout. Identical timeouts are simplest.

Filesystem tool writes are scoped. Approved commands can modify their mounted workspace;
the Guardian independently checks the resulting diff before delivery.

Docker commands have no network, a read-only root, dropped capabilities, 512 MB memory,
one CPU, a 128-process limit, and bounded temporary storage. Images are not pulled
automatically. Reviewer commands also mount the workspace read-only.

trusted_local executes on the host without Docker's filesystem/network/resource isolation.
Read-only reviewer commands require Docker.

The workspace's execution policy is bound to the run. Editing its JSON file does not expand
existing permissions; mismatches are rejected. Broader tool/write authorization generally
requires a new run.

### Delivery policy

| Field | Purpose |
| --- | --- |
| documentation_path | Optional approved .md, .rst, or .txt destination |
| approved_sensitive_paths | Exact sensitive configuration paths approved for changes |
| max_deleted_line_ratio | Default 0.5 deletion safeguard |
| push | false by default |
| remote | origin by default |
| allow_local_remote | false; explicitly allow local test remotes when appropriate |
| author_name / author_email | Supply both or neither |

Without documentation_path, Orqalis creates external documentation under
.artifacts/RUN_UUID beside the worktree hierarchy.

Build/dependency/CI/governance changes can require explicit sensitive-path approval.
That does not waive secret scanning, acceptance, or other gates. Review the policy before
the first finalize call: delivery authorization becomes immutable once delivery starts.

### Optional push

Push needs both ProjectSettings.allow_push=true and delivery push=true. CLI init defaults
to a project that prohibits pushing.

For a project not yet registered, an operator can configure this through the SDK:

~~~python
from pathlib import Path

from orqalis.domain.project import ProjectSettings
from orqalis.sdk import Orqalis

sdk = Orqalis()
try:
    project = sdk.initialize(Path("S:/Projects/new-project"), ProjectSettings(allow_push=True))
    print(project.id)
finally:
    sdk.close()
~~~

Repeated initialization does not update existing settings. V1 has no CLI project-policy
editing command; repeating init is not a way to enable pushing.

The remote must be reachable through host Git authentication. Delivery rejects protected
branches, force pushes, embedded URL credentials, and multiple push destinations. A run's
accepted commit remains traceable in its delivery record.

## 7. Mission Control

~~~powershell
& $orqalis ui --open
~~~

ui starts or reuses a background local server. Closing the browser stops neither the server
nor execution. For foreground hosting and startup diagnostics:

~~~powershell
& $orqalis serve
~~~

Use an unused port when another server is listening. Ctrl+C stops a foreground server.
There is no ui stop command in V1.

Select a run or open its /runs/RUN_UUID URL.

| View | What it shows |
| --- | --- |
| Mission | Orchestrator, instantiated agents, assignments, phase, counts, acceptance, repairs, activity |
| Graph | Dependencies, parallel branches, responsible actors, repair paths |
| Timeline | Persisted actor/task/phase intervals, waiting/blocking and concurrency |
| Acceptance | Validator, status, evidence, review, failure reason and related work |
| Project Brain | Knowledge search, provenance, indexed commit, freshness, file/directory relationships |
| Delivery | Guardian findings, documentation, final checks, artifacts, diff, commit and push |
| Metrics | Durations, actor activity, provider/tool calls, reported usage and run comparison |

Inspect graph nodes, timeline entries, and actor details for related evidence. Themes support
system, light, and dark modes. Developer mode exposes public structured data, not private
model reasoning.

Progress uses completed task weights in the current plan. Adding repair or delivery work
can change its denominator. A completion percentage is not an acceptance vote. Timers come
from persisted records; unavailable tokens and costs remain unreported.

Refresh reconnects to the same run. An active-looking persisted status after a process crash
does not prove a worker is still alive; inspect recovery details.

The browser provides inspection and supported run controls. Create tasks and approve
execution through CLI, SDK, or MCP. It is not a second orchestration engine.

## 8. Project Memory

~~~powershell
& $orqalis memory status --repo $repo
& $orqalis memory search "architecture" --repo $repo --limit 10
& $orqalis memory search "decisions" --repo $repo --json
& $orqalis memory refresh --repo $repo --json
& $orqalis context "Where should name normalization be implemented?" --repo $repo --json
~~~

memory status does not trigger a rescan. Search/context refresh committed changes first.
Unchanged HEAD avoids broad source reads; changed commits refresh affected paths selectively.

Knowledge has source files, source commits, confidence and verification/invalidation
metadata. Dirty files require inspection and are not promoted as committed facts. Secret,
generated, oversized, and unsupported binary inputs are excluded or redacted.

Successful delivery curates knowledge against its new commit. The original source checkout
may remain on an older branch; its context queries continue to represent that branch.
The Project Brain for a delivered run can inspect its worktree. Unmerged run knowledge
does not automatically become current source-branch truth.

Structured retrieval works without embeddings. Semantic retrieval needs an optional
embedding adapter; configuring an LLM provider does not configure embeddings.

## 9. Control, recovery, and goal revisions

### Understand the checkpoint

| State | Typical next action |
| --- | --- |
| RECEIVED / CONTEXT_SYNC | Continue with runs prepare |
| ANALYZING | Continue with define-goal |
| GOAL_DEFINED / PLANNED | Inspect the contract, then execute |
| EXECUTING / TESTING | Observe active work or diagnose a stopped worker |
| REVIEWING | Inspect review; finalize after acceptance passes |
| REPAIR_PLANNING | Continue execution to schedule targeted repairs |
| PAUSED | Resume the stored checkpoint, then invoke the appropriate driver |
| BLOCKED | Inspect blockers and attempt receipts |
| HUMAN_REVIEW_REQUIRED | Human decision after repair-budget/policy escalation |
| DOCUMENTING / DELIVERY_VALIDATION / COMMITTING / PUSHING / MEMORY_FINALIZATION | Continue safe finalization with the original policy |
| COMPLETED | Inspect the delivered commit and retained evidence |
| CANCELLED / FAILED | Terminal; normal resume does not restart the run |

### Pause, resume, cancel

~~~powershell
& $orqalis runs pause $runId
& $orqalis runs resume $runId
& $orqalis runs cancel $runId
~~~

These are separate actions, not an automatic sequence. Pause requires a quiescent checkpoint
and may be refused during active work. Resume restores state but does not launch execution;
continue with execute, define-goal, or finalize.

Cancellation stops unfinished work and prevents subsequent delivery. It does not undo
effects already completed. A canceled run remains canceled.

### Inspect after interruption

~~~powershell
$snapshot = & $orqalis runs show $runId --json | ConvertFrom-Json
$snapshot.run
$snapshot.blockers
$snapshot.attempts | Select-Object id, task_id, status, started_at, completed_at
~~~

Use the same run UUID, workspace root, provider and approved policies. Reissuing the
appropriate driver can reuse completed receipts and continue a known checkpoint.

For failed context preparation:

~~~powershell
& $orqalis runs prepare $runId
~~~

For requirements ready to continue at ANALYZING:

~~~powershell
& $orqalis define-goal $runId --provider openai
~~~

When an uncertain provider/tool operation prevents continuation, stop any old worker and
inspect its effects. Then authorize a replacement attempt:

~~~powershell
$executionId = 'REPLACE_WITH_INTERRUPTED_ATTEMPT_UUID'
& $orqalis runs recover $runId $executionId --reason "Inspected the stopped worker and its workspace effects" --acknowledge-uncertainty
~~~

Use the attempt's id, not task_id or actor ID. If the run is BLOCKED after recovery, resume
before continuing its driver:

~~~powershell
& $orqalis runs resume $runId
& $orqalis execute $runId --policy $executionPolicy --provider openai --workspaces $workspaces
~~~

For requirements, use define-goal instead of execute. For delivery, use finalize with the
original policy. Recovery cannot take over a live controller lease and preserves old
attempts/evidence. The default project attempt limit is three.

Ordinary acceptance failures use targeted repair. The default repair budget is five for
newly initialized projects. Exhaustion escalates to human review; attempt recovery does
not increase that budget.

### Revise the goal explicitly

For an actual user-approved change to scope, pause and create a new version:

~~~powershell
& $orqalis runs pause $runId
& $orqalis goal revise $runId --contract 'S:\OrqalisPolicies\example-app\revised-goal.json' --reason "Approved scope clarification" --expected-version 1
& $orqalis runs replan $runId
& $orqalis runs resume $runId
& $orqalis execute $runId --policy $executionPolicy --provider openai --workspaces $workspaces
~~~

This sequence is for a run that already has an implementation plan. Before planning, normal
execute creates the initial plan. If already paused or in human review, do not blindly repeat
pause. Supply the actual current version to --expected-version.

Old goals, tasks, and evidence stay in history. New criteria do not inherit old acceptance.
The existing execution policy remains bound; broader permissions may require a new run.
Once delivery starts, a changed goal requires a new run.

## 10. Coding assistants and MCP

An MCP client uses Orqalis Project Memory and workflow while implementation can happen in
the assistant's native session. That connection is separate from an Orqalis provider adapter.
The independent reviewer uses the provider configured on the MCP server.

Start with a read-only policy:

~~~json
{
  "project_id": "00000000-0000-0000-0000-000000000000",
  "workspaces_root": "S:/OrqalisWorktrees",
  "allow_work": false,
  "allow_delivery": false
}
~~~

Replace the all-zero placeholder with the registered project UUID. Save the file outside the
source worktree. Configure the MCP client to launch the installed executable with arguments:

~~~text
mcp --policy S:/OrqalisPolicies/example-app/mcp-policy.json
~~~

For this checkout, the executable is S:/Orqalis/.venv/Scripts/orqalis.exe. The client normally
starts the stdio server. A manually launched server can appear silent because stdout is
reserved for protocol traffic.

The process must receive the correct database settings. To authorize work, set allow_work
to true and provide execution as an object matching ExecutionPolicy. To authorize delivery,
also set allow_delivery and provide delivery. Configure reviewer_provider and its credentials.
A client tool call cannot expand the server-owned permissions.

The native workflow is:

1. Retrieve project context.
2. start_task with an explicit goal draft.
3. Inspect get_goal/get_plan; request get_next_work.
4. Edit the assigned worktree within approved scope.
5. report_result with the assigned execution ID.
6. Request review_run; continue targeted repair if needed.
7. Request finalize_run when independently accepted and permitted.

A second client can continue with the same persisted run/attempt IDs. Worker reports cannot
approve acceptance or waive the Guardian.

Templates and details:

- [MCP workflow and setup](docs/MCP.md)
- [Codex example](docs/examples/codex-mcp.toml)
- [Claude Code example](docs/examples/claude-mcp.json)
- [VS Code/Copilot example](docs/examples/vscode-mcp.json)

Replace template paths and project IDs. The examples do not edit global assistant settings.
Remote MCP hosting is not enabled in V1.

## 11. Python SDK and local API

All interfaces use the same application services.

### SDK example

This assumes existing policy files, an approved test image, and a configured OpenAI provider:

~~~python
import asyncio
from pathlib import Path

from orqalis.domain.acceptance import GoalDraft
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.execution import ExecutionPolicy
from orqalis.sdk import Orqalis


async def main() -> None:
    sdk = Orqalis()
    try:
        project = sdk.initialize(Path("S:/Projects/example-app"))
        config = Path("S:/OrqalisPolicies/example-app")
        goal = GoalDraft.model_validate_json((config / "goal.json").read_text(encoding="utf-8"))
        execution = ExecutionPolicy.model_validate_json(
            (config / "execution-policy.json").read_text(encoding="utf-8")
        )
        delivery = DeliveryPolicy.model_validate_json(
            (config / "delivery-policy.json").read_text(encoding="utf-8")
        )
        prepared = sdk.prepare_run(project.id, goal.goal, "feature/sdk-normalization", goal)
        result = await sdk.executor(Path("S:/OrqalisWorktrees")).execute(
            prepared.run.id, "openai", execution
        )
        if result.review and result.review.result.overall == "PASS":
            delivered = await sdk.delivery.finalize(prepared.run.id, delivery)
            print(delivered.model_dump_json())
        else:
            print(result.model_dump_json())
    finally:
        sdk.close()


asyncio.run(main())
~~~

Choose a new branch for a new run. To resume existing work, use its run UUID rather than
calling prepare_run again.

### REST and events

The local API schema is at http://127.0.0.1:7842/openapi.json.

~~~powershell
Invoke-RestMethod 'http://127.0.0.1:7842/health'
Invoke-RestMethod 'http://127.0.0.1:7842/api/projects'
Invoke-RestMethod "http://127.0.0.1:7842/api/runs/$runId"
Invoke-RestMethod "http://127.0.0.1:7842/api/runs/$runId/events?after=0"
Invoke-RestMethod "http://127.0.0.1:7842/api/runs/$runId/acceptance"
Invoke-RestMethod "http://127.0.0.1:7842/api/runs/$runId/timeline"
~~~

WebSocket subscriptions use /ws/runs/RUN_UUID?after=EVENT_SEQUENCE and deliver structured
event batches and snapshots. Preserve the sequence for reconnects.

REST supports inspection, explicit-goal creation and supported controls. Do not assume
execute/finalize HTTP routes exist; use CLI/SDK/MCP for those drivers. Loopback/origin checks
also apply to WebSocket connections.

## 12. Skills and capabilities

~~~powershell
& $orqalis capabilities
~~~

A skill subdirectory contains skill.toml and instructions.md. Add an existing trusted root:

~~~powershell
$env:ORQALIS_SKILL_ROOTS = '["S:/OrqalisSkills"]'
& $orqalis capabilities
~~~

Create valid skill files before setting the root. Refer to the
[Python edit metadata](src/orqalis/skills/bundled/python-edit/skill.toml) and
[instructions](src/orqalis/skills/bundled/python-edit/instructions.md).

Orqalis discovers metadata, selects by capabilities/applicable tags, and loads instructions
on selection. Adding a skill does not grant additional tool permissions. Version/hash
checks make changes observable; duplicate ID/version combinations are rejected.

Bundled skills cover Python editing/testing and evidence review. Provider-neutral Python
interfaces support extensions. Merely naming an external provider does not enable an
arbitrary command launcher; native assistants use MCP.

## 13. Data, backups, and upgrades

Retain these together for restart and audit:

| Data | Location |
| --- | --- |
| Runs, goals, events, evidence, policies, memory | Configured PostgreSQL database |
| Source and delivered branches | Your Git repositories |
| Owned worktrees | Configured --workspaces root |
| External docs artifacts | .artifacts/RUN_UUID beside the worktree hierarchy |
| Operator policies | Your external policy directory |
| Custom skills | Trusted skill roots |

Compose stores PostgreSQL in a named volume. Back it up with standard PostgreSQL tools.
Keep the worktrees and artifacts referenced by database records; a database backup cannot
reconstruct deleted workspace files.

Before upgrading, reach a safe execution checkpoint, retain a backup, install the new
package, run migrate, and restart UI/MCP processes with the intended environment. Source
distributions need a frontend build before packaging.

Do not remove a worktree containing active or unreviewed work. Safe worktree management
exists as a Python service; there is no blanket CLI cleanup command.

docker compose stop preserves the database volume. Removing that volume destroys runtime
history and memory and is not a routine troubleshooting step.

To enable optional operation telemetry in newly launched processes:

~~~powershell
$env:ORQALIS_TELEMETRY_CONSOLE = 'true'
~~~

Spans/metrics go to stderr without prompt, command, provider-response content or private
reasoning. Persisted events remain authoritative for UI execution statistics.

## 14. Troubleshooting

| Symptom | Action |
| --- | --- |
| orqalis not found | Use the absolute installed executable or uv run from the Orqalis checkout |
| npm.ps1 blocked | Use npm.cmd |
| doctor fails | Check Git, database container health, URL/credentials and migrate |
| Frontend missing | Build web/ or install the complete wheel |
| Port belongs to another service | Choose another ORQALIS_PORT; leave unrelated processes alone |
| UI shows an old version | Restart the Orqalis server you own after updating code |
| Project not initialized | Run init --repo against the intended repository |
| Detached HEAD / no initial commit | Establish a named branch and reviewed baseline commit |
| Run branch exists | New run: choose a new branch; existing run: reuse its UUID |
| Provider missing | Configure both model/key in the invoking process and choose --provider |
| Authentication/model failure | Verify credentials/model, then inspect the persisted attempt before recovery |
| Command denied | Compare exact argv and timeout with the bound policy |
| Docker image missing | Build/pull the approved image explicitly before execution |
| Tests need dependencies/network | Install dependencies in the image before starting the sandbox |
| Guardian rejects caches/build output | Prevent generated output or explicitly reconsider intended delivery scope |
| Guardian rejects sensitive config | Review goal scope and approve exact paths before delivery starts |
| Invocation already running | Inspect worker/lease; do not start a competing controller |
| Uncertain interrupted invocation | Inspect effects, authorize recover, then continue the appropriate driver |
| Resume does not start work | Invoke execute, define-goal or finalize after restoring state |
| Repair limit reached | Inspect failed criteria and evidence; human decision is required |
| Manual criterion unapproved | V1 does not auto-attest; handle explicitly or authorize a verifiable revised contract |
| Finalize rejects policy changes | Reuse the original policy; new authorization may require a new run |
| Push denied | Check project and delivery permission, branch protection, and remote configuration |
| Memory stale after delivery | Original branch may still be old; inspect the run worktree or merge normally |
| Schema errors after upgrade | Verify the active database, package version and migrate result |

For issue reports, include version, run UUID, state, relevant attempt IDs, validator
result/error code, and a redacted snapshot. Exclude API keys and private provider reasoning.

## 15. Command reference

Prefix these with the installed executable, & $orqalis in PowerShell, or uv run orqalis
from the source checkout.

| Command | Purpose |
| --- | --- |
| version / doctor / migrate | Version, connectivity, schema upgrades |
| init --repo PATH | Register and index a project |
| status --repo PATH --json | Project identity and Git state |
| memory status / refresh / search | Memory inspection and retrieval |
| context "TASK" --repo PATH | Bounded, provenance-backed context |
| capabilities | Configured providers and discoverable skills |
| run "REQUEST" | Prepare requirements; optional --contract and --policy |
| define-goal RUN_ID | Continue requirements |
| execute RUN_ID --policy FILE | Implementation, validation, review, repair |
| finalize RUN_ID --policy FILE | Document and deliver accepted work |
| runs --json / runs show RUN_ID --json | Find runs and inspect snapshots |
| runs prepare / pause / resume / cancel | Preparation and lifecycle controls |
| runs recover RUN_ID EXECUTION_ID | Explicit interrupted-attempt recovery |
| runs replan RUN_ID | Plan work for an explicitly revised goal |
| goal create / show / revise / validate | Contract and evidence operations |
| ui --open / serve | Background or foreground local UI host |
| mcp --policy FILE | Project-scoped MCP stdio server |

Inspect exact options through CLI help:

~~~powershell
& $orqalis --help
& $orqalis run --help
& $orqalis runs recover --help
& $orqalis goal validate --help
~~~

Further reading:

- [Developer setup and tests](docs/DEVELOPMENT.md)
- [Concise operations and recovery](docs/OPERATIONS.md)
- [MCP integration](docs/MCP.md)
- [Release notes and operational limits](docs/RELEASE_NOTES.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Canonical implementation plan](docs/09-implementation-plan.md)

This guide documents implemented usage. It does not replace the signed-off architecture or
claim that live provider credentials and every platform build were validated locally.
