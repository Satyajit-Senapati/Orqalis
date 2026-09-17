# Repository cleanup audit

Audit date: 2026-09-17
Architecture authority: repo-local `.orqalis/` filesystem store
Candidate: 2.0.0 (unpublished)
Disposition: repository-controlled release gates complete

This is the path-level classification and action record for the local-first persistence
release cleanup. It describes the working-tree migration from the published 1.0.x SQL
implementation to the current filesystem implementation. Historical release evidence may
still name PostgreSQL when it is explicitly labelled historical; it is not a current
runtime requirement.

## Runtime entry points traced

| Surface | Entry point | Authoritative composition |
| --- | --- | --- |
| Python command | `pyproject.toml` -> `orqalis.cli.app:app` | Root-bound SDK and filesystem unit of work |
| npm command | `packages/npm/bin/orqalis.js` -> launcher/runtime bundle | Hash-verified Python wheel containing the same CLI |
| `orqalis init` | `src/orqalis/cli/app.py` -> project bootstrap | Creates and validates the selected repository's `.orqalis/` store |
| `orqalis run` | `src/orqalis/cli/app.py` -> SDK preparation services | Creates a Task Capsule before execution and persists each reached stage |
| `orqalis ui` / `serve` | CLI -> `src/orqalis/api/hosting.py` | FastAPI/API/WebSocket services over the root-bound filesystem store |
| MCP | `orqalis mcp --root ...` -> `src/orqalis/mcp/server.py` | One explicit project root and high-level application services per process |

## Classification and actions

| Path or path group | Classification | References/decision | Action |
| --- | --- | --- | --- |
| `src/orqalis/persistence/contracts.py`, `src/orqalis/persistence/*_ports.py` | KEEP | Storage-neutral domain/application boundaries | Retained; orchestration depends on ports rather than a storage technology. |
| `src/orqalis/persistence/filesystem/` | KEEP | Sole standard persistence implementation | Added atomic I/O, scoped layout, locks, schema migration, stores and filesystem unit of work. |
| `src/orqalis/{tasks,graph,indexing,context}/`, `memory/curated.py` | KEEP | Implements Task Capsules, graph/index retrieval, Context Packs and curated memory | Added as the canonical local-first services. |
| `src/orqalis/{agents,core,domain,evaluation,execution,providers,skills,delivery,git,security,workspace}/` | KEEP | Current orchestration, provider, review, repair, Guardian and Git behavior | Retained and rebound to filesystem-backed contracts. |
| `src/orqalis/{cli,api,mcp}/`, `src/orqalis/sdk.py`, `web/` | REWRITE | Public CLI/API/MCP/UI surfaces are active entry points | Reworked composition and projections to use one resolved project root and filesystem services. |
| `tests/integration/test_*.py` (27 changed modules) | MIGRATE | Product behavior was valuable; SQL fixtures were not authoritative behavior | Ported to filesystem fixtures and root-local assertions instead of deleting coverage. |
| `tests/support/filesystem.py` and local-first unit/e2e suites | KEEP | Shared filesystem test composition and release gates | Added; covers isolation, restart, migration, graph, memory, events, API/MCP/UI and packaging. |
| Canonical root/docs files and `docs/01`, `03`, `05`, `07`, `09`, `10` | REWRITE | Previously described SQL as the active design | Rewritten for local-first authority; dated 1.0.x evidence is explicitly historical. |
| `CONSOLIDATION_NOTES.md` | REMOVE | Superseded prompt-era consolidation notes; useful rules are in canonical docs/handoff/sign-off | Deleted. |
| `alembic.ini`, `compose.yaml` | REMOVE | Only configured the retired required database stack | Deleted; Docker remains optional only for command isolation. |
| `src/orqalis/persistence/{approval_models,approvals,database,delivery,delivery_models,events,execution,execution_models,memory,memory_models,migrate,models,projects,provider_models,providers,runs,runtime,runtime_models,schema,unit_of_work,workflow_models}.py` | REMOVE | SQLAlchemy repositories/models duplicated the filesystem authority | Deleted after orchestration and behavior tests passed through the filesystem unit of work. |
| `src/orqalis/persistence/migrations/` | REMOVE | Alembic schema history was not part of standard local-first runtime | Deleted; schema-versioned file migrations now back up, validate and atomically replace project files. |
| `tests/integration/{conftest,test_postgres}.py`, `tests/unit/test_approval_repository.py` | REMOVE | Database-only fixture/schema coverage | Deleted after relevant behavior coverage moved to filesystem suites. |
| `.venv/`, `.tools/`, `dist/`, `node_modules/`, `web/dist/`, npm staging trees and language/tool caches | GENERATED | Recreated by install, test, build or package commands | Ignored; cache directories outside tool/runtime environments are removed after final validation. |
| `.orqalis/cache/`, `.orqalis/index/`, `.orqalis/runtime/` | GENERATED | Per-project derived or machine-local data | Remain physically project-local and are governed by generated `.orqalis/.gitignore`; canonical memory/tasks are not lost when these are deleted. |
| Compatibility source-summary records and graph projections | GENERATED | Older orchestration contracts still consume a rebuildable projection | Moved from canonical `memory/` paths to `cache/search/` and `cache/graph/`; curated memory, typed graph and Task Capsules remain the only authorities. |
| `src/orqalis/skills/bundled/database-edit/` and database planning tags | KEEP | Generic capability for user repositories that contain databases, not Orqalis persistence | Retained intentionally; it does not import or configure a database runtime for Orqalis. |
| PostgreSQL terms in dated release appendices and `docs/verification/` | KEEP | Immutable evidence for the artifacts that were actually tested in 1.0.0/1.0.1 | Retained only with current local-first supersession notices. |
| Credential-shaped strings in security/secret-scanner tests | KEEP | Synthetic redaction fixtures | Retained as non-secret test data; package and tracked-file scans found no actual credential. |

