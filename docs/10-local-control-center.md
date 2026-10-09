# Local Control Center and runtime visualization

Status: canonical UI contract, revised 2026-09-16. The former database-query architecture
is superseded.

## Purpose

The Local Control Center is a project-scoped view of the same Orqalis application services
used by CLI and MCP. It visualizes orchestration without becoming a second source of truth.

```text
React UI
   |
FastAPI + WebSocket
   |
Orqalis application services and EventBus
   |
filesystem stores
   |
<repository>/.orqalis/
```

React must never open, watch or mutate `.orqalis` files directly. No PostgreSQL service,
database URL or Docker installation is required to launch the Control Center. Docker may
remain an optional execution sandbox.

## Launch and root binding

`orqalis ui` and `orqalis serve` bind the API host to the resolved project root. Root
resolution follows explicit root, `ORQALIS_PROJECT_ROOT`, Git root and current directory.
The selected root is visible in project/status responses. Starting a server for Project B
must not reuse Project A's manifest, memory, capsules, indexes, runtime locks or event bus.

## Information architecture

The existing product surfaces remain:

- Mission Control: goal, current phase, overall status, next action and blockers.
- Orchestrator: immutable goal versions, plan versions, repair iteration and approvals.
- Agents: actor sessions, provider/model, skills, task assignment, state and timing.
- Tasks/DAG: dependencies, readiness, retries, results and evidence links.
- Timeline: persisted phase/actor/tool/provider activity with active and waiting time.
- Acceptance: criteria, reviewer results, findings, evidence and validation status.
- Changes and delivery: file changes, Change Guardian, tests, documentation and Git result.
- Project Brain: graph, curated memory, decisions, related tasks and freshness.
- Historical tasks: reopen any retained Task Capsule after a restart.

Views distinguish running, waiting, blocked, human-review, failed, cancelled and completed
states. A progress bar never implies acceptance: completion means the required evidence and
review gates passed.

## Snapshot, replay and live delivery

The Orchestrator publishes each structured event to a project-local EventBus. The event
store appends it to the active capsule's `execution/events.jsonl`; the WebSocket broadcaster
sends the same operational event to connected clients.

A late or reconnecting client:

1. loads the current run/task snapshot;
2. loads relevant persisted historical events using its cursor;
3. applies them idempotently;
4. subscribes to live events; and
5. detects gaps or resets and rehydrates from a fresh snapshot.

`execution/state.yaml` and other capsule snapshots provide current state without replaying
an unbounded log. JSONL provides the audit trail. UI projections never contain hidden
chain-of-thought or unredacted provider/tool payloads.

## Project Brain

Project Brain reads through services backed by:

```text
.orqalis/project/
.orqalis/memory/
.orqalis/memory/graph/
.orqalis/index/
.orqalis/tasks/
```

It can show files, symbols, modules, extracted/inferred dependencies, decisions,
conventions, related historical tasks and stale memory. Derived indexes and graph
presentations are explicitly marked rebuildable; curated memory and task history remain
canonical.

## Historical inspection

The API reconstructs a historical task from its capsule: request, context, goal,
acceptance, plan/DAG, phases, agents, timing, attempts, reviews, repair loops, evidence,
changes, delivery and final result. Missing optional stage files mean that stage did not
occur; the frontend must not fabricate it.

## Security and privacy

- All routes and subscriptions are scoped to the server's bound project root.
- Mutating operations enforce the same permission and approval policy as CLI/MCP.
- Durable memory and summaries pass secret scanning and redaction.
- Provider credentials come from environment, user configuration, keychain or provider
  configuration, never Project Memory.
- File paths exposed to the browser are repository-relative.
- Raw tool output is not copied into human-readable projections by default.

## Performance

The browser requests bounded pages and graph neighborhoods. Backend services use the local
task index, search index and graph ranking rather than loading every task or graph node.
Initial bootstrap may be deeper; one-file changes should normally reprocess only affected
files and relationships.

## Acceptance criteria

- The UI works after `orqalis init` on a clean machine with no database server.
- Refreshing or restarting preserves historical tasks from `.orqalis/tasks/`.
- Reconnect produces a consistent snapshot plus event timeline with no duplicate state.
- Live agent, phase, review, repair, evidence, change and delivery updates remain visible.
- Project Brain reports graph provenance and memory freshness.
- Project A and Project B cannot retrieve each other's state.
- The packaged web assets are served through FastAPI; no frontend filesystem access exists.


## Local operation trace and measured critical path

The Timeline view reads `RunSnapshot.trace`: stable identities for the run, phases,
task attempts, actor sessions, model calls and tools. Selecting an operation exposes
its parent chain, related attempts, persisted provider/model identity and evidence IDs.
The view filters operation kinds and renders at most 50 table rows per page. Shared
sessions retain related-attempt links rather than being duplicated under one task.
Historical snapshots without a trace remain readable.

