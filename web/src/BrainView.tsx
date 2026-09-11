import { useEffect, useState } from "react";
import { get } from "./api";
import { FlowGraph } from "./Graphs";
import { Badge, Empty, label } from "./ui";
import type { Brain, Snapshot } from "./types";

type BrainRequest =
  | { id: string; status: "loading" }
  | { id: string; status: "success"; value: Brain }
  | { id: string; status: "error"; message: string };

export function BrainView({ snapshot }: { snapshot: Snapshot }) {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [requestAttempt, setRequestAttempt] = useState(0);
  const [request, setRequest] = useState<BrainRequest>({
    id: "",
    status: "loading",
  });
  const [categorySelection, setCategorySelection] = useState({
    requestId: "",
    value: "",
  });
  const [graph, setGraph] = useState(false);

  const projectId = snapshot.run.project_id;
  const runId = snapshot.run.id;
  const requestUrl = `/api/projects/${projectId}/brain?run_id=${runId}&query=${encodeURIComponent(submitted)}`;
  const requestId = JSON.stringify([
    projectId,
    runId,
    submitted,
    requestAttempt,
  ]);
  const currentRequest: BrainRequest =
    request.id === requestId ? request : { id: requestId, status: "loading" };
  const brain =
    currentRequest.status === "success" ? currentRequest.value : null;
  const error = currentRequest.status === "error" ? currentRequest.message : "";
  const loading = currentRequest.status === "loading";

  useEffect(() => {
    const controller = new AbortController();
    get<Brain>(requestUrl, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setRequest({ id: requestId, status: "success", value: result });
        }
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) {
          setRequest({
            id: requestId,
            status: "error",
            message: String(failure),
          });
        }
      });
    return () => controller.abort();
  }, [requestId, requestUrl]);

  const categories = brain
    ? [...new Set(brain.matches.map((match) => match.item.type))].sort()
    : [];
  const category =
    categorySelection.requestId === requestId &&
    categories.includes(categorySelection.value)
      ? categorySelection.value
      : "";
  const matches =
    brain?.matches.filter(
      (match) => !category || match.item.type === category,
    ) ?? [];
  const entities = brain?.entities.slice(0, 150) ?? [];
  const ids = new Set(entities.map((entity) => entity.id));

  const retrySearch = () => {
    setRequestAttempt((attempt) => attempt + 1);
  };

  return (
    <section
      className="panel operational-panel"
      aria-busy={loading}
      aria-label="Project Brain"
    >
      <div className="section-heading">
        <h2>Project Brain</h2>
        {brain && <Badge status={brain.freshness.fresh ? "PASS" : "STALE"} />}
      </div>
      <div className="panel-body">
        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            setSubmitted(query);
            setRequestAttempt((attempt) => attempt + 1);
            setCategorySelection({ requestId: "", value: "" });
          }}
        >
          <label className="field-label">
            Search project knowledge
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Architecture, conventions, decisions…"
            />
          </label>
          <button type="submit">{loading ? "Searching…" : "Search"}</button>
        </form>
        {error && (
          <div role="alert">
            <p>{error}</p>
            <button type="button" onClick={retrySearch}>
              Retry search
            </button>
          </div>
        )}
        {brain && (
          <>
            <dl className="brain-health">
              <dt>Indexed commit</dt>
              <dd>
                <code>{brain.freshness.indexed_commit ?? "Not indexed"}</code>
              </dd>
              <dt>Inspected HEAD</dt>
              <dd>
                <code>{brain.freshness.current_commit}</code>
              </dd>
              <dt>Workspace</dt>
              <dd>{brain.inspected_root}</dd>
              <dt>Active facts</dt>
              <dd>{brain.freshness.active_items}</dd>
              <dt>Uncommitted paths</dt>
              <dd>{brain.freshness.dirty_paths.join(", ") || "None"}</dd>
            </dl>
            <div className="view-toolbar">
              <label>
                Category{" "}
                <select
                  value={category}
                  onChange={(event) =>
                    setCategorySelection({
                      requestId,
                      value: event.target.value,
                    })
                  }
                >
                  <option value="">All categories</option>
                  {categories.map((type) => (
                    <option key={type} value={type}>
                      {label(type)}
                    </option>
                  ))}
                </select>
              </label>
              <button aria-pressed={graph} onClick={() => setGraph(!graph)}>
                Knowledge graph
              </button>
            </div>
          </>
        )}
      </div>
      {graph && brain && (
        <>
          <FlowGraph
            name="Project knowledge graph"
            nodes={entities.map((entity) => ({
              id: entity.id,
              position: { x: 0, y: 0 },
              data: { label: entity.name },
              className: "task-node",
            }))}
            edges={brain.relations
              .filter(
                (relation) =>
                  ids.has(relation.source_entity_id) &&
                  ids.has(relation.target_entity_id),
              )
              .map((relation) => ({
                id: relation.id,
                source: relation.source_entity_id,
                target: relation.target_entity_id,
                label: relation.relation_type,
                type: "smoothstep",
              }))}
          />
          <p className="panel-body">
            Showing {entities.length} of {brain.entities.length} source-backed
            entities.
          </p>
        </>
      )}
      {loading ? (
        <Empty>
          {submitted
            ? "Searching committed knowledge…"
            : "Retrieving committed knowledge…"}
        </Empty>
      ) : error ? null : !brain || !matches.length ? (
        <Empty>No matching knowledge. Try a different query.</Empty>
      ) : (
        <div className="memory-grid">
          {matches.map(({ item, sources }) => (
            <article className="memory-card" key={item.id}>
              <div>
                <span className="eyebrow">{label(item.type)}</span>
                <span>{Math.round(item.confidence * 100)}% confidence</span>
              </div>
              <h3>{item.title}</h3>
              {snapshot.context_memory_ids?.includes(item.id) && (
                <span className="context-tag">Included in run context</span>
              )}
              <pre>{item.content}</pre>
              <dl>
                <dt>Source commit</dt>
                <dd>
                  <code>{item.source_commit}</code>
                </dd>
                <dt>Verified</dt>
                <dd>{new Date(item.last_verified_at).toLocaleString()}</dd>
                <dt>Sources</dt>
                <dd>
                  {sources.map((source) => (
                    <p key={source.source_ref}>{source.source_ref}</p>
                  ))}
                </dd>
              </dl>
              {item.introduced_by_run && (
                <a
                  className="text-link"
                  href={`/runs/${item.introduced_by_run}`}
                >
                  Originating run {item.introduced_by_run.slice(0, 8)} ↗
                </a>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