## Removed inventory

Thirty-eight tracked files were removed:

- three obsolete root files: `CONSOLIDATION_NOTES.md`, `alembic.ini`, and `compose.yaml`;
- thirty-two SQL persistence files, including eleven Alembic migration files; and
- three database-only test/fixture files.

The standard dependency set removed four direct database packages: SQLAlchemy, Alembic,
psycopg (binary extra), and pgvector. The lock regeneration also removed their unused
transitives (`greenlet`, `mako`, `markupsafe`, and `tzdata`, plus the split psycopg binary
distribution). Database environment settings, health checks, migration commands, Compose
startup, and database-only CI were removed. No alternate required database was introduced.

## Generated and package policy

The repository `.gitignore` excludes local environments, caches, coverage/build output,
Node dependencies, npm staging trees and tarballs. Each initialized project receives a
separate `.orqalis/.gitignore` rendered from its tracking policy. Durable project documents,
curated memory and selected Task Capsule summaries remain eligible for Git tracking.

The npm package uses an explicit `files` allowlist. Packaging rejects database dependencies,
symlinks, stale wheel/frontend/source inventories, unpinned dependencies, local URLs and
private `.orqalis/` state. Maintainer-only readiness and cleanup audits are not copied into
the npm runtime artifact.

## Verification evidence

The final candidate passed without PostgreSQL, another database service, `DATABASE_URL`,
or a Postgres container:

- Python collected 425 tests: 424 passed and the separately configured Docker command
  sandbox test was the only skip because no image was configured;
- Ruff lint passed and all 262 formatted files were clean; strict mypy passed across 250
  source/test files and the three release scripts;
- the Control Center passed lint, 33 tests across seven files, and its 209-module production
  build; the npm wrapper passed syntax, lint, formatting, and all 29 tests;
- npm dry-run and actual pack contained 69 allowlisted entries, with no project `.orqalis/`,
  test tree, database bootstrap/configuration, SQL persistence module, maintainer audit, or
  detected credential pattern;
- the exact tarball passed an isolated cold and cached launcher setup plus CLI/help/JSON/
  invalid-exit/cwd isolation; and
- the installed application verifier passed no-database doctor, idempotent init, status,
  memory/context, agent/skill catalog, explicit-goal run, 26-tool MCP, API schema,
  WebSocket ordering/reconnect, packaged UI/static assets, hostile-cwd startup and owned
  process shutdown outside the checkout.

Release-candidate artifacts are regenerated only after every documentation and metadata
edit has settled:

| Artifact | SHA-256 |
| --- | --- |
| `.tools/release/orqalis-2.0.0-py3-none-any.whl` | `7E6129FC2F167C644A5E882BFACC208DFD3521A197505EEC0EB6B4E2D7CD2FB0` |
| `dist/orqalis-2.0.0.tgz` | `2161403A190034585F07DE473530EC1B93FF4194AA745E062E6BB43CD4DE8A88` |