Core derives phase ownership from persisted phase/task events, model ownership from
actor/task-execution IDs, and tool ownership from provider-invocation IDs. When historical
ownership is absent, the operation remains under the run instead of inventing a parent.
The projection includes no prompts, tool arguments, raw model output or private reasoning.
A missing or invalid end timestamp produces `Not reported`, not a zero duration.

The measured critical path is the backend's existing path through recorded task work.
The Timeline lists its tasks and outlines their intervals; it is not a completion estimate.
The browser never calculates orchestration decisions from this display.

Validation uses an actual persisted parallel run with a failed review and successful
repair, exported after restart/ownership checks. The saved fixture and regeneration
command are in `web/src/fixtures/README.md`; browser coverage exercises keyboard ancestry
navigation and mobile layout. This does not qualify a native provider or hosted exporter.

## Visual and operating detail

The sections below retain the shipped visual and operating details from the former dashboard guide. The core snapshot and policy contracts above remain authoritative.

### Visual system

The primary presentation is Pitch-inspired dark: a deep navy-to-purple canvas, layered
magenta, violet and cyan light, luminous surfaces, and high-contrast type. Colorful
components give actors, tasks, evidence and workflow phases a recognizable visual rhythm
without turning the operating surface into a decorative slide.

Role accents identify the Orchestrator and specialist agents. Semantic status colors are
stable across cards, graph nodes, timelines, badges and activity. Color is never the only
signal: text, icons, shapes and accessible names carry the same meaning. Decorative
gradients do not encode runtime data.

Motion is presentation state, not workflow state. A restrained pulse or flow may draw
attention to active work and newly received events, while persisted status and timestamps
remain the source of truth. The reduced-motion preference removes nonessential animation
and preserves every status, relationship and control.

Pitch-dark is the sole product theme and the theme used for documentation captures.

### Navigation

Home projects the local workspace before a run is selected. Project cards expose the
registered repository root, default branch, run totals, active work and latest run without
inventing another workspace domain model. Selecting a project stores the filter in the URL,
filters history and makes Mission Control resolve to that project's latest run. View all
projects clears the filter.

The desktop sidebar keeps its footer fixed and scrolls the project/recent-run body when the
viewport is short. At 900px and below, the same controls move into a keyboard-accessible
drawer; nothing is removed from mobile navigation. Menu reports its expanded state, Escape
and the backdrop close it, and focus returns to the trigger. Primary and project controls
have at least 44px mobile hit targets.

Mission is the run overview: goal, branch, current phase, recorded timing, plan progress,
active workers, acceptance and a graph of actual actors/tasks. Task retry counts derive
from execution attempts; the repair-loop counter comes from the Run.

Graph switches between orchestration, task DAG and actors. Solid edges show dependencies,
dotted edges delegation, assignment edges ownership and dashed edges repair ancestry.
Queued work has no invented assigned agent. Tasks that perform review/documentation/delivery
are the real DAG nodes, not a second UI workflow.

Click a node or use Inspect task / Inspect actor. Tasks and Agents also provide normal
keyboard-operable list buttons. Inspectors use native modal dialogs: focus stays inside,
Escape closes, and focus returns to the originating control. On mobile they become sheets.
Files link to Delivery only when a Guardian report actually includes that path.
Attribution comes from evidence/artifacts, not guessed ownership of every changed file.

Timeline retains persisted execution intervals and paginates after 50 tracks. Activity
shows the latest 200 events in sequence order and filters by actor, task, phase, type and
status. These are display windows, not deletions of runtime history. Use the events API
with after and optional limit (1–1000) for older records. Existing callers omitting limit
retain the previous full-history API behavior.

Skills describes registry availability and event-backed load activity. A load is not
a successful invocation. Dynamic acquisition milestones without events are explained as
the selection process, not shown as fabricated completed steps. Historical versions
removed from the current registry remain listed from their load records.

### Operator control

The run overview now includes Operator control. SUPERVISED runs show their durable
GOAL, PLAN, REPAIR and DELIVERY gates; TASK may be enabled explicitly. A pending
request shows its stage, version, reason and complete SHA-256 subject digest. The
operator can approve or reject the exact request. Rejection requires a reason.
Goal revisions, a first plan preview, plan-draft replacement and revised-goal
replanning invoke the same Core services used by CLI and MCP. A changed subject
gets a new version or digest and needs a new decision. The Orchestrator actor and
timing derive approval waiting/blocking from persisted events.

To enable browser mutations, set ORQALIS_OPERATOR_TOKEN in the terminal that
starts the local UI and enter it on the run page. The token stays in React
component memory and is sent in the request header; it is not written to
local storage, URL or event payload. Read-only run views remain available
without it. The approval and edit endpoints reject mutations when no server token is configured.

