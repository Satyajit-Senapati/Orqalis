# Project Memory Design

> **Canonical baseline:** Orqalis Consolidated End-to-End Design v1.2 (2026-09-10). This file supersedes earlier session versions.

## 1. Objective

Project Memory allows Orqalis and connected coding assistants to retain reliable repository-specific context across tasks without full repository re-analysis. Memory supplements the repository; it never replaces source-of-truth verification.

## 2. Memory scopes

### Global memory
Reusable engineering knowledge, skill definitions, organization policies, generic patterns, and tool instructions.

### Project memory
Repository-specific architecture, modules, file roles, business/domain rules, conventions, decisions, CI/build/test rules, known issues, previous tasks, and high-value implementation facts.

### Run memory
Goal, acceptance criteria, plan, current task state, findings, artifacts, test results, reviewer comments, repair attempts, decisions, and temporary coordination for a single run.

After successful completion, selected run knowledge is promoted to project memory by the Memory Curator.

## 3. Memory categories

- Project identity and purpose.
- Technology stack and versions where stable.
- Architecture and module boundaries.
- Repository map and important file roles.
- Data flows and API contracts.
- Domain entities and business rules.
- Coding/testing conventions.
- CI/CD and Git policies.
- Architecture Decision Records.
- Previous accepted changes.
- Known issues, technical debt, flaky tests, and limitations.
- Relationships/dependencies among files, modules, services, and concepts.

## 4. Provenance model

Every durable fact should include:

```json
{
  "fact": "Room is the primary local persistence layer.",
  "memory_type": "architecture",
  "confidence": 0.98,
  "source_paths": ["data/database/AppDatabase.kt", "docs/architecture.md"],
  "source_commit": "91abc22",
  "introduced_by_run": "ORQ-2026-0202",
  "last_verified_at": "2026-09-10T10:00:00Z",
  "status": "active"
}
```

Memory must support superseding rather than destructive rewriting so history is auditable.

## 5. Git-aware freshness

Each project-memory snapshot records `indexed_commit_sha`. At run start:

1. Read current HEAD/base commit.
2. Compare to indexed commit.
3. If equal, memory is considered structurally current.
4. If different, calculate changed paths and commit range.
5. Determine impacted memory entries and graph neighborhoods.
6. Invalidate or mark stale only affected knowledge.
7. Re-index changed areas.
8. Update snapshot metadata.

This turns repository refresh into an incremental process.

## 6. Dependency-aware invalidation

Memory should model relationships such as:

```text
Theme.kt -> defines -> AppTheme
AppTheme -> used_by -> HomeScreen
AppTheme -> used_by -> EditorScreen
NotesRepository -> backed_by -> Room
NotesRepository -> syncs_through -> SyncCoordinator
```

If a foundational file changes, Orqalis invalidates related facts and summaries rather than the whole project.

## 7. Context Pack

Agents should normally receive a Context Pack, not raw memory search results.

```yaml
context_pack:
  project: Novra Android
  task: Add tablet split-pane editor
  architecture:
    - MVVM
    - responsive layout uses WindowSizeClass
  relevant_files:
    - EditorScreen.kt
    - EditorViewModel.kt
    - ResponsiveScaffold.kt
  conventions:
    - UI state is immutable
  decisions:
    - ADR-008
  related_runs:
    - ORQ-0113
  known_issues:
    - ISSUE-42
  confidence: 0.94
  freshness:
    indexed_commit: abc123
    current_commit: abc123
```

## 8. Retrieval pipeline

1. Parse current task into concepts/capabilities.
2. Retrieve structured facts by project/type.
3. Semantic search over memory text/embeddings.
4. Traverse relevant knowledge-graph relations.
5. Include related prior runs and ADRs.
6. Rank file candidates.
7. Apply token/size budget.
8. Return provenance and confidence.
9. If confidence is below threshold or memory is stale, request targeted repository inspection.

## 9. Bootstrap

`orqalis init` performs the only intentionally broad analysis:

- Detect languages/frameworks/build files.
- Read repository instructions and documentation.
- Identify entry points and module boundaries.
- Detect tests, lint, build, format commands.
- Map high-value files and dependencies.
- Identify Git conventions/protected-branch assumptions where available.
- Generate architecture summary and initial facts.
- Build embeddings and initial graph.
- Store current commit as memory baseline.

## 10. Memory storage

V1 recommendation: PostgreSQL + pgvector. Core relational entities should remain queryable without vector search. Embeddings augment, not replace, structured retrieval.

Core tables: projects, project_memory, memory_sources, memory_versions, repository_files, architecture_entities, architecture_relations, decisions, runs, run_findings, known_issues, embeddings.

## 11. Memory safety rules

- Never store secrets, tokens, passwords, or raw credential files.
- Redact likely secrets before persistence.
- Do not promote transient chain-of-thought or model scratch reasoning.
- Do not trust a single agent assertion as high-confidence architecture truth.
- Prefer source-backed facts.
- Mark inferred facts explicitly.
- Tie accepted changes to commit SHAs.

## 12. Project Brain observability

Project Memory is exposed in the Local Control Center as the **Project Brain**. The UI may show memory categories, indexed commit, freshness, relevant architecture entities/relations, ADRs, known issues, related runs, Context Pack composition, and source provenance.

Memory retrieval and curation emit privacy-safe structured events including query/task reference, selected memory IDs/types, source/commit freshness, count/size, invalidations, and promotions. Do not log full secrets, raw hidden prompts, or private chain-of-thought.

## 13. Memory performance metrics

Track memory hit rate, context-pack size, percentage of repository re-analyzed, changed-file refresh scope, stale-memory invalidations, retrieval latency, and post-run promotions. These metrics help verify the core product claim that Orqalis reduces repeated repository analysis over time.
