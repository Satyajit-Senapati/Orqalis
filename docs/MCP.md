# Assistant interoperability

Orqalis serves a registered project using MCP stdio:

    orqalis mcp --policy /absolute/path/to/mcp-policy.json

Install the public npm package with `npm install -g orqalis` (`npm.cmd` on Windows).
See the [installation guide](../README.md#1-installation-and-first-launch) for Node.js,
Python and database requirements. Run `orqalis --version` once to complete first-launch
Python setup before the client's startup timeout. In Windows PowerShell, use the [session-local alias](../README.md#install-globally)
for `orqalis` when the generated `.ps1` shim is blocked; `orqalis.cmd` remains a fallback.

For assistant hosts that spawn processes without a shell, use the absolute Node
executable plus the installed JavaScript launcher. This works across platforms and
avoids requiring .cmd/.ps1 shell handling or a separate orqalis.exe installation.
Find the paths with Get-Command node and npm.cmd root -g on PowerShell, or command -v
node and npm root -g on Bash/zsh. The launcher is <global npm root>/orqalis/bin/orqalis.js.
Templates below use placeholders for both absolute paths; do not paste them unchanged.

Example server argv:

    node /absolute/global-node-modules/orqalis/bin/orqalis.js mcp --policy /absolute/path/to/mcp-policy.json

Replace the project UUID in examples/mcp-policy.json with the ID from orqalis init
or orqalis status --json. Set an absolute workspace directory outside the source repository.
The server reads the same ORQALIS_DATABASE_URL as the CLI/API. Its policy starts read-only.

To enable work, set allow_work to true and provide execution using the same schema
as examples/execution-policy.json. The assistant cannot supply or expand command
permissions through a tool call. To enable finalization, also set allow_delivery
and supply delivery using examples/delivery-policy.json. Optional pushing additionally
requires ProjectSettings.allow_push. Configure reviewer_provider and its credentials
on the server; native assistant implementation does not need an Orqalis model key,
but independent model review does.

In the unpublished 1.0.1 source candidate, an operator can set control_mode
to SUPERVISED in the trusted MCP policy JSON.
The assistant cannot select or remove gates through a tool call. By default, supervised
runs require human GOAL, PLAN, REPAIR, and DELIVERY decisions; approval_gates can set
an exact custom set, including TASK. get_next_work stops at pending gates and leaves
the request in Core for the CLI or local Mission Control to display. Use
orqalis approvals list RUN_ID and orqalis approvals approve RUN_ID REQUEST_ID
--expected-digest DIGEST, or the token-protected browser controls, then repeat
get_next_work. The MCP server cannot approve its own requests. The UI process
needs ORQALIS_OPERATOR_TOKEN for browser decisions; the CLI uses the OS operator.

The workflow is get_project_context, start_task with an explicit GoalDraft, get_goal,
get_next_work, native edits in the returned worktree, report_result, review_run,
and finalize_run. WorkerResult is an implementation report, never an acceptance vote.
Actual validators and the independent reviewer produce acceptance evidence. Failed
reviews add bounded repair tasks. Call get_next_work again to continue. Omitting
worker_capabilities leaves task selection unrestricted by client preference; the trusted
registry still selects required skills within role/project permissions. A nonempty capability
list restricts assignments to tasks whose requirements it covers. A second MCP client can continue the same
persisted run using its UUID and assigned execution ID.

The server exposes compact project/context, workflow and capability tools plus read-only
project, run, architecture and decision resources. list_agents and list_skills provide focused
catalogs; list_capabilities combines those with configured providers. get_related_files returns
paths from the same Git-aware Context Pack. The MCP handshake reports the installed Orqalis
application version, matching orqalis --version. Core does not import MCP. The interface policy binds every run operation
to one authorized project and separately controls work/delivery. Local stdio relies
on the host OS/process identity. Remote HTTP hosting is not enabled; a future remote
host must authenticate callers, map identity to server-owned project/action policy,
and retain the same domain gates. Tool annotations are descriptive, not authorization.

Report an observed issue with report_finding while its external assignment is active:

```json
{
  "run_id": "RUN_UUID",
  "execution_id": "ASSIGNED_EXECUTION_UUID",
  "idempotency_key": "normalization-source-issue",
  "finding": {
    "severity": "blocking",
    "summary": "Normalization still retains surrounding whitespace",
    "source_ref": "main.py"
  }
}
```

Replace UUID placeholders with the actual assigned IDs. Severity is info, warning or blocking.
Supply a current criterion_id, a repository-relative source_ref, or both. Reports reject
private content, unrelated criteria and forged resolution fields. Repeating a key with the
same payload returns its existing receipt; changing that payload is rejected.

report_result does not resolve findings. The independent reviewer receives open findings and
must address each through finding_reviews. A resolution requires current passing evidence
or verified source assertions. A source-anchored finding needs a matching source check or
current FileValidation evidence whose validator path and observed source both match the
reported path. Orqalis rechecks that file condition before accepting resolution, including
must_exist=false when deletion fixes the issue. Unrelated or stale evidence is rejected.
Unresolved blocking findings produce failed review and targeted repair, and block delivery.
Final validation rechecks resolved source assertions and every relied-on evidence criterion
after documentation changes, even if that criterion was otherwise optional. No client
method can self-approve a finding or waive the acceptance/Guardian gates.

Client configuration examples:

- Codex: merge examples/codex-mcp.toml into the appropriate MCP configuration.
  [Official MCP configuration](https://developers.openai.com/codex/mcp).
- Claude Code: use the mcpServers entry in examples/claude-mcp.json or
  claude mcp add --transport stdio orqalis -- /absolute/path/to/node /absolute/global-node-modules/orqalis/bin/orqalis.js mcp --policy /absolute/path/to/mcp-policy.json.
  [Official Claude Code MCP configuration](https://code.claude.com/docs/en/mcp).
- VS Code/Copilot: use examples/vscode-mcp.json in the selected MCP configuration.
  [Official VS Code MCP configuration](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

These are configuration examples; Orqalis does not edit your global assistant settings.
Credentials should come from the process environment, not committed configuration.
A client tool timeout must allow the configured validator/reviewer duration.

The integration uses the official MCP Python SDK 2.2 with a constrained major version.
Tests use both its protocol client and a real stdio subprocess, and verify read-only
denials, premature review rejection, result schema validation, cross-client continuity,
and successful delivery. [SDK server and client documentation](https://py.sdk.modelcontextprotocol.io/).