The stale local 1.0.1 wheel/tarball and staged vendor wheel were removed or replaced; only
2.0.0 release artifacts remain. Nothing was published. Public 1.0.1 remains immutable and
database-backed.

## Review resolution

Repository searches found no unresolved product-name placeholder, active database import,
database startup requirement, competing persistence implementation, deleted source import,
or production demo-data authority. Remaining database language is either labelled historical,
a negative regression assertion, a synthetic secret, or a capability for editing a user's
database-backed application. No content item remains classified `REVIEW`, and no
repository-controlled release blocker remains open.

## Final 2.0.0 release preparation - 2026-09-17

The verified application source remained frozen. Release preparation added only a
manual, tag-bound Trusted Publishing gate, its focused tests and documentation, plus a
release-verifier correction for the observed Windows venv redirector process shape. The
publication job requires an explicit `workflow_dispatch` with `publish=true` on a version
tag, depends on the platform-smoke and installed-integration jobs, uses the protected
`npm-release` environment and job-scoped OIDC, and contains no npm token. A branch or tag
push alone cannot publish.

The complete 425-test application baseline remains 424 passed with one optional Docker
sandbox skip. The final collection is 430 after adding two publication-workflow tests and
three process-ownership regression cases. The release-critical rerun passed 354 unit/e2e
tests, 35 filesystem/orchestrator/API/MCP integrations, all 9 npm-release tests and all 20
installed-smoke tests. Ruff and formatting passed; configured strict mypy passed across
250 source/test files and strict release-script mypy passed across all three scripts. The
Control Center again passed 33 tests and its 209-module production build, while the npm
launcher again passed all 29 tests.

The final installed tarball passed 7 launcher checks and 17 application checks from a
clean external prefix/runtime: database-free doctor, idempotent project initialization,
status, curated memory/context, agent/skill catalog, deterministic Task Capsule creation,
26-tool MCP, packaged UI, API schema, WebSocket replay/reconnect, direct routes, hostile-cwd
isolation and owned-process shutdown. The first Windows UI verification exposed that the
venv redirector and base interpreter can report the same venv command line. Live inspection
proved the exact `Node -> managed redirector -> listener` ancestry; the verifier now accepts
that chain only when the parent is the expected runtime and the grandparent is the launched
CLI. Positive and negative ancestry tests preserve the cleanup safety boundary.

The first hosted quality run then exposed one platform-specific static-analysis issue:
Linux-targeted mypy inspected the Windows `msvcrt` lock branch. The lock implementation now
loads both platform modules behind typed protocols, without changing runtime semantics.
Native and Linux-targeted strict mypy passed across all 250 source/test files, Ruff and
formatting passed, and all 25 filesystem-foundation tests passed. The rebuilt artifacts then
passed the complete 7-check launcher and 17-check installed verifier again.

The final Python wheel and npm archive therefore have new digests attributable to that
reviewed portability correction. The npm archive retains the same 69-entry allowlist. Its
final metadata is:

- SHA-256 `2161403A190034585F07DE473530EC1B93FF4194AA745E062E6BB43CD4DE8A88`;
- npm shasum `b75c400eb6963cb4a31fc30b1becde541adeb44a`; and
- unpacked/package sizes 1,907,436 / 1,544,012 bytes.

Pack and publish dry-runs passed. Archive, dependency and secret scans found no project
`.orqalis/`, credentials, local paths, retired database code or database requirement.
Public npm still reports `1.0.1` as `latest`, maintainer `satyajit-pro`, and no
`orqalis@2.0.0`. The local npm client is unauthenticated, and the private npm
Trusted-Publisher relationship plus protected GitHub environment require release-owner
verification. No npm publication or GitHub Release was performed.

After all tests and installed-package work completed, final hygiene removed 278 ignored
cache roots containing 2,007 regenerated files plus `web/tsconfig.tsbuildinfo`. Every
resolved target was verified inside the workspace and outside `.venv`, `.tools` and
`node_modules`; release artifacts and durable source/evidence were retained.

The annotated `v2.0.0` tag is the authoritative locator for the release commit. The exact
commit ID and push state are recorded by Git and the final release handoff after the commit
exists; a commit cannot embed its own future object ID.
