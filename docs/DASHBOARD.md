# Dashboard design and operating guide

Orqalis Mission Control is the local browser projection of the signed-off v1.2 Core.
This guide records the current navigation, visual contract, telemetry boundaries,
performance limits and reproducible product media for Orqalis 1.0.0.

The first dashboard enhancement was audited from commit 2451063. The September 11, 2026
visual refresh changes presentation only: orchestration, workflow transitions, persisted
telemetry, APIs, security policy and Git delivery remain authoritative in Core.

## Visual system

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

Light and system themes remain available. The dark theme is the product's primary visual
identity and the theme used for documentation captures.

## Capability map

| Area | Current contract |
| --- | --- |
| Core / CLI / SDK | Shared deterministic workflow, DAG scheduler, provider/tool boundaries, repair and safe Git delivery |
| Persistence | PostgreSQL/pgvector, SQLAlchemy, migration-backed canonical runtime records |
| Browser shell | Pitch-dark default, light/system alternatives, responsive navigation and inspectors |
| Graph | Selectable orchestration, task and actor relationships with stable topology-aware layout |
| Inspector | Keyboard-accessible actor/task detail with attempts, context, tools, evidence and artifacts |
| Activity | Chronological persisted events, five filters, bounded pending/history buffers and explicit error states |
| Agent context | Memory IDs, loaded skill references and a bounded context summary when recorded |
| Skills | Trusted metadata catalog and event-derived load counts, users and last-load times |
| Project Brain | Git freshness, sources, provenance, categories, search and knowledge relationships |
| Verification / delivery | Evidence, review history, repair ancestry, Guardian reports, final validation and Git diffs |
| Product media | Eight optimized screenshots captured from deterministic persisted integration runs |

## Navigation

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

## Observability and compatibility

The existing PROVIDER_INVOCATION_STARTED payload now includes memory IDs, loaded skill
references and a short context freshness/inspection summary. It contains no raw prompt,
memory content, skill instructions or private reasoning. Historical calls without that
metadata explicitly remain unavailable.

RunSnapshot adds skill_activity and context_memory_ids with empty defaults.
ProviderCallProjection adds selected_skills, context_memory_ids and context_summary.
GET /api/skills calls the shared SDK registry catalog; GET /api/runs/{id}/events accepts
an optional bounded limit. Workflow transitions, task execution, CLI behavior, configuration
and database schemas are unchanged. Existing saved themes are preserved; new browsers
default to Pitch-dark and can choose light or system.

## Performance and boundaries

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

## Screenshots

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
| Mission overview | [mission-control.jpg](assets/mission-control.jpg) |
| Task DAG | [orchestration-graph.jpg](assets/orchestration-graph.jpg) |
| Agent inspector | [agent-inspector.jpg](assets/agent-inspector.jpg) |
| Timeline | [execution-timeline.jpg](assets/execution-timeline.jpg) |
| Project Brain | [project-memory.jpg](assets/project-memory.jpg) |
| Skills | [skills.jpg](assets/skills.jpg) |
| Verification / repair | [verification-repair.jpg](assets/verification-repair.jpg) |
| Repository delivery | [repository-delivery.jpg](assets/repository-delivery.jpg) |

Regenerate with the capture command documented in [DEVELOPMENT.md](DEVELOPMENT.md).
The September 11 refresh produced eight 1600 x 1180 JPEGs with zero browser diagnostics;
a forced failed-capture check preserved all eight prior hashes. The strict browser suite
passed 7 tests with 0 skipped across the documented responsive and reduced-motion
coverage. See the dated
[verification record](verification/dashboard-visual-refresh.json).

See [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md) for the original architecture reading order.
