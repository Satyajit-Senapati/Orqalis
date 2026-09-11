import { useEffect, useRef } from "react";
import { duration } from "./api";
import { Badge, Empty, label } from "./ui";
import {
  actorName,
  taskFiles,
  taskRelations,
  type Inspect,
  type Selection,
} from "./runtime";
import type { Event, Snapshot } from "./types";

export function Inspector({
  selection,
  snapshot: s,
  events,
  inspect,
  openFile,
  openMemory,
}: {
  selection: Selection;
  snapshot: Snapshot;
  events: Event[];
  inspect: Inspect;
  openFile: (path: string) => void;
  openMemory: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const active = !!selection;
  const selectionKey = selection ? selection.kind + ":" + selection.id : null;
  const timestamp = (value: string | null | undefined) =>
    value ? new Date(value).toLocaleString() : "Not recorded";
  useEffect(() => {
    const node = dialog.current;
    if (!node || !active) return;
    const previous = document.activeElement as HTMLElement | null;
    node.showModal();
    return () => {
      node.close();
      previous?.focus();
    };
  }, [active]);
  useEffect(() => {
    const node = dialog.current;
    if (!node || !selectionKey) return;
    requestAnimationFrame(() => {
      node.scrollTop = 0;
      titleRef.current?.focus({ preventScroll: true });
    });
  }, [selectionKey]);
  if (!selection) return null;
  const actor =
    selection.kind === "actor"
      ? s.actors.find((a) => a.session.id === selection.id)
      : undefined;
  const task =
    selection.kind === "task"
      ? s.tasks.find((t) => t.id === selection.id)
      : undefined;
  const attempts = s.attempts.filter((a) =>
    actor
      ? a.assigned_actor_session_id === actor.session.id
      : a.task_id === task?.id,
  );
  const taskIds = [
    ...new Set(attempts.map((a) => a.task_id).concat(task ? [task.id] : [])),
  ];
  const attemptIds = new Set(attempts.map((a) => a.id));
  const providers = s.providers.filter((p) =>
    actor
      ? p.actor_session_id === actor.session.id
      : attemptIds.has(p.task_execution_id),
  );
  const tools = s.tools.filter((t) =>
    actor
      ? t.actor_session_id === actor.session.id
      : attemptIds.has(t.task_execution_id),
  );
  const artifacts = s.artifacts.filter(
    (a) => a.task_id && taskIds.includes(a.task_id),
  );
  const files = taskFiles(s, taskIds);
  const related = events
    .filter((e) =>
      actor ? e.actor_session_id === actor.session.id : e.task_id === task?.id,
    )
    .slice(-8);
  const latestContext = providers.filter((p) => p.context_summary).at(-1);
  const criteria =
    s.goal?.criteria.filter((c) =>
      task
        ? task.acceptance_criterion_ids.includes(c.id)
        : s.tasks.some(
            (t) =>
              taskIds.includes(t.id) &&
              t.acceptance_criterion_ids.includes(c.id),
          ),
    ) ?? [];
  const relations = task ? taskRelations(s, task.id) : null;
  const taskLink = (id: string) => (
    <button className="text-link" onClick={() => inspect({ kind: "task", id })}>
      {s.tasks.find((t) => t.id === id)?.description ?? id} ↗
    </button>
  );
  const title = actor
    ? actorName(actor)
    : (task?.description ?? "Record unavailable");
  const timing = actor?.timing ?? (task ? s.task_timing[task.id] : undefined);
  return (
    <dialog
      ref={dialog}
      className="runtime-inspector"
      aria-labelledby="inspector-title"
      onCancel={() => inspect(null)}
    >
      <div className="inspector-heading">
        <span className="eyebrow">{selection.kind} inspector</span>
        <button aria-label="Close inspector" onClick={() => inspect(null)}>
          ×
        </button>
      </div>
      <div className="inspector-content">
        <h2 ref={titleRef} id="inspector-title" tabIndex={-1}>
          {title}
        </h2>
        <Badge
          status={actor?.session.status ?? task?.status ?? "UNAVAILABLE"}
        />
        <p className="inspector-summary">
          {task?.expected_outcome ??
            (actor?.session.actor_type === "ORCHESTRATOR"
              ? "Authoritative workflow controller. Delegates work and persists transitions."
              : "Specialized worker. Results return to the Orchestrator for workflow decisions.")}
        </p>
        <dl>
          <dt>Role</dt>
          <dd>
            {label(
              actor?.session.role ?? task?.preferred_role ?? "orchestrator",
            )}
          </dd>
          <dt>Started</dt>
          <dd>{timestamp(actor?.session.started_at ?? task?.started_at)}</dd>
          <dt>Completed</dt>
          <dd>
            {timestamp(actor?.session.completed_at ?? task?.completed_at)}
          </dd>
          <dt>Elapsed / working</dt>
          <dd>
            {timing
              ? duration(timing.wall_ms) + " / " + duration(timing.active_ms)
              : "Not recorded"}
          </dd>
          <dt>Queue / waiting / blocked</dt>
          <dd>
            {timing
              ? [timing.queue_ms, timing.waiting_ms, timing.blocked_ms]
                  .map(duration)
                  .join(" / ")
              : "Not recorded"}
          </dd>
          <dt>Retries</dt>
          <dd>
            {task
              ? Math.max(0, task.attempt_count - 1)
              : attempts.filter((a) => a.attempt > 1).length}
          </dd>
          {actor && (
            <>
              <dt>Provider / model</dt>
              <dd>
                {actor.session.provider ?? "Core runtime"} /{" "}
                {actor.session.model ?? "Not reported"}
              </dd>
              <dt>Completed / attempted</dt>
              <dd>
                {actor.session.tasks_completed} /{" "}
                {actor.session.tasks_attempted}
              </dd>
              <dt>Current task</dt>
              <dd>
                {actor.session.current_task_id
                  ? taskLink(actor.session.current_task_id)
                  : "No current assignment"}
              </dd>
              <dt>Loaded skills</dt>
              <dd>
                {actor.session.loaded_skills.join(", ") ||
                  "No dynamic skills recorded"}
              </dd>
            </>
          )}
        </dl>
        {task && (
          <>
            <h3>Why this task runs</h3>
            <p>{task.expected_outcome}</p>
            <dl>
              <dt>Capabilities</dt>
              <dd>
                {task.required_capabilities.join(", ") || "Role capabilities"}
              </dd>
              <dt>Expected artifacts</dt>
              <dd>{task.expected_artifacts.join(", ") || "Not specified"}</dd>
            </dl>
            <h3>Dependencies</h3>
            {relations?.dependencies.length ? (
              relations.dependencies.map((t) => (
                <p key={t.id}>
                  {taskLink(t.id)} <Badge status={t.status} />
                </p>
              ))
            ) : (
              <p>No prerequisites.</p>
            )}
            <h3>Subsequent tasks</h3>
            {relations?.subsequent.length ? (
              relations.subsequent.map((t) => (
                <p key={t.id}>{taskLink(t.id)}</p>
              ))
            ) : (
              <p>No dependent task in this plan.</p>
            )}
            {task.parent_task_id && (
              <p>Repairs {taskLink(task.parent_task_id)}</p>
            )}
          </>
        )}
        <h3>Attempts and ownership</h3>
        {attempts.length ? (
          attempts.map((a) => {
            const owner = s.actors.find(
              (item) => item.session.id === a.assigned_actor_session_id,
            );
            return (
              <div className="inspector-record" key={a.id}>
                <div>{taskLink(a.task_id)}</div>
                <div>
                  Attempt {a.attempt} · <Badge status={a.status} />
                </div>
                {owner && (
                  <button
                    className="text-link"
                    onClick={() =>
                      inspect({ kind: "actor", id: owner.session.id })
                    }
                  >
                    {actorName(owner)} ↗
                  </button>
                )}
                <small>
                  {a.started_at} → {a.completed_at ?? "Open"}
                </small>
              </div>
            );
          })
        ) : (
          <p>No execution attempts yet.</p>
        )}
        <h3>Context and memory</h3>
        <p>
          {latestContext?.context_summary ??
            "Per-invocation context attribution was not recorded for this selection."}
        </p>
        {!!latestContext?.context_memory_ids?.length && (
          <details>
            <summary>
              {latestContext.context_memory_ids.length} memory references
            </summary>
            <ul>
              {latestContext.context_memory_ids.map((id) => (
                <li key={id}>
                  <code>{id}</code>
                </li>
              ))}
            </ul>
          </details>
        )}
        <button className="text-link" onClick={openMemory}>
          Inspect Project Brain ↗
        </button>
        <h3>Acceptance and verification</h3>
        {criteria.length ? (
          criteria.map((c) => (
            <div className="inspector-record" key={c.id}>
              <strong>
                {c.key} · {c.description}
              </strong>
              <Badge status={c.status} />
              <p>
                {label(c.validation_spec.kind)} · {c.evidence_refs.length}{" "}
                evidence records
              </p>
              {s.reviews
                .at(-1)
                ?.result.criteria.filter((r) => r.criterion_id === c.id)
                .map((r) => (
                  <p key={r.criterion_id}>{r.reason}</p>
                ))}
            </div>
          ))
        ) : (
          <p>No acceptance criterion attributed to this selection.</p>
        )}
        <h3>Files and artifacts</h3>
        {files.length ? (
          files.map((path) => (
            <p key={path}>
              {s.guardians.at(-1)?.changes.some((c) => c.path === path) ? (
                <button className="text-link" onClick={() => openFile(path)}>
                  {path} · inspect diff ↗
                </button>
              ) : (
                <code>{path}</code>
              )}
            </p>
          ))
        ) : (
          <p>No source evidence or artifact paths attributed.</p>
        )}
        {artifacts.map((a) => (
          <div className="inspector-record" key={a.id}>
            <strong>{a.type}</strong>
            <p>{a.path_or_uri}</p>
            <code>{a.content_hash}</code>
          </div>
        ))}
        <h3>Tool activity · {tools.length}</h3>
        {tools.length ? (
          tools.map((t) => (
            <details className="inspector-record" key={t.id}>
              <summary>
                {t.tool} <Badge status={t.status} />
              </summary>
              <pre>{t.observation?.summary ?? "No result recorded"}</pre>
              <small>
                {t.started_at} → {t.completed_at ?? "Open"}
              </small>
            </details>
          ))
        ) : (
          <p>No tool calls attributed.</p>
        )}
        <h3>Provider activity · {providers.length}</h3>
        {providers.map((p) => (
          <details className="inspector-record" key={p.id}>
            <summary>
              {p.provider} / {p.model} <Badge status={p.status} />
            </summary>
            <dl>
              <dt>Input / output tokens</dt>
              <dd>
                {p.usage?.input_tokens ?? "Not reported"} /{" "}
                {p.usage?.output_tokens ?? "Not reported"}
              </dd>
              <dt>Error</dt>
              <dd>{p.error_code ?? "None recorded"}</dd>
            </dl>
          </details>
        ))}
        <h3>Recent events</h3>
        {related.length ? (
          related.map((e) => (
            <div className="inspector-record" key={e.id}>
              <strong>{label(e.event_type)}</strong>
              <p>{e.payload.summary ?? e.payload.reason ?? e.payload.status}</p>
              <small>
                #{e.sequence} · {new Date(e.occurred_at).toLocaleString()}
              </small>
            </div>
          ))
        ) : (
          <Empty>No matching events in the latest 200-event window.</Empty>
        )}
      </div>
    </dialog>
  );
}
