import { useEffect, useState } from "react";
import { get } from "./api";
import { Badge, Empty } from "./ui";
import type { Snapshot } from "./types";
import type { Inspect } from "./runtime";

export function DeliveryView({
  snapshot,
  initialPath = "",
  inspect: inspectRecord,
}: {
  snapshot: Snapshot;
  initialPath?: string;
  inspect?: Inspect;
}) {
  const report = snapshot.guardians.at(-1);
  const [diff, setDiff] = useState<{
    path: string;
    diff: string;
    truncated: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!initialPath) return;
    const abort = new AbortController();
    get<{ path: string; diff: string; truncated: boolean }>(
      "/api/runs/" +
        snapshot.run.id +
        "/diff?path=" +
        encodeURIComponent(initialPath),
      abort.signal,
    )
      .then((value) => {
        setDiff(value);
        setError("");
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) setError(String(failure));
      });
    return () => abort.abort();
  }, [initialPath, snapshot.run.id]);
  async function inspect(path: string) {
    try {
      setDiff(
        await get(
          `/api/runs/${snapshot.run.id}/diff?path=${encodeURIComponent(path)}`,
        ),
      );
      setError("");
    } catch (failure) {
      setError(String(failure));
    }
  }
  return (
    <section className="panel operational-panel">
      <div className="section-heading">
        <h2>Changes and delivery</h2>
        <span>{report?.changes.length ?? 0} inspected paths</span>
      </div>
      <div className="delivery-checkpoints">
        {[
          ["Independent review", snapshot.reviews.at(-1)?.result.overall],
          [
            "Implementation Guardian",
            snapshot.guardians.find((r) => r.checkpoint === "implementation")
              ?.passed,
          ],
          [
            "Documentation",
            snapshot.artifacts.some((a) => a.type === "documentation") ||
              undefined,
          ],
          ["Final validation", snapshot.final_validations.at(-1)?.passed],
          [
            "Final Guardian",
            snapshot.guardians.find((r) => r.checkpoint === "final")?.passed,
          ],
          ["Commit", snapshot.delivery?.commit_attached || undefined],
        ].map(([name, value]) => (
          <div key={String(name)}>
            <strong>{name}</strong>
            <Badge
              status={
                value === true || value === "PASS"
                  ? "PASS"
                  : value === false || value === "FAIL"
                    ? "FAIL"
                    : "PENDING"
              }
            />
          </div>
        ))}
      </div>
      {snapshot.delivery && (
        <div className="panel-body">
          <h3>Git delivery</h3>
          <dl>
            <dt>Commit</dt>
            <dd>
              <code>{snapshot.delivery.commit_sha ?? "Intent recorded"}</code>
            </dd>
            <dt>Branch</dt>
            <dd>{snapshot.delivery.branch}</dd>
            <dt>Push</dt>
            <dd>
              {snapshot.delivery.push_status}{" "}
              {snapshot.delivery.remote && `· ${snapshot.delivery.remote}`}
            </dd>
          </dl>
          <details>
            <summary>Commit message</summary>
            <pre>{snapshot.delivery.commit_message}</pre>
          </details>
        </div>
      )}
      {report ? (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Inspected changes</caption>
            <thead>
              <tr>
                <th>Path</th>
                <th>Change</th>
                <th>Added</th>
                <th>Deleted</th>
              </tr>
            </thead>
            <tbody>
              {report.changes.map((change) => (
                <tr key={change.path}>
                  <td>
                    <button
                      className="text-link"
                      onClick={() => void inspect(change.path)}
                    >
                      {change.path}
                    </button>
                  </td>
                  <td>{change.status}</td>
                  <td>+{change.added_lines}</td>
                  <td>−{change.deleted_lines}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>Change Guardian has not inspected this workspace yet.</Empty>
      )}
      {error && (
        <p className="panel-body" role="alert">
          {error}
        </p>
      )}
      {diff && (
        <div className="panel-body">
          <h3>{diff.path}</h3>
          <pre className="diff-view">
            {diff.diff || "No textual difference."}
          </pre>
          {diff.truncated && <p>Diff truncated at the API display limit.</p>}
        </div>
      )}
      <div className="panel-body">
        <h3>Artifacts</h3>
        {snapshot.artifacts.length ? (
          snapshot.artifacts.map((artifact) => (
            <div className="artifact-row" key={artifact.id}>
              <strong>{artifact.type}</strong>
              <span>{artifact.path_or_uri}</span>
              {artifact.task_id && inspectRecord && (
                <button
                  className="text-link"
                  onClick={() =>
                    inspectRecord({ kind: "task", id: artifact.task_id! })
                  }
                >
                  Inspect originating task ?
                </button>
              )}
              <code>{artifact.content_hash}</code>
            </div>
          ))
        ) : (
          <p>No artifacts recorded.</p>
        )}
      </div>
      <details className="panel-body">
        <summary>
          Guardian audit history · {snapshot.guardians.length} checkpoints
        </summary>
        {snapshot.guardians.map((guardian) => (
          <article className="detail-card" key={guardian.id}>
            <h3>
              {guardian.checkpoint}{" "}
              <Badge status={guardian.passed ? "PASS" : "FAIL"} />
            </h3>
            <code>{guardian.tree_hash}</code>
            <ul>
              {guardian.findings.map((finding) => (
                <li key={finding.id}>
                  {finding.category}: {finding.summary} · {finding.source_ref}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </details>
    </section>
  );
}
