import { useMemo, useState } from "react";
import type { Project, Run } from "./types";
import { Badge } from "./ui";

const finishedStates = new Set(["COMPLETED", "CANCELLED"]);
const attentionStates = new Set(["BLOCKED", "FAILED", "HUMAN_REVIEW_REQUIRED"]);

function projectRuns(runs: Run[], projectId: string) {
  return runs.filter((run) => run.project_id === projectId);
}

function displayRepoRoot(repoRoot: string) {
  return repoRoot
    .replace(/^[A-Za-z]:\\Users\\[^\\]+(?=\\)/i, "~")
    .replace(/^\/(?:Users|home)\/[^/]+(?=\/)/, "~");
}

export function Overview({
  projects,
  runs,
  selectedProjectId,
}: {
  projects: Project[];
  runs: Run[];
  selectedProjectId: string | null;
}) {
  const [historyPage, setHistoryPage] = useState(0);
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? null;
  const visibleRuns = useMemo(
    () => (selectedProject ? projectRuns(runs, selectedProject.id) : runs),
    [runs, selectedProject],
  );
  const activeRuns = visibleRuns.filter(
    (run) => !finishedStates.has(run.state),
  );
  const completedRuns = visibleRuns.filter((run) => run.state === "COMPLETED");
  const attentionRuns = visibleRuns.filter((run) =>
    attentionStates.has(run.state),
  );
  const repairCycles = visibleRuns.reduce(
    (total, run) => total + run.repair_iteration,
    0,
  );
  const pageCount = Math.max(1, Math.ceil(visibleRuns.length / 50));

  return (
    <>
      <div className="page-heading overview-heading">
        <div>
          <span className="eyebrow">
            {selectedProject
              ? "PROJECT WORKSPACE"
              : "YOUR ENGINEERING WORKSPACE"}
          </span>
          <h1>{selectedProject?.name ?? "Local Mission Control"}</h1>
          <p>
            {selectedProject
              ? displayRepoRoot(selectedProject.repo_root) +
                " · " +
                selectedProject.default_branch
              : "Projects, runs, agents, and evidence in one local workspace."}
          </p>
        </div>
        {selectedProject && (
          <a className="clear-project-filter" href="/#projects">
            View all projects
          </a>
        )}
      </div>

      <section
        id="projects"
        className="panel overview-section"
        aria-labelledby="projects-heading"
      >
        <div className="section-heading">
          <div>
            <span className="eyebrow">LOCAL WORKSPACE</span>
            <h2 id="projects-heading">Projects</h2>
          </div>
          <span>
            {projects.length} registered{" "}
            {projects.length === 1 ? "project" : "projects"}
          </span>
        </div>
        {projects.length ? (
          <div className="project-grid">
            {projects.map((project) => {
              const relatedRuns = projectRuns(runs, project.id);
              const latest = relatedRuns[0] ?? null;
              const active = relatedRuns.filter(
                (run) => !finishedStates.has(run.state),
              ).length;
              const selected = selectedProject?.id === project.id;
              return (
                <article
                  key={project.id}
                  className={
                    "project-card" + (selected ? " selected-project" : "")
                  }
                  data-project-id={project.id}
                >
                  <a
                    className="project-card-link"
                    href={"/?project=" + project.id + "#projects"}
                    aria-current={selected ? "page" : undefined}
                  >
                    <span className="project-card-icon" aria-hidden="true">
                      {project.name.slice(0, 1).toUpperCase()}
                    </span>
                    <span>
                      <small>PROJECT</small>
                      <strong>{project.name}</strong>
                    </span>
                    <span className="project-card-arrow" aria-hidden="true">
                      ↗
                    </span>
                  </a>
                  <code title={project.repo_root}>
                    {displayRepoRoot(project.repo_root)}
                  </code>
                  <dl>
                    <div>
                      <dt>Default branch</dt>
                      <dd>{project.default_branch}</dd>
                    </div>
                    <div>
                      <dt>Runs</dt>
                      <dd>{relatedRuns.length}</dd>
                    </div>
                    <div>
                      <dt>Active</dt>
                      <dd>{active}</dd>
                    </div>
                  </dl>
                  {latest ? (
                    <a className="project-latest" href={"/runs/" + latest.id}>
                      Open latest run
                      <span>{latest.request}</span>
                    </a>
                  ) : (
                    <p className="project-latest project-latest-empty">
                      No runs recorded
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="empty overview-empty">
            <span>◇</span>
            <h3>No registered projects</h3>
            <p>
              Run <code>orqalis init --repo PATH</code>, then refresh this page.
            </p>
          </div>
        )}
      </section>

      <section className="overview-stat-grid" aria-label="Workspace statistics">
        <div>
          <span>Projects</span>
          <strong>{selectedProject ? 1 : projects.length}</strong>
          <small>
            {selectedProject ? "Current filter" : "Registered locally"}
          </small>
        </div>
        <div>
          <span>Active runs</span>
          <strong>{activeRuns.length}</strong>
          <small>Persisted non-terminal runs</small>
        </div>
        <div>
          <span>Completed</span>
          <strong>{completedRuns.length}</strong>
          <small>Accepted and delivered</small>
        </div>
        <div>
          <span>Needs attention</span>
          <strong>{attentionRuns.length}</strong>
          <small>{repairCycles} recorded repair cycles</small>
        </div>
      </section>

      <div className="overview-columns">
        <section
          id="active-runs"
          className="panel home-runs"
          aria-labelledby="active-runs-heading"
        >
          <div className="section-heading">
            <h2 id="active-runs-heading">Active runs</h2>
            <span>{activeRuns.length} running or awaiting action</span>
          </div>
          {activeRuns.length ? (
            activeRuns
              .slice(0, 6)
              .map((run) => <RunLink key={run.id} run={run} />)
          ) : (
            <div className="empty small-empty overview-empty">
              <span>✓</span>
              <h3>No active runs</h3>
              <p>New and resumed work will appear here.</p>
            </div>
          )}
        </section>

        <section
          id="runs"
          className="panel home-runs"
          aria-labelledby="run-history-heading"
        >
          <div className="section-heading">
            <h2 id="run-history-heading">
              {selectedProject ? "Project run history" : "Run history"}
            </h2>
            <span>{visibleRuns.length} runs</span>
          </div>
          {visibleRuns.length ? (
            visibleRuns
              .slice(historyPage * 50, (historyPage + 1) * 50)
              .map((run) => <RunLink key={run.id} run={run} />)
          ) : (
            <div className="empty small-empty overview-empty">
              <span>◎</span>
              <h3>No runs yet</h3>
              <p>Runs created through Orqalis will appear here.</p>
            </div>
          )}
          {visibleRuns.length > 50 && (
            <nav className="history-pagination" aria-label="Run history pages">
              <button
                disabled={historyPage === 0}
                onClick={() => setHistoryPage((page) => page - 1)}
              >
                Previous runs
              </button>
              <span>
                Page {historyPage + 1} of {pageCount}
              </span>
              <button
                disabled={historyPage + 1 >= pageCount}
                onClick={() => setHistoryPage((page) => page + 1)}
              >
                Next runs
              </button>
            </nav>
          )}
        </section>
      </div>
    </>
  );
}

function RunLink({ run }: { run: Run }) {
  return (
    <a className="history-row" href={"/runs/" + run.id}>
      <div>
        <strong>{run.request}</strong>
        <small>
          {run.target_branch} · {new Date(run.created_at).toLocaleString()}
        </small>
      </div>
      <Badge status={run.state} />
      <span aria-hidden="true">↗</span>
    </a>
  );
}
