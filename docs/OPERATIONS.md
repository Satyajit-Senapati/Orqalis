# Local operation and recovery

Install globally through npm and migrate using [README.md](../README.md). The browser runs on
127.0.0.1:7842 by default. ORQALIS_PORT changes the local port.

## Run a task

Initialize a committed Git repository once with orqalis init --repo PATH.
Configure an explicit OpenAI or Anthropic model and API key through the documented
ORQALIS_ environment variables.

    orqalis run "Describe the requested change" --repo PATH --open

`--open` hosts the local UI inside this CLI process while work runs. After the run,
press Ctrl+C to stop its UI and return to the prompt, or use a second terminal for
the commands below. If another Orqalis UI already owns the port, its host is reused
and remains independently controlled. No Windows service is registered.

A Requirements actor creates a structured goal and evidence-backed acceptance contract.
The command prints a run ID before provider execution. The source branch is not switched.
Use --branch to choose the owned run branch; otherwise a unique orqalis/run-* branch
name is generated. This command prepares the contract. Execution requires an explicit
tool/write policy:

    orqalis execute RUN_ID --policy execution-policy.json --provider openai
    orqalis finalize RUN_ID --policy delivery-policy.json

You can pass --policy to run to execute after requirements. Existing contract files remain
supported with --contract; they avoid a requirements provider call. Inspect generated
acceptance before execution; unavailable commands or manual checks remain blocked/pending,
and Orqalis never weakens criteria to force a pass.

If context synchronization failed, use orqalis runs prepare RUN_ID to resume that same run.
After context preparation, use orqalis define-goal RUN_ID to continue the persisted
Requirements checkpoint. A successful response/goal is reused without another provider call.

## Inspect and control

    orqalis runs show RUN_ID --json
    orqalis runs pause RUN_ID
    orqalis runs resume RUN_ID
    orqalis runs cancel RUN_ID

Pause requires a quiescent checkpoint. Cancel stops unfinished work and prevents delivery.
A canceled run stays canceled. A provider failure or uncertain operation blocks the run.

The Control Center exposes actor/task details, timeline, acceptance evidence, Project Brain,
diffs, tool/provider results, delivery receipts and historical comparison. Unknown tokens and
cost display as not reported. Developer mode contains public structured snapshots only.

## Explicit recovery

Stop any old external worker and inspect its workspace/tool effects before authorizing a retry.
The old attempt, outputs and evidence remain in history.

    orqalis runs recover RUN_ID EXECUTION_ID --reason "Describe what was inspected and fixed" --acknowledge-uncertainty
    orqalis runs resume RUN_ID
    orqalis execute RUN_ID --policy execution-policy.json

For preparatory work, continue with define-goal instead of execute. For a delivery checkpoint,
continue with finalize using the original policy. Recovery cannot take over a live execution
lease or silently retry beyond ProjectSettings.max_task_attempts (default three).
A repair-limit escalation needs human review; recovery cannot extend that repair budget.

## Explicit goal revisions

At a quiescent checkpoint:

    orqalis runs pause RUN_ID
    orqalis goal revise RUN_ID --contract revised-goal.json --reason "User-approved scope change" --expected-version 1
    orqalis runs replan RUN_ID
    orqalis runs resume RUN_ID
    orqalis execute RUN_ID --policy execution-policy.json

A revision creates fresh criteria and a new plan, preserving prior goals, tasks, evidence
and timing. It cannot silently reinterpret old success as acceptance of a new contract.
Once delivery starts, a changed goal requires a new run.

## Data and diagnostics

PostgreSQL contains runtime state and Project Memory. Back it up using normal PostgreSQL
tools. Owned worktrees and external documentation artifacts must be retained along with
the database to support restart and evidence inspection. Do not remove an active worktree.

ORQALIS_TELEMETRY_CONSOLE=true enables OpenTelemetry span/metric export to stderr.
Embedding applications may configure OpenTelemetry providers/exporters themselves.
Operation telemetry excludes prompts, commands, returned content and exception text.
Runtime events include trace IDs when a recording span is active.

Docker commands run with network disabled, a read-only root, bounded memory/CPU/process
counts and a temporary scratch directory. Images must already be available locally.
Reviewer commands mount the workspace read-only. trusted_local executes approved argv
on the host and is intended for explicitly trusted development commands.
On POSIX hosts, sandbox containers use the Orqalis process's effective user and group IDs,
which keeps owner-only workspaces accessible and generated files owned by the caller.

Remote HTTP/MCP transport is not enabled. Native assistant interoperability uses the
project-scoped stdio [MCP interface](MCP.md).
