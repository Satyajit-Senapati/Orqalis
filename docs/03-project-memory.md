# Project memory, graph, history, and context

> **Canonical local-first baseline - 2026-09-16.** Earlier database/pgvector
> recommendations are superseded.
>
> **Version scope:** this guide describes the development checkout. Reviewed supersession,
> progressive discovery, JS/TS/TSX extraction and bounded symbolic reads are post-2.0.0
> enhancements, not features of the released 2.0.0 package. See the
> [release boundary](RELEASE_NOTES.md#orqalis-210-local-candidate-unpublished) and
> [validation status](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/ENHANCEMENT_STATUS.md).

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
JSON frontmatter (a YAML-compatible subset; arbitrary YAML is not accepted by the parser)
and include, where applicable:

```json
{
  "id": "MEM-20260916-0001",
  "category": "architecture",
  "title": "Sync coordination policy",
  "source": {
    "type": "repository",
    "paths": ["src/sync/coordinator.py"],
    "content_hashes": {
      "src/sync/coordinator.py": "<actual 64-character SHA-256>"
    }
  },
  "verified_commit": "<git-sha>",
  "introduced_by_task": "ORQ-20260916-0004",
  "confidence": 0.97,
  "last_verified_at": "2026-09-16T14:20:00+05:30"
}
```

The JSON metadata sits between `---` delimiters; the Markdown body follows the closing
delimiter. Replace illustrative hash placeholders with the actual source and Git hashes.

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

Python uses AST extraction. JavaScript, TypeScript and TSX use Tree-sitter syntax
extraction, including source spans and conservative relation candidates. This does not
provide LSP/type-checker binding completeness. Other supported source/config/document
formats receive deterministic file-level nodes. Extraction limits and parser diagnostics
are exposed on file nodes. Graphify is a research reference, not a runtime requirement. Its three documented
outputs are graph exports, not a three-file canonical memory store; the
[storage comparison](https://github.com/Satyajit-Senapati/Orqalis/blob/main/docs/quality/research/KNOWLEDGE_RESEARCH.md#project-memory-storage-and-read-optimization) explains the
request-local I/O optimization and what still reads full records.

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

Core retrieval combines identifier-aware lexical terms, symbol names, paths, graph centrality and
distance, incoming/outgoing relations, Git recency, memory relevance, and related task
summaries. Current retrieval is lexical/graph based; it requires neither embeddings nor a
vector database.

Historical task retrieval validates canonical task metadata and repairs the compact
`.orqalis/tasks/index.json` when it changes. It reads final summaries for matching capsules
and never injects an entire old event stream by default. Canonical metadata is checked on
each history-index read; small context output does not imply constant-time history scanning.

## Context Pack

`ProjectContextBuilder` produces a bounded `ProjectContextPack` containing project/branch,
HEAD and dirty paths, relevant files, ranked graph nodes/neighbors, curated memory with
freshness, decisions, and related historical tasks. Relevant records too large to include
in full retain bounded `memory_discovery` previews with stable IDs and explicit body-fetch
guidance. Provider projections and Task Capsule memory-use evidence retain these previews
and mark their bodies as not loaded. Graph entries expose ranking reasons; centrality-only
results with no query/dependency/dirty match are labeled `orientation_only`.
The configured character budget is a
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


## Reviewed supersession and history

A replacement proposal identifies the active record it `supersedes` and captures its
canonical digest. Approval checks that the predecessor is still active and unchanged.
The successor remains immutable, and an atomic `.orqalis/memory/lifecycle.json` transition
activates it while hiding the predecessor from default search, context, and index rebuilds.
This file is **canonical lifecycle state**, not a disposable index or graph artifact.
The predecessor body, review reason, evidence, time, and successor ID remain available.

The successor's immutable supersession marker keeps it out of normal retrieval if a
process stops after writing the body but before publishing the transition. Retrying the
approval completes recovery without duplicating a transition. Pending or rejected proposals
do not suppress the prior active memory. Conflicting reviews and supersession cycles are
rejected. Historical records are available through explicit reads; `list(include_inactive=True)`
is the service-level audit operation. Source freshness and lifecycle state are independent.

Operators inspect `orqalis memory proposals` and `memory proposal ID`, then use
`memory approve ID --reason TEXT` or `memory reject ID --reason TEXT`. These commands accept
`--repo PATH`. Assistant MCP tools can propose updates under the configured project policy;
operator approval is deliberately not exposed as an unrestricted assistant tool.

## Progressive discovery and integrity

Records may declare a brief `summary` and up to 32 explicit `references` to other stable
`MEM-...` IDs in the same project. Titles can evolve through supersession without making
IDs into filesystem paths. Missing references are rejected on write. References do not
silently follow successors: reading a historical target reports its lifecycle and successor.

`memory discover QUERY --max-chars N` returns bounded previews, matching fields, content
lengths, and reference IDs. `memory get ID --offset N --max-chars N` returns a body page with
source provenance, freshness, lifecycle, and `next_offset`. The serialized response itself
fits the character cap; metadata/body traversal never automatically loads a reference tree.
The current discovery implementation scans local records; smaller assistant context is not
a claim of fewer local disk reads or a new full-text index.

`memory check` reports malformed records, lifecycle inconsistencies, missing references,
and reference cycles, with bounded issue output. Manual edits remain reviewable files and
are checked rather than automatically rewritten. The corresponding SDK and read-only MCP
operations are `discover_project_memory`, `get_project_memory`, and `check_project_memory`.

Graph binding evidence distinguishes extracted source expressions from inferred lexical,
import, and class-member candidates. An unresolved call is a source-scoped reference; it
is not labeled as a known external implementation. `resolution_basis` and `source_expressions`
explain candidate edges. Dynamic Python dispatch is not asserted as proven by AST syntax.

## Bounded symbolic reads

The SDK and read-only MCP offer `find_project_symbols`, `get_module_symbols`,
`get_symbol_body`, and `get_symbol_references` (SDK outline/body/reference methods are
`project_symbol_outline`, `project_symbol_body`, and `project_symbol_references`).
Discovery returns exact IDs and source hashes; duplicate names remain separate symbols.
A body request must supply its discovered source hash. It returns the complete UTF-8
byte span only while the live source still matches; stale, missing, invalid-span or
oversized bodies produce an explicit error instead of a guessed or partial body.

Every response fits its serialized character cap. `source_coverage` exposes truncated
extraction and bounded per-file diagnostic codes; `diagnostics_truncated` reports omitted
diagnostics. Name discovery and references account for incomplete files across their
search scope. Outlines and body reads report the selected file's coverage. Reference
results are labeled `static_graph_candidates`, preserve edge evidence and inference
provenance, and can exclude inferred edges. They do not claim exhaustive semantic
references, and these operations do not modify source code.
