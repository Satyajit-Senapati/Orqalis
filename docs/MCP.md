# Assistant interoperability

Orqalis serves a registered project using MCP stdio:

    orqalis mcp --policy /absolute/path/to/mcp-policy.json

Use the installed executable's absolute path, including orqalis.exe on Windows.
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

The workflow is get_project_context, start_task with an explicit GoalDraft, get_goal,
get_next_work, native edits in the returned worktree, report_result, review_run,
and finalize_run. WorkerResult is an implementation report, never an acceptance vote.
Actual validators and the independent reviewer produce acceptance evidence. Failed
reviews add bounded repair tasks; call get_next_work with the advertised diagnosis
and implementation capabilities to continue. A second MCP client can continue the same
persisted run using its UUID and assigned execution ID.

The server exposes 15 tools and read-only project, run, architecture and decision
resources. Core does not import MCP. The interface policy binds every run operation
to one authorized project and separately controls work/delivery. Local stdio relies
on the host OS/process identity. Remote HTTP hosting is not enabled; a future remote
host must authenticate callers, map identity to server-owned project/action policy,
and retain the same domain gates. Tool annotations are descriptive, not authorization.

Client configuration examples:

- Codex: merge examples/codex-mcp.toml into the appropriate MCP configuration.
  [Official MCP configuration](https://developers.openai.com/codex/mcp).
- Claude Code: use the mcpServers entry in examples/claude-mcp.json or
  claude mcp add --transport stdio orqalis -- /absolute/path/to/orqalis mcp --policy /absolute/path/to/mcp-policy.json.
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
