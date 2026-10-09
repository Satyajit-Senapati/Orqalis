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
- command audit logs;
- POSIX caller identity mapping for bind-mount access and artifact ownership.

Execution policy explicitly selects `docker` or `trusted_local`; there is no silent fallback
from failed isolation to host execution. Docker images must already exist locally.

Application command paths record container intent and ownership under the canonical
project's `.orqalis/runtime/sandboxes/`, outside the writable worktree. Ownership binds the
project root, run, invocation, workspace, daemon identity, labels and exact container ID.
Create precedes start; cleanup verifies absence. Mismatched ownership, daemon errors, or
uncertain cleanup block further execution/recovery rather than deleting an unrelated container.
Do not remove active runtime receipts as though they were disposable parser caches.
Low-level callers without an application owner have only ephemeral cleanup scope.

A controller death during daemon creation can leave a stopped container before its identity
is observed. Recovery remains conservative; these receipts do not claim universal
exactly-once Docker behavior. Live daemon qualification is an explicit environment tier.

## 4. Command policy

Commands are selected by configured IDs and checked against exact approved argv, workspace,
time/output bounds, scrubbed environment and role/project tool permissions. The command
runner does not infer a permission grant from a skill declaration or repository instruction.
An approved shell interpreter invocation remains the explicitly approved shell command;
Orqalis does not claim a universal semantic classifier for arbitrary shell scripts.

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


## 12. Test-integrity review

Change Guardian bounds changed-file reads before allocation and secret/diff inspection.
For modified Python test files, it detects removed test declarations/assertions, loss of
standard assertion helpers such as `pytest.raises`, `pytest.warns` and `pytest.fail`, new
skip/xfail signals, and newly unparseable or excessively complex test syntax. These are
conservative review signals, not proof of test equivalence or exhaustive semantic analysis.

Intentional refactors can use the existing approved delivery policy's `reviewed_test_changes`
list. Each entry contains the exact repository-relative `path`, `old_hash`, and `new_hash`
from the inspected `ChangedFile` report. Both hashes are lowercase 64-character SHA-256
values over the old/new bytes. Review the diff before granting the exception; an edit to
either side invalidates it. The exception covers that test-integrity signal only, not
scope, secret, acceptance or other delivery gates. Empty lists are omitted from serialized
policies so existing approval fingerprints remain compatible.

MCP tools and resources verify the policy's project before returning project decisions,
configured skill content, graph or memory results. Generic factory construction receives the
same root check as the CLI entry path. Memory proposal approval remains an operator/service
operation rather than an unrestricted assistant tool.
