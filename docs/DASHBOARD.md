# Dashboard enhancement audit and operating notes

This is an enhancement to Orqalis 1.0.0 on the signed-off architecture v1.2.
Discovery started on main at 2451063 with a clean working tree. The attached enhancement
brief is the UX target; no separate accompanying design document was present.

## Gap analysis

| Area | Audit category | Existing implementation | Enhancement |
| --- | --- | --- | --- |
| Core / CLI / SDK | Existing | Shared deterministic workflow, DAG scheduler, provider/tool boundaries, repair, safe Git delivery | Preserved |
| Persistence | Existing | PostgreSQL/pgvector, SQLAlchemy, eight Alembic revisions, canonical runtime records | No new table or migration |
| Browser shell | Partially Existing | React/TypeScript/Vite, theme, run history, tabs | Compact mission summary, dark default, readable status symbols, responsive drawers |
| Graph | Partially Existing | React Flow/Dagre task DAG and actor graph | Combined orchestration relationships, selectable agents/tasks, stable topology layout |
| Inspector | Needs UI Exposure | Attempts, actors, tools, evidence, artifacts in snapshots | Shared keyboard-accessible actor/task inspector and cross-view file/task links |
| Activity | Partially Existing | Last 12 events, cursor-based WebSocket reconnect | Chronological activity, five filters, bounded pending/history buffers, explicit error states |
| Agent context | Needs Runtime Telemetry | Initial run memory IDs persisted; provider request bodies intentionally not persisted | Add memory IDs, skill refs and a bounded context summary to existing invocation-start events |
| Skills | Needs UI Exposure | Trusted metadata registry, capability selection, versioned SKILL_LOADED events | Read-only SDK/API catalog and event-derived load counts, users and last-load times |
| Project Brain | Existing | Git freshness, sources, provenance, categories, search and knowledge graph | Highlight facts used in the run context |
| Verification / delivery | Existing | Evidence, review history, repair ancestry, Guardian reports, final validation and Git diffs | Expose repair counter and originating-task navigation |
| README | Needs Documentation Only | Canonical handoff index | Product front page, tested local setup, real screenshots, retained source-of-truth index |
| Media | Missing | Ignored browser QA captures | Optimized screenshots of persisted deterministic integration runs |

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
default to dark and can choose light or system.

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
were not used. No production UI contains hard-coded fixture state.

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
See [SOURCE_OF_TRUTH.md](SOURCE_OF_TRUTH.md) for the original architecture reading order.
