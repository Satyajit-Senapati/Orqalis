# Security, Git, and Governance

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Threat model

Orqalis executes model-generated actions against source code, local tools, and potentially remote Git. Treat every agent output as untrusted until validated against tool schemas, policies, workspace boundaries, and acceptance gates.

## 2. Permission model

Define permissions by role and tool class.

Example:

```text
Developer
  read repo: yes
  write workspace: yes
  run approved commands: yes
  read memory: yes
  mutate canonical memory: no
  commit: no
  push: no

Reviewer
  read repo: yes
  write code: no
  run tests: yes
  read memory: yes
  commit/push: no

Git delivery service
  stage/commit: yes after gates
  push: yes after gates
  force push: denied by default
```

## 3. Sandbox

Commands run with:
- workspace-scoped filesystem mounts;
- resource/time limits;
- network policy;
- environment-variable allowlist;
- no host secrets exposure;
- command audit logs.

V1 may implement Docker-based sandboxing with configurable fallback for trusted local development.

## 4. Command policy

Classify commands:
- read-only/safe;
- build/test;
- workspace-mutating;
- networked;
- destructive;
- privileged.

Deny or require human approval for destructive/privileged classes. Explicitly block unsafe defaults such as force push, deleting parent directories, rewriting protected branch history, and unscoped credential access.

## 5. Git workflow

At run start:
1. Confirm repository root.
2. Record base commit.
3. Fetch if policy allows/requests.
4. Confirm target branch.
5. Create isolated worktree.
6. Record initial status.

Before commit:
1. Confirm reviewer PASS.
2. Confirm Change Guardian PASS.
3. Confirm final validation PASS.
4. Check secrets and forbidden files.
5. Inspect full diff.
6. Ensure target branch remains valid.
7. Generate documentation updates.
8. Stage explicit files.
9. Generate commit message from goal/diff/evidence.
10. Commit.
11. Push only if configured.

## 6. Commit message format

Recommended:

```text
feat(sync): add offline note synchronization

Implement background synchronization and conflict handling for offline note edits.

Changes:
- add SyncCoordinator and persistence queue
- integrate WorkManager scheduling
- add conflict-resolution tests
- update architecture documentation

Validation:
- build passed
- unit tests passed
- sync integration tests passed

Acceptance:
- AC-001 PASS
- AC-002 PASS
- AC-003 PASS

Orqalis-Run: ORQ-2026-0202
```

## 7. Protected operations

Default deny:
- force push;
- branch deletion;
- `git reset --hard` against user work;
- cleaning untracked user files;
- pushing directly to protected branches;
- secret/credential commits;
- disabling security tests to make acceptance pass.

## 8. Secrets

Secrets belong in OS keychain, environment injection, vault integration, or CI secret stores. Never persist them in project memory, run artifacts, prompts, traces, or docs. Add redaction to logs and memory ingestion.

## 9. Audit

Persist who/what caused each consequential transition:
- user request;
- selected provider/model;
- task assignment;
- tool execution;
- file-change summary;
- reviewer decision;
- repair reason;
- commit/push event;
- memory promotion.

## 10. Human-in-the-loop policy

Support configurable approval gates for:
- architecture-changing tasks;
- dependency upgrades;
- migrations;
- network access;
- pushes;
- protected files;
- max cost/time thresholds;
- repeated repair failures.

## 11. Control Center and telemetry security

The local UI binds to loopback by default. Any non-loopback/remote binding requires explicit configuration, authentication, authorization, CSRF/origin protections appropriate to the transport, and the same project/role policies used by CLI/MCP.

Telemetry/event payloads are security boundaries. Redact or omit credentials, auth headers, environment secrets, sensitive command arguments, provider raw responses that may contain secrets, and private model chain-of-thought. Developer mode may reveal additional structured diagnostics only after the same redaction pipeline.

Browser controls never bypass policy. Pause/cancel/resume/approval/delivery operations are normal Orqalis commands recorded in the audit log. UI display data must be sourced from persisted projections/events so browser refresh cannot invent or alter workflow history.
