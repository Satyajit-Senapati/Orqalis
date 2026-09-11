import { useEffect, useState } from "react";
import { duration, get } from "./api";
import { Badge, classToken, Empty, label } from "./ui";
import {
  actorName,
  taskRelations,
  visibleTasks,
  type Inspect,
} from "./runtime";
import type { Event, SkillCatalogEntry, Snapshot } from "./types";

export function TaskList({
  snapshot: s,
  inspect,
}: {
  snapshot: Snapshot;
  inspect: Inspect;
}) {
  const [filter, setFilter] = useState("");
  const visible = visibleTasks(s);
  const statuses = [...new Set(visible.map((task) => task.status))];
  const activeFilter = statuses.some((status) => status === filter)
    ? filter
    : "";
  const tasks = visible.filter(
    (task) => !activeFilter || task.status === activeFilter,
  );
  return (
    <section className="panel operational-panel">
      <div className="section-heading">
        <div>
          <h2>Task plan</h2>
          <span>
            Plan v{s.run.plan_version} · {visible.length} tasks
          </span>
        </div>
        <div className="view-toolbar">
          <label className="compact-field">
            Status
            <select
              value={activeFilter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="">All tasks</option>
              {statuses.map((status) => (
                <option key={status}>{status}</option>
              ))}
            </select>
          </label>
          {activeFilter && (
            <button
              type="button"
              className="text-link"
              onClick={() => setFilter("")}
            >
              Clear filter
            </button>
          )}
        </div>
      </div>
      {!tasks.length ? (
        <Empty>No tasks match this view.</Empty>
      ) : (
        <div className="task-list">
          {tasks.map((t) => (
            <button
              className="task-list-row"
              key={t.id}
              onClick={() => inspect({ kind: "task", id: t.id })}
            >
              <span className="task-identity">
                <small>
                  {label(t.preferred_role)} · {t.id.slice(0, 8)}
                </small>
                <strong>{t.description}</strong>
                <span>
                  {taskRelations(s, t.id).dependencies.length} dependencies ·{" "}
                  {Math.max(0, t.attempt_count - 1)} retries
                </span>
              </span>
              <Badge status={t.status} />
              <span className="numeric">
                {duration(s.task_timing[t.id]?.active_ms ?? 0)}
                <small>working</small>
              </span>
              <span aria-hidden="true">↗</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

export function AgentList({
  snapshot: s,
  inspect,
  compact = false,
}: {
  snapshot: Snapshot;
  inspect: Inspect;
  compact?: boolean;
}) {
  return (
    <section
      className={compact ? "actor-roster" : "panel operational-panel"}
      aria-label="Runtime actors"
    >
      <div className="section-heading">
        <div>
          <h2>Runtime actors</h2>
          <span>
            {s.actors.filter((a) => a.session.status === "WORKING").length}{" "}
            working · {s.actors.length} instantiated
          </span>
        </div>
      </div>
      {!s.actors.length ? (
        <Empty>No actor sessions have been recorded.</Empty>
      ) : (
        <div className={compact ? "actor-roster-list" : "agent-directory"}>
          {s.actors.map((a) => (
            <button
              key={a.session.id}
              className={
                "actor-row role-" +
                classToken(a.session.role ?? a.session.actor_type) +
                " " +
                (a.session.actor_type === "ORCHESTRATOR"
                  ? "orchestrator-row"
                  : "")
              }
              onClick={() => inspect({ kind: "actor", id: a.session.id })}
            >
              <span className="actor-glyph" aria-hidden="true">
                {a.session.actor_type === "ORCHESTRATOR" ? "◎" : "◇"}
              </span>
              <span className="actor-identity">
                <strong>{actorName(a)}</strong>
                <span>
                  {s.tasks.find((t) => t.id === a.session.current_task_id)
                    ?.description ??
                    (a.session.actor_type === "ORCHESTRATOR"
                      ? label(s.run.ui_phase)
                      : "No current assignment")}
                </span>
                <small>
                  {a.session.provider ?? "Core"}
                  {a.session.model ? " / " + a.session.model : ""} ·{" "}
                  {duration(a.timing.wall_ms)}
                </small>
              </span>
              <Badge status={a.session.status} />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

export function SkillsView({
  snapshot: s,
  inspect,
}: {
  snapshot: Snapshot;
  inspect: Inspect;
}) {
  const [catalog, setCatalog] = useState<SkillCatalogEntry[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    get<SkillCatalogEntry[]>("/api/skills", abort.signal)
      .then(setCatalog)
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) setError(String(failure));
      });
    return () => abort.abort();
  }, []);
  const historicalActivity =
    catalog && !error
      ? (s.skill_activity ?? []).filter(
          (activity) =>
            !catalog.some(
              (entry) =>
                entry.metadata.id + "@" + entry.metadata.version ===
                activity.ref,
            ),
        )
      : [];
  return (
    <section className="panel operational-panel">
      <div className="section-heading">
        <div>
          <h2>Skills</h2>
          <span>Discoverable capabilities, loaded when work needs them</span>
        </div>
        <span>{catalog?.length ?? "—"} available</span>
      </div>
      <div className="skill-lifecycle">
        <span>01 · Capability required</span>
        <span>02 · Metadata discovered</span>
        <span>03 · Permissions validated</span>
        <span>04 · Instructions loaded</span>
      </div>
      <p className="panel-body muted">
        Availability comes from the configured registry. Load counts and
        timestamps come from persisted events. Loading a skill does not prove
        its instructions succeeded.
      </p>
      {error ? (
        <div role="alert" className="panel-body">
          Skill registry unavailable. {error}
        </div>
      ) : !catalog ? (
        <Empty>Reading skill metadata…</Empty>
      ) : !catalog.length ? (
        <Empty>No skills discovered in the configured roots.</Empty>
      ) : (
        <div className="skill-grid">
          {catalog.map(({ metadata: m, source }) => {
            const ref = m.id + "@" + m.version,
              activity = s.skill_activity?.find((a) => a.ref === ref);
            const actors = s.actors.filter((a) =>
              activity?.actor_session_ids.includes(a.session.id),
            );
            const active = actors.some(
              (a) =>
                a.session.status === "WORKING" &&
                a.session.loaded_skills.includes(ref),
            );
            return (
              <article className="skill-card" key={ref}>
                <div className="section-heading">
                  <span className="skill-symbol" aria-hidden="true">
                    ⌘
                  </span>
                  <Badge
                    status={
                      active ? "ACTIVE" : activity ? "LOADED" : "AVAILABLE"
                    }
                  />
                </div>
                <h3>{m.id}</h3>
                <p>{m.description}</p>
                <div className="chip-row">
                  {m.capabilities.map((c) => (
                    <span key={c}>{c}</span>
                  ))}
                </div>
                <dl>
                  <dt>Version / source</dt>
                  <dd>
                    {m.version} · {source}
                  </dd>
                  <dt>Load events</dt>
                  <dd>{activity?.load_count ?? 0}</dd>
                  <dt>Last loaded</dt>
                  <dd>
                    {activity
                      ? new Date(activity.last_loaded_at).toLocaleString()
                      : "Not loaded in this run"}
                  </dd>
                  <dt>Permitted tools needed</dt>
                  <dd>{m.required_tools.join(", ") || "None"}</dd>
                </dl>
                <div className="chip-row">
                  {actors.map((a) => (
                    <button
                      key={a.session.id}
                      onClick={() =>
                        inspect({ kind: "actor", id: a.session.id })
                      }
                    >
                      {actorName(a)} ↗
                    </button>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      )}
      {historicalActivity.length > 0 && (
        <div className="panel-body">
          <h3>Historical skills outside this registry</h3>
          {historicalActivity.map((activity) => (
            <p key={activity.ref}>
              {activity.ref} · {activity.load_count} loads
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

export interface ActivityFilter {
  actor: string;
  task: string;
  phase: string;
  type: string;
  status: string;
}
export function filterEvents(events: Event[], f: ActivityFilter) {
  return events.filter(
    (e) =>
      (!f.actor || e.actor_session_id === f.actor) &&
      (!f.task || e.task_id === f.task) &&
      (!f.phase || e.phase === f.phase) &&
      (!f.type || e.event_type === f.type) &&
      (!f.status || (e.status ?? e.payload.status) === f.status),
  );
}

export function retainAvailableFilter(
  value: string,
  options: readonly (readonly [string, string])[],
) {
  return options.some(([option]) => option === value) ? value : "";
}
export function ActivityView({
  snapshot: s,
  events,
  inspect,
  compact = false,
}: {
  snapshot: Snapshot;
  events: Event[];
  inspect: Inspect;
  compact?: boolean;
}) {
  const [filters, setFilters] = useState<ActivityFilter>({
    actor: "",
    task: "",
    phase: "",
    type: "",
    status: "",
  });
  const actorOptions: [string, string][] = s.actors.map((actor) => [
    actor.session.id,
    actorName(actor),
  ]);
  const taskOptions: [string, string][] = s.tasks.map((task) => [
    task.id,
    task.description,
  ]);
  const phaseOptions: [string, string][] = [
    ...new Set(
      events
        .map((event) => event.phase)
        .filter((phase): phase is string => !!phase),
    ),
  ]
    .sort()
    .map((phase) => [phase, label(phase)] as [string, string]);
  const typeOptions: [string, string][] = [
    ...new Set(events.map((event) => event.event_type)),
  ]
    .sort()
    .map((type) => [type, label(type)] as [string, string]);
  const statusOptions: [string, string][] = [
    ...new Set(
      events
        .map((event) => event.status ?? event.payload.status)
        .filter((status): status is string => !!status),
    ),
  ]
    .sort()
    .map((status) => [status, label(status)] as [string, string]);
  const activeFilters: ActivityFilter = {
    actor: retainAvailableFilter(filters.actor, actorOptions),
    task: retainAvailableFilter(filters.task, taskOptions),
    phase: retainAvailableFilter(filters.phase, phaseOptions),
    type: retainAvailableFilter(filters.type, typeOptions),
    status: retainAvailableFilter(filters.status, statusOptions),
  };
  const hasFilters = Object.values(activeFilters).some(Boolean);
  const filtered = filterEvents(events, activeFilters),
    shown = compact ? filtered.slice(-6) : filtered;
  const field = (
    key: keyof ActivityFilter,
    title: string,
    options: [string, string][],
  ) => (
    <label className="compact-field">
      {title}
      <select
        aria-label={title}
        value={activeFilters[key]}
        onChange={(event) =>
          setFilters({ ...activeFilters, [key]: event.target.value })
        }
      >
        <option value="">All</option>
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <section className="panel activity-panel">
      <div className="section-heading">
        <div>
          <h2>{compact ? "Latest activity" : "Structured activity"}</h2>
          <span>
            {compact
              ? "Latest persisted events"
              : "Latest 200 events · ordered by server sequence"}
          </span>
        </div>
        <span>#{s.last_event_sequence}</span>
      </div>
      {!compact && (
        <div className="activity-filters">
          {field("actor", "Agent", actorOptions)}
          {field("task", "Task", taskOptions)}
          {field("phase", "Phase", phaseOptions)}
          {field("type", "Event type", typeOptions)}
          {field("status", "Event status", statusOptions)}
          {hasFilters && (
            <button
              type="button"
              className="text-link"
              onClick={() =>
                setFilters({
                  actor: "",
                  task: "",
                  phase: "",
                  type: "",
                  status: "",
                })
              }
            >
              Clear filters
            </button>
          )}
        </div>
      )}
      <div className={compact ? "" : "activity-scroll"}>
        {shown.length ? (
          shown.map((e) => (
            <div className="activity-row" key={e.id}>
              <time dateTime={e.occurred_at}>
                {new Date(e.occurred_at).toLocaleTimeString()}
              </time>
              <span className="event-mark" aria-hidden="true">
                •
              </span>
              <div>
                <strong>{label(e.event_type)}</strong>
                <span>
                  {e.payload.summary ??
                    e.payload.reason ??
                    (e.phase ? label(e.phase) : "Run event")}
                </span>
                {e.task_id && (
                  <button
                    className="text-link"
                    onClick={() => inspect({ kind: "task", id: e.task_id! })}
                  >
                    {s.tasks.find((t) => t.id === e.task_id)?.description ??
                      "Inspect task"}{" "}
                    ↗
                  </button>
                )}
                {!e.task_id && e.actor_session_id && (
                  <button
                    className="text-link"
                    onClick={() =>
                      inspect({ kind: "actor", id: e.actor_session_id! })
                    }
                  >
                    Inspect actor ↗
                  </button>
                )}
              </div>
              <small>#{e.sequence}</small>
            </div>
          ))
        ) : (
          <Empty>
            {events.length
              ? "No events match these filters."
              : "No structured activity recorded yet."}
          </Empty>
        )}
      </div>
    </section>
  );
}
