import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type { Project, Run } from "./types";
import { label, statusTone } from "./ui";

interface SidebarProps {
  projects: Project[];
  runs: Run[];
  runId: string | null;
  selectedProjectId: string | null;
  coreStatus: string;
}

export function Sidebar({
  projects,
  runs,
  runId,
  selectedProjectId,
  coreStatus,
}: SidebarProps) {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const projectRuns = selectedProjectId
    ? runs.filter((run) => run.project_id === selectedProjectId)
    : runs;
  const latestRun = projectRuns[0] ?? runs[0] ?? null;

  function closeNavigation(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) requestAnimationFrame(() => toggleRef.current?.focus());
  }

  useEffect(() => {
    document.body.classList.toggle("sidebar-menu-open", open);
    return () => document.body.classList.remove("sidebar-menu-open");
  }, [open]);

  useEffect(() => {
    const media = matchMedia("(max-width: 900px)");
    const handleViewport = () => {
      if (!media.matches) setOpen(false);
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (open && event.key === "Escape") {
        event.preventDefault();
        closeNavigation(true);
      }
    };
    media.addEventListener("change", handleViewport);
    addEventListener("keydown", handleEscape);
    return () => {
      media.removeEventListener("change", handleViewport);
      removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  function retainDrawerFocus(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!open || event.key !== "Tab" || !panelRef.current) return;
    const focusable = [
      ...panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ].filter((element) => !element.hasAttribute("hidden"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <>
      <aside className={"sidebar" + (open ? " sidebar-open" : "")}>
        <div className="sidebar-header">
          <a
            className="brand"
            href="/"
            aria-label="Orqalis home"
            onClick={() => closeNavigation()}
          >
            <span className="brand-mark">◈</span>ORQALIS
            <span className="local-tag">LOCAL</span>
          </a>
          <button
            ref={toggleRef}
            className="sidebar-toggle"
            type="button"
            aria-controls="sidebar-navigation"
            aria-expanded={open}
            aria-label={open ? "Close navigation" : "Open navigation"}
            onClick={() => setOpen((current) => !current)}
          >
            <span aria-hidden="true">{open ? "×" : "☰"}</span>
            Menu
          </button>
        </div>

        <div
          ref={panelRef}
          id="sidebar-navigation"
          className="sidebar-content"
          onKeyDown={retainDrawerFocus}
        >
          <div className="sidebar-scroll">
            <a
              className="workspace"
              href="/#projects"
              onClick={() => closeNavigation()}
            >
              <span className="workspace-icon" aria-hidden="true">
                ⌘
              </span>
              <div>
                <strong>Local workspace</strong>
                <small>
                  {projects.length} registered{" "}
                  {projects.length === 1 ? "project" : "projects"}
                </small>
              </div>
              <span className="workspace-arrow" aria-hidden="true">
                ↗
              </span>
            </a>

            <span className="nav-caption">WORKSPACE</span>
            <nav aria-label="Primary">
              <a
                href="/"
                className={!runId && !selectedProjectId ? "selected" : ""}
                aria-current={!runId && !selectedProjectId ? "page" : undefined}
                onClick={() => closeNavigation()}
              >
                <span aria-hidden="true">▦</span>Overview
              </a>
              <a
                href="/#projects"
                className={!runId && selectedProjectId ? "selected" : ""}
                aria-current={!runId && selectedProjectId ? "page" : undefined}
                onClick={() => closeNavigation()}
              >
                <span aria-hidden="true">◇</span>Projects
              </a>
              <a
                href={latestRun ? "/runs/" + latestRun.id : "/#runs"}
                className={runId ? "selected" : ""}
                aria-current={runId ? "page" : undefined}
                onClick={() => closeNavigation()}
              >
                <span aria-hidden="true">◎</span>Mission Control
              </a>
            </nav>

            <div className="nav-caption project-heading">
              PROJECTS <span>{projects.length}</span>
            </div>
            {projects.length ? (
              <nav className="project-nav" aria-label="Projects">
                {projects.map((project) => {
                  const count = runs.filter(
                    (run) => run.project_id === project.id,
                  ).length;
                  const selected = project.id === selectedProjectId;
                  return (
                    <a
                      key={project.id}
                      href={"/?project=" + project.id + "#projects"}
                      className={selected ? "current-project" : ""}
                      aria-current={selected ? "page" : undefined}
                      onClick={() => closeNavigation()}
                    >
                      <span className="project-glyph" aria-hidden="true">
                        {project.name.slice(0, 1).toUpperCase()}
                      </span>
                      <span className="project-nav-copy">
                        <strong>{project.name}</strong>
                        <small>
                          {project.default_branch} · {count}{" "}
                          {count === 1 ? "run" : "runs"}
                        </small>
                      </span>
                    </a>
                  );
                })}
              </nav>
            ) : (
              <p className="sidebar-empty">No registered projects yet.</p>
            )}

            <div className="nav-caption recent-heading">
              RECENT RUNS <span>{projectRuns.length}</span>
            </div>
            {projectRuns.length ? (
              <nav className="recent-runs" aria-label="Recent runs">
                {projectRuns.slice(0, 7).map((run) => (
                  <a
                    key={run.id}
                    href={"/runs/" + run.id}
                    className={run.id === runId ? "current-run" : ""}
                    aria-current={run.id === runId ? "page" : undefined}
                    aria-label={run.request + ", " + label(run.state)}
                    onClick={() => closeNavigation()}
                  >
                    <i
                      aria-hidden="true"
                      className={
                        "run-dot dot-" +
                        run.state.toLowerCase() +
                        " tone-" +
                        statusTone(run.state)
                      }
                    />
                    <span>{run.request}</span>
                  </a>
                ))}
              </nav>
            ) : (
              <p className="sidebar-empty">No runs for this project.</p>
            )}
          </div>

          <div className="sidebar-bottom">
            <span
              className={`connection-dot ${
                ["Live", "Ready"].includes(coreStatus) ? "" : "amber"
              }`}
              aria-hidden="true"
            />
            Orqalis Core
            <small>{coreStatus} · durable state</small>
          </div>
        </div>
      </aside>
      <button
        className={"sidebar-backdrop" + (open ? " is-open" : "")}
        type="button"
        aria-label="Close navigation"
        tabIndex={open ? 0 : -1}
        onClick={() => closeNavigation(true)}
      />
    </>
  );
}