For DELIVERY, inspect the exact policy JSON passed to finalize and the
Repository Delivery diff before approving. The card summarizes that policy and
shows its digest, but cannot display the full policy. For TASK, inspect the
plan task and execution policy. Home does not create supervised runs yet;
create one through CLI, SDK or trusted MCP policy. After browser approval,
resume execute or finalize from CLI/SDK/MCP. Browser job submission and
full-policy inspection remain follow-up work. These controls were introduced in the
historical public 1.0.1 release and remain part of the local-first 2.0.0 release.

### Observability and compatibility

The existing PROVIDER_INVOCATION_STARTED payload now includes memory IDs, loaded skill
references and a short context freshness/inspection summary. It contains no raw prompt,
memory content, skill instructions or private reasoning. Historical calls without that
metadata explicitly remain unavailable.

RunSnapshot adds skill_activity and context_memory_ids with empty defaults.
ProviderCallProjection adds selected_skills, context_memory_ids and context_summary.
GET /api/skills calls the shared SDK registry catalog; GET /api/runs/{id}/events accepts
an optional bounded limit. In that September 11 visual-only enhancement,
workflow transitions, task execution, CLI behavior, configuration and database
schemas were unchanged. The later operator controls above add a migration and
CLI/API behavior. Stored browser theme preferences are ignored; every browser
uses Pitch-dark.

### Performance and boundaries

The initial activity request fetches at most 200 records. Reconnect replay is deduplicated
against the snapshot cursor; pending and visible histories stay bounded to 200 records.
Fetches have timeouts; unavailable run IDs stop automatic retries. Graph coordinates are
recomputed only when topology changes, not on every timing update. Long narrow plans wrap
into directed rows to keep labels readable; branching plans retain layered DAG layout.
Graphs cap at 150 visible
nodes with an explicit notice; full task/actor lists remain accessible. Timeline groups
tracks in one pass and displays 50 tracks per page. Run history also pages at 50 entries
while retaining navigation to older runs.

Core still reconstructs snapshots from persisted history. This enhancement does not claim
constant-cost backend snapshots or unlimited graph rendering. Very large-run server
projection profiling and incremental snapshot caching remain future optimization work.
Tool-call paths are not guessed: when no source evidence/artifact records a file, the
inspector says attribution is unavailable. Cost/token fields retain unknown values.

### Screenshots

These are real browser captures of persisted local integration runs produced by
tests/e2e/seed_runtime.py and tests/e2e/seed_execution.py. Deterministic test providers
exercise the actual Core, tools, review, repair, Git and memory; live model credentials
were not used. The disposable Git repositories live under a workspace-keyed OS temporary
directory or an external ORQALIS_QA_FIXTURE_ROOT; fixture roots inside the checkout are
rejected. Only ignored run-ID pointers are written under .tools. No production UI contains
hard-coded fixture state.

The strict npm run test:e2e command rejects missing, malformed or API-unreachable fixture
IDs before Playwright starts. The capture process verifies the Pitch-dark tokens and
required surfaces, waits for fonts and settled layout, freezes nonessential animation,
and treats same-origin request/HTTP failures, console errors and page errors as diagnostics.
All images stage and validate before a directory rename publishes the set, so a failed
capture leaves the previously published screenshots unchanged.

| View | Capture |
| --- | --- |
| Project workspace | [workspace-overview.jpg](assets/workspace-overview.jpg) |
| Mission overview | [mission-control.jpg](assets/mission-control.jpg) |
| Task DAG | [orchestration-graph.jpg](assets/orchestration-graph.jpg) |
| Agent inspector | [agent-inspector.jpg](assets/agent-inspector.jpg) |
| Timeline | [execution-timeline.jpg](assets/execution-timeline.jpg) |
| Project Brain | [project-memory.jpg](assets/project-memory.jpg) |
| Skills | [skills.jpg](assets/skills.jpg) |
| Verification / repair | [verification-repair.jpg](assets/verification-repair.jpg) |
| Repository delivery | [repository-delivery.jpg](assets/repository-delivery.jpg) |

Regenerate with the capture command documented in [DEVELOPMENT.md](DEVELOPMENT.md).
The September 11 refresh produced nine 1600 x 1180 JPEGs with zero browser diagnostics;
a forced failed-capture check preserved all nine prior hashes. The strict browser suite
passed 11 tests with 0 skipped across the documented responsive and reduced-motion
coverage. See the dated
[verification record](verification/ui-behavior-hardening.json).

See [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md) for the original architecture reading order.

### Provider performance breakdown

The Metrics view groups persisted provider calls by provider and model, with outcome
counts, p50/p95 observed latency, token/cost reporting coverage, and recorded errors.
Unknown telemetry is shown as not reported. Call success does not imply acceptance.
See [ecosystem integrations](05-interfaces-and-integrations.md#provider-measurements) for
sampling and compatibility details.
