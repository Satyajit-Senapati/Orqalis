# Project memory, graph, history, and context

> **Canonical local-first baseline - 2026-09-16.** Earlier database/pgvector
> recommendations are superseded.

## Three distinct knowledge systems

Orqalis never collapses all knowledge into one file or one index.

1. **Repository Graph** contains deterministic or explicitly inferred facts about files,
   modules, symbols, tests, configuration, documentation, and their relationships.
2. **Curated Project Memory** contains durable explanations: product intent, architecture,
   technology, conventions, domain language, workflows, testing practice, pitfalls,
   modules, and decisions.
3. **Task History** contains one self-contained Task Capsule per request, including context,
   goal, acceptance, plan, execution, review, evidence, repair, changes, and delivery.

Graph facts are not promoted as architectural rationale. Short-lived execution state stays
in Task Capsules rather than curated memory.

## Curated memory format

Baseline category documents are Markdown. Individual durable records use Markdown with
structured frontmatter and include, where applicable:

```yaml
id: MEM-20260916-0001
category: architecture
source:
  type: repository
  paths: [src/sync/coordinator.py]
  content_hashes:
    src/sync/coordinator.py: <sha256>
verified_commit: <git-sha>
introduced_by_task: ORQ-20260916-0004
confidence: 0.97
last_verified_at: 2026-09-16T14:20:00+05:30
```

Paths are repository-relative. A source hash mismatch, missing source, or unverifiable
commit marks a record `STALE`; stale records may still be retrieved at reduced relevance
but must not be presented as unquestioned fact.

## Curation and secret safety

The Memory Curator proposes only durable knowledge learned from accepted changes,
review evidence, decisions, conventions, or pitfalls. Policies are `auto`, `review`, or
`manual`. Reviewable proposals live under `memory/staging/MEM-PROP-.../`, containing the
proposal, proposed Markdown, diff, and evidence. Approval promotes the record; rejection
moves the proposal to history without changing active memory.

Candidate titles, content, rationale, evidence, and serialized metadata are scanned for
credential fields, tokens, passwords, private keys, authenticated URLs, and private model
diagnostics. Unsafe durable memory is rejected. Store only requirements such as
"authentication uses `GITHUB_TOKEN`," never the value.

## Repository graph

Graph nodes include file, module, package, class, function, method, interface, route,
configuration, test, documentation, table, and reference kinds. Relations include
`IMPORTS`, `CALLS`, `IMPLEMENTS`, `EXTENDS`, `USES`, `DEFINES`, `REFERENCES`, `TESTS`,
`CONFIGURES`, `DEPENDS_ON`, `ROUTES_TO`, `READS_FROM`, and `WRITES_TO`.

Every edge records provenance:

- `EXTRACTED`: deterministic repository analysis produced the relationship;
- `INFERRED`: a secondary reasoning step produced it, with explicit confidence/evidence.

Python AST extraction is implemented; other supported source/config/document formats
receive deterministic file-level nodes. Graphify may inspire or later adapt to the stable
Orqalis contract, but it is not a runtime requirement.

## Incremental refresh and caches

The graph manifest stores indexed branch/commit, file content hashes, parser/schema
versions, and last indexed time. Refresh considers Git tracked files, relevant untracked
and dirty files, and current content hashes. Only changed/new content is parsed; removed or
renamed paths and their affected edges are invalidated. Cached parser output is keyed by
SHA-256 and may be reused across paths with identical content.

`memory/graph/`, `index/`, and `cache/` are derived. Removing them never removes curated
memory or Task Capsules. Use `orqalis rebuild-index --repo PATH` for a full regeneration;
idempotent `orqalis init --repo PATH` also restores missing bootstrap-derived data.

The compatibility source-summary projection used by older orchestration contracts also
lives under `cache/search/`. It is rebuildable input acceleration, never durable Project
Memory, and may be deleted with the rest of the cache.

## Local retrieval

Core retrieval combines lexical terms, symbol names, paths, tags, graph centrality and
distance, incoming/outgoing relations, Git recency, memory relevance, and related task
summaries. Embeddings are optional and cannot be a prerequisite or sole source of truth.

Historical task retrieval uses compact `.orqalis/tasks/index.json` entries and reads only
selected final summaries and affected metadata from matching capsules. It never injects an
entire old event stream by default.

## Context Pack

`ProjectContextBuilder` produces a bounded `ProjectContextPack` containing project/branch,
HEAD and dirty paths, relevant files, ranked graph nodes/neighbors, curated memory with
freshness, decisions, and related historical tasks. The configured character budget is a
hard bound. At run startup the pack is persisted to the current Task Capsule as:

```text
context/context-pack.md
context/memory-used.yaml
context/files-used.json
context/graph-query.json
```

These are human-readable projections of the authoritative capsule snapshot.

Implemented user commands include `orqalis memory status`, `memory refresh`, `memory
search`, `memory graph [--open]`, `orqalis context`, and `orqalis rebuild-index`.
