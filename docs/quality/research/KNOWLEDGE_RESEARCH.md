# Repository intelligence and durable project memory research

This combined guide preserves dated repository intelligence, memory optimization, parser correction, and the iteration-1 independent audit. For current acceptance and
release status, use the [enhancement status](../ENHANCEMENT_STATUS.md).

Inspection date: 2026-09-26. Baseline: `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / immutable `v2.0.0`. This audit distinguishes the released baseline from the current development tree, which already contains `graph/queries.py` and identifier-aware lexical terms. These additions are not evidence that every gap below is closed.

Scope: master-plan sections 11-17, 34-41 and 60-61. Repository authority: `SIGNOFF.md`, `docs/SOURCE_OF_TRUTH.md`, actual graph/context/memory services and tests. No root `AGENTS.md` was present. Upstream source was inspected in isolated shallow checkouts under the OS temporary directory; public GitHub API metadata was used until rate-limited, then ordinary Git. No `gh`, hosted service, external database or upstream runtime was installed into Orqalis.

This is a source-backed capability comparison and benchmark specification, not an executed end-to-end performance contest. The concrete provenance reproducer below was executed. Upstream marketing token reductions and upstream retrieval results are not Orqalis measurements. Licensing statements record inspected notices and are not legal advice.

## Upstream refresh - 2026-10-03

[Current refresh disposition](../evidence/release-upstream-refresh-20261003-independent-disposition-v1.json)
rechecks all40 linked references across the three guides. The bounded metadata/README
review confirms the existing graph, identifier retrieval and reviewed-memory patterns;
it identifies no new confirmed accepted P0/P1 gap. Graph exports do not replace canonical
memory/task authority, and upstream token/retrieval claims remain unmeasured in Orqalis.
All23 accepted implementations remain pending evaluation and13 DEFER decisions remain.
Changed upstream code and nested license payloads were not comprehensively audited;
the source inspections below retain their original dates and pins.

## Pinned references and maintenance observations

All links in this table identify the inspected revision. A recent commit is evidence of activity, not a quality score. Source/tests were read; the entire upstream test suites were not executed.

| Project | Inspected revision | Commit date | License and activity observation |
|---|---|---|---|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify/tree/4139885a1212956cf69a76946fbde0d181ab85e9) | `4139885a1212956cf69a76946fbde0d181ab85e9` | 2026-09-26 | Apache-2.0; `NOTICE` preserves pre-relicensing MIT portions and `LICENSE-MIT`. Current extraction, cache, query and resolution tests. The search result `mbilalnust/Graphify` is an older fork, not the current reference. |
| [Aider-AI/aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | 2026-05-22 | Apache-2.0. Substantial repo-map tests; default-branch commit several months old at inspection, not proof of abandonment. |
| [oraios/serena](https://github.com/oraios/serena/tree/7a2968335f2198b966864de1ce3655c8e485a653) | `7a2968335f2198b966864de1ce3655c8e485a653` | 2026-09-24 | **Application GPL-3.0-or-later; SolidLSP MIT.** Active v2 transition. `src/serena`, its tools/memory manager, application tests and docs are GPL. `src/solidlsp`, `test/solidlsp`, `test/resources` are MIT. Combined distribution is GPL. The license names v1.7.0 / `74c38a65f03fc0764d7ee4b3016ef6a07572ed64` as last MIT release/commit. Do not infer current terms from stale search snippets. |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter/tree/dcdc8cc55e5dfedfc858080835f153999a29ec40) | `dcdc8cc55e5dfedfc858080835f153999a29ec40` | 2026-09-24 | MIT core; grammar and binding licenses require separate checks. Active source and API tests. |
| [microsoft/multilspy](https://github.com/microsoft/multilspy/tree/b9a0ef1bc221e5575787be80493059b01f03c37a) | `b9a0ef1bc221e5575787be80493059b01f03c37a` | 2026-08-20 | MIT client library; language servers have independent terms/runtime dependencies. |
| [sourcegraph/scip](https://github.com/sourcegraph/scip/tree/08b592d981d675d46de9301b50c66ed9064dc759) | `08b592d981d675d46de9301b50c66ed9064dc759` | 2026-09-25 | Apache-2.0 protocol/tooling; language-specific indexers must be assessed separately. |
| [nova-land/coding-agent-memory-mcp](https://github.com/nova-land/coding-agent-memory-mcp/tree/efa89c0e9f2765a71b0e9e31a7127588644fd36a) | `efa89c0e9f2765a71b0e9e31a7127588644fd36a` | 2026-05-30 | MIT; compact TypeScript implementation with `src/test/store.test.ts`; several months since default-branch commit. |
| [xChuCx/agent-memory](https://github.com/xChuCx/agent-memory/tree/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2) | `4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2` | 2026-09-25 | Apache-2.0; actual intended Agent-Memory candidate is named explicitly because the generic name is ambiguous. Active Go implementation, drift/archive/security tests and labeled retrieval eval. |
| [official MCP memory reference](https://github.com/modelcontextprotocol/servers/tree/f46d9578190b476b3501923ea8977d899e8db2cb/src/memory) | `f46d9578190b476b3501923ea8977d899e8db2cb` | 2026-09-22 | Root notice describes transition: new code Apache-2.0, unconsented historical contributions MIT, non-spec documentation CC-BY-4.0. Do not label the entire current tree MIT. Atomic-save, graph and resource tests exist. |
| [letta-ai/letta](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) | `5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a` | 2026-09-10 | Apache-2.0 pointer repository; README explicitly directs current development to letta-code; retired v1 server is on `archive`. |
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code/tree/5e420db9f2871bc3106ba14372d4f8d94c5e63ae) | `5e420db9f2871bc3106ba14372d4f8d94c5e63ae` | 2026-09-26 UTC | Apache-2.0; active current harness with filesystem memory, constraints, conflict, worktree and Windows tests. Local backend exists; cloud is README default. |
| [getzep/graphiti](https://github.com/getzep/graphiti/tree/ba4a9cb32495b6864160616f8dfa2b898f4a500c) | `ba4a9cb32495b6864160616f8dfa2b898f4a500c` | 2026-09-25 | Apache-2.0 current license. Active temporal graph and retrieval implementation. README requires a graph backend and inference/embedding provider; Kuzu adapter is deprecated. |
| [mem0ai/mem0](https://github.com/mem0ai/mem0/tree/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd) | `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd` | 2026-09-25 | Apache-2.0. Active OSS memory SDK with configurable vector backend and SQLite history; hosted product is separate. Current add path uses additive extraction; do not repeat historical blanket claims that every add automatically updates/deletes older facts. |

## Actual Orqalis state

Local evidence: `src/orqalis/graph/{models,engine,queries}.py`, `src/orqalis/context/{builder,models}.py`, `src/orqalis/memory/curated.py`, `src/orqalis/persistence/filesystem/memory_store.py`, `src/orqalis/domain/memory.py`, `src/orqalis/retrieval.py`, `src/orqalis/mcp/server.py`, and `tests/unit/test_{project_graph,project_context_builder,curated_memory,graph_queries,identifier_retrieval}.py`.

- **KEEP:** project-bound `.orqalis` authority, canonical curated records separate from graph and task history; atomic file writes and locks; proposals with review policy; source hashes and Git provenance; stale-memory detection; secret rejection; source/worktree common-repository validation; rebuildable cache; persisted graph checksum and parser-version validation.
- Graph supports Python AST definitions, imports, calls, inheritance, test associations, docs/config file nodes and evidence locations. Other listed language extensions receive file-level ingestion, **not equivalent full parsers**. `INTERFACE`, `IMPLEMENTS`, route/schema relation enums do not establish an implemented extractor.
- Refresh reuses content-addressed per-file parsing and handles branch, dirty, untracked, renamed and deleted paths. On a changed repository it still reads/hashes the inventory and assembles the graph; `processed_files == 1` must not be described as O(1) total indexing work. Whole-file caching differs from Tree-sitter incremental syntax-tree edits.
- Context ranking already combines name/path overlap, eight-step PageRank-like centrality, undirected distance up to three hops, changed-file bonus, curated memory, stale discount, and completed task title/history. The serialized JSON has a hard character cap. These are meaningful existing strengths.
- `get_related_symbols` is ranked node discovery. It is not full symbol body/reference/implementation or hash-checked replacement tooling. Current context graph entries expose neighbor names but not every witnessing edge's provenance.
- Durable curated records have categories, title/content, source hashes, commit/task association and confidence. They do not yet expose explicit active/superseded/archived lifecycle, tags, durable memory-to-memory references, or per-record tool-read-only policy. The similarly named `MemoryStatus.SUPERSEDED` belongs to the legacy source-search projection and does **not** implement curated memory supersession.
- Search reads whole durable records and counts matching terms. No section-level/lazy memory selection, relevance explanation, inverse-document-frequency weighting or distinct curated full-text index was found. Human-editable JSON frontmatter is YAML-compatible in format, but `_parse_record` explicitly calls `json.loads`: arbitrary YAML frontmatter is not supported.
- Explicit `revalidate` changes source hashes/commit/time, not memory prose. That operation acknowledges a new source snapshot; it does not independently prove a factual claim is still correct.

## Structured capability decisions

Every entry provides the master-plan research contract. Cost is relative engineering scope, not a schedule guarantee: S = isolated contract/service change; M = several interfaces plus fixtures; L = runtime/dependency integration.

### K01: conservative code-edge provenance

**PROJECT:** Graphify. **SUBSYSTEM:** repository graph. **FEATURE:** extracted/inferred/ambiguous evidence and conservative call-target resolution. **HOW IT WORKS:** extraction records source evidence; symbol resolution records import aliases and refuses unsupported receiver resolution instead of treating every matching name as a binding. **WHY EFFECTIVE:** consumers can separate a syntactic occurrence from a semantically justified dependency. **ORQALIS CURRENT:** provenance exists, but `_resolve_symbol` falls back to the globally unique last name and `_add_call` always emits EXTRACTED/1.0. **GAP:** P1, a unrelated method receiver can create a false exact call and false impact. **ADAPTATION:** preserve an EXTRACTED edge to a scoped call-reference occurrence when target binding is unknown; resolve only supported lexical/import evidence, or label a candidate INFERRED with its resolution basis; do not equate confidence with runtime proof. **BENEFIT:** trustworthy impact, navigation and evidence filtering. **COST:** M. **LICENSE:** Graphify Apache-2.0 plus retained MIT portions; original Orqalis implementation preferred. **RISKS:** unresolved edges reduce recall; Python rebinding/dynamic dispatch remain limitations. **RECOMMENDATION:** ADAPT, accepted P1. **EVIDENCE:** [symbol_resolution.py](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/symbol_resolution.py), [resolution tests](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/tests/test_symbol_resolution.py), local executable reproducer below.

### K02: multi-language syntax extraction

**PROJECT:** Tree-sitter, Graphify, Aider. **SUBSYSTEM:** repository parsing. **FEATURE:** grammar-specific definitions/imports/references and syntax-error tolerance. **HOW IT WORKS:** Tree-sitter builds concrete syntax trees; query captures or language extractors produce normalized facts. Prior trees plus edit coordinates can support incremental reparse. **WHY EFFECTIVE:** JS/TS/TSX and other source become queryable symbols; partial code can still expose useful structure. **ORQALIS CURRENT:** Python `ast` only; other code file nodes lack bodies/symbols. **GAP:** P1 for Orqalis's own React/TypeScript frontend; broader language support is a separately scoped opportunity. **ADAPTATION:** Orqalis parser protocol and declared capabilities, deterministic TypeScript/JavaScript fixtures first; pin grammar/binding compatibility and parser cache identity; retain Python ast. **BENEFIT:** frontend and cross-module tasks receive actual symbols. **COST:** M for JS/TS, L for broad parity. **LICENSE:** core MIT; verify individual grammar/binding licenses before dependency change. **RISKS:** native wheels/ABI portability, incomplete syntax mistaken for semantic resolution. **RECOMMENDATION:** ADD JS/TS parser capability; DEFER universal grammar set until task evidence. **EVIDENCE:** [Tree-sitter API](https://github.com/tree-sitter/tree-sitter/blob/dcdc8cc55e5dfedfc858080835f153999a29ec40/lib/include/tree_sitter/api.h), [Graphify extractors](https://github.com/Graphify-Labs/graphify/tree/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/extractors), [Aider captures](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/repomap.py).

### K03: incremental graph freshness

**PROJECT:** Graphify and Tree-sitter. **SUBSYSTEM:** indexing. **FEATURE:** file hashes, parser/prompt cache versioning, dirty changes. **HOW IT WORKS:** content and parser identity invalidate derived extraction; Graphify separates semantic prompt fingerprints and AST caches. **WHY EFFECTIVE:** unchanged work is reused without retaining stale semantic extraction. **ORQALIS CURRENT:** hash cache, parser version, graph digest, branch/head/dirty cursor and rebuild tests already cover core needs. **GAP:** semantic prompt cache is irrelevant until semantic extraction exists; no need to introduce one now. **ADAPTATION:** retain invariant and add parser identity for each new grammar; record actual bytes/files read separately from parser misses. **BENEFIT:** accurate performance claims and safe evolution. **COST:** S. **LICENSE:** Graphify Apache-2.0/MIT portions; Tree-sitter MIT. **RISKS:** misleading incremental metrics; cache identity collisions when parsers expand. **RECOMMENDATION:** KEEP, ADAPT measurement. **EVIDENCE:** [Graphify cache](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/cache.py), local graph branch/cache/tamper tests.

### K04: graph navigation, communities, heterogeneous ingestion

**PROJECT:** Graphify. **SUBSYSTEM:** graph exploration. **FEATURE:** neighborhood/path queries, topology communities, docs/schema semantic links. **HOW IT WORKS:** a local graph supports directed traversal and source-located explanations; clustering groups dense regions; non-code inference is labeled separately. **WHY EFFECTIVE:** agents can navigate an unfamiliar subsystem without the full graph or document corpus. **ORQALIS CURRENT:** new bounded impact/shortest-path queries already preserve evidence, direction and truncation; documentation/configuration nodes are shallow. **GAP:** path/navigation was a real gap addressed in the current wave; communities and doc/schema relations remain unmeasured. **ADAPTATION:** benchmark the new queries; consider deterministic Markdown links/config import relationships before model-inferred ingestion. **BENEFIT:** smaller auditable discovery results. **COST:** S validation; M/L semantic ingestion. **LICENSE:** current Apache-2.0 with MIT notices. **RISKS:** communities are navigational groupings, not architecture truth; model ingestion exposes source to chosen provider and costs tokens. **RECOMMENDATION:** KEEP new navigation subject to tests; DEFER communities and multimodal ingestion; REJECT mandatory model extraction or graph DB. **EVIDENCE:** [build.py](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/build.py), [cluster.py](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/cluster.py), [CLI paths](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/graphify/cli.py).

### K05: personalized compact repository maps

**PROJECT:** Aider. **SUBSYSTEM:** context ranking. **FEATURE:** definition/reference graph, query/chat-file personalization, compact code map under budget. **HOW IT WORKS:** `get_ranked_tags` weights references, boosts mentioned identifiers/files and chat files, uses personalized PageRank, then selects and renders source lines under a measured/estimated token target. **WHY EFFECTIVE:** central symbols connected to the immediate task outrank generic central code. **ORQALIS CURRENT:** global centrality, lexical boosts, distance, dirty signal and character cap already exist; context includes graph JSON and repeated node neighbors. **GAP:** no measured benefit of personalization; generic central nodes can still fill negative-query packs; no language-aware signature skeleton. **ADAPTATION:** evaluate query-seeded personalization and deduplicated file/symbol skeletons against existing ranking; expose score reasons; avoid all-candidate graph arrays. **BENEFIT:** better recall per byte, especially unfamiliar-module queries. **COST:** M. **LICENSE:** Apache-2.0. **RISKS:** centrality over-promotes hubs; tiny exact-match benchmarks hide poor negative precision; token estimates must be labeled. **RECOMMENDATION:** ADAPT after held-out eval; KEEP current hard serialized cap and independent memory/task signals. **EVIDENCE:** [repomap.py](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/repomap.py), [repo-map tests](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/tests/basic/test_repomap.py).

### K06: symbolic read and edit operations

**PROJECT:** Serena / SolidLSP and multilspy. **SUBSYSTEM:** source tools. **FEATURE:** symbol outline, find symbol/body, references, implementations, replace-symbol semantics. **HOW IT WORKS:** language servers supply document/workspace symbols and positions; high-level operations select bounded symbols, optionally body text, and constrain edits to a symbol. **WHY EFFECTIVE:** edits do not rely on fragile guessed line ranges; targeted reads omit unrelated code. **ORQALIS CURRENT:** graph nodes have qualified names/line spans/hash; ranked symbols exist but dedicated body/reference/implementation/replacement APIs do not. **GAP:** P1 read-side abstraction; LSP-backed semantic completeness and writing can follow separately. **ADAPTATION:** `SymbolService` over existing graph, return outline/body with source hash, scope and capability metadata; stale-hash rejection, unique-match requirement and UTF-8/UTF-16 conversion for future adapters. Optional SolidLSP or multilspy adapter behind interface, no mandatory language-server daemon. **BENEFIT:** reliable bounded source access across assistants. **COST:** M read tools, L LSP/edits. **LICENSE:** Serena application GPL-3.0-or-later; SolidLSP and multilspy MIT. **RISKS:** do not copy GPL tool implementation into MIT Orqalis; server startup/download and per-server license costs; decorators/overloads/Unicode boundaries. **RECOMMENDATION:** ADD native read abstraction; DEFER LSP and writes until focused fixtures; REJECT copying incompatible current Serena application code. **EVIDENCE:** [symbol_tools.py](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/src/serena/tools/symbol_tools.py), [component license](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/LICENSE), [multilspy API](https://github.com/microsoft/multilspy/blob/b9a0ef1bc221e5575787be80493059b01f03c37a/src/multilspy/language_server.py).

### K07: portable semantic index ingestion

**PROJECT:** Sourcegraph SCIP. **SUBSYSTEM:** graph interoperability. **FEATURE:** stable symbol identities, occurrence ranges, semantic relationships. **HOW IT WORKS:** a typed index records repo-relative document paths, position encoding, occurrences, external symbols and definition/implementation/reference relationships. **WHY EFFECTIVE:** code intelligence can come from compiler-aware indexers without forcing an IDE server into every query. **ORQALIS CURRENT:** native file/symbol IDs and generic relation enums; no import adapter. **GAP:** complex cross-language binding is beyond current parser; not demonstrated as a normal-install blocker. **ADAPTATION:** optional validate-and-import derived SCIP adapter after language coverage and benchmark demand. **BENEFIT:** stronger semantic navigation for supported ecosystems. **COST:** L. **LICENSE:** Apache-2.0 protocol; indexer terms separate. **RISKS:** stale indexes, position encoding, malicious paths, dependency burden. **RECOMMENDATION:** DEFER; preserve provenance and source hashes if adopted. **EVIDENCE:** [scip.proto](https://github.com/sourcegraph/scip/blob/08b592d981d675d46de9301b50c66ed9064dc759/scip.proto).

### K08: progressive explicit memory references

**PROJECT:** Serena. **SUBSYSTEM:** curated memory discovery. **FEATURE:** topic names, explicit references, rename propagation and broken-link checking. **HOW IT WORKS:** its memory manager recognizes `mem:` links, lists topic-scoped names, traverses names explicitly, updates writable references on rename, and reports missing/ambiguous references with suggestions. **WHY EFFECTIVE:** brief orientation memories can lead to detailed relevant knowledge without loading everything. **ORQALIS CURRENT:** stable MEM IDs and categories, full-record search, no typed references. **GAP:** P1 for progressive discovery and integrity. **ADAPTATION:** preserve stable MEM IDs; add `references: tuple[MEM-id]` and summaries/tags as metadata; optionally human-friendly aliases with a separate unique alias map. Resolve explicit IDs only; bounded depth/visited set/character budget; integrity reports for broken links, cycles and superseded targets. **BENEFIT:** smaller auditable memory packs, rename-stable human links. **COST:** M. **LICENSE:** current Serena memory code GPL; clean Orqalis implementation of the concept. **RISKS:** automatic fuzzy repairs can link the wrong memory; reference cycles and prompt injection; no cross-project/global dereference. **RECOMMENDATION:** ADAPT, accepted P1; REJECT automatic fuzzy rewrite as authority. **EVIDENCE:** [reference analysis](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/src/serena/memories/memory_reference_analysis.py), [manager](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/src/serena/memories/memory_manager.py).

### K09: tags, excerpts and explainable memory search

**PROJECT:** nova-land/coding-agent-memory-mcp. **SUBSYSTEM:** memory search. **FEATURE:** Markdown authority, lightweight index, tags/links, metadata-first search results. **HOW IT WORKS:** local files contain frontmatter; search weights title/tag/body matches and returns an excerpt plus `matchedOn`; get loads the complete memory. **WHY EFFECTIVE:** users can inspect why an item matched and agents can choose which bodies to read. **ORQALIS CURRENT:** stronger source provenance/review/locking than this compact store, but lacks tags, links and metadata-only memory search. **GAP:** P1 progressive body loading; tag filters P2 unless representative tasks need them. **ADAPTATION:** metadata result contract with matched fields, excerpt and body length; separate get by ID; preserve `.orqalis` and atomic locks. **BENEFIT:** reduced context and explainable selection. **COST:** S/M. **LICENSE:** MIT. **RISKS:** upstream `writeFileSync` is not an atomic transaction strategy to copy; links are free-form and do not demonstrate integrity checking. **RECOMMENDATION:** ADAPT discovery, KEEP Orqalis persistence/proposals, DEFER extra taxonomy. **EVIDENCE:** [search.ts](https://github.com/nova-land/coding-agent-memory-mcp/blob/efa89c0e9f2765a71b0e9e31a7127588644fd36a/src/search.ts), [types.ts](https://github.com/nova-land/coding-agent-memory-mcp/blob/efa89c0e9f2765a71b0e9e31a7127588644fd36a/src/types.ts), [store.ts](https://github.com/nova-land/coding-agent-memory-mcp/blob/efa89c0e9f2765a71b0e9e31a7127588644fd36a/src/store.ts).

### K10: lifecycle and stale proposal protection

**PROJECT:** xChuCx/agent-memory. **SUBSYSTEM:** durable knowledge lifecycle. **FEATURE:** structured section changes, target checksums, staged review, archive-first removal. **HOW IT WORKS:** operations have drift policies; staging records target checksums; application checks drift and archives prior content before removal, with write-once archive paths. **WHY EFFECTIVE:** a later assistant cannot silently replace a target based on an old read; forgotten facts remain auditable. **ORQALIS CURRENT:** immutable record IDs and reviewed new-record proposals, but no curated supersession chain or archive filtering. **GAP:** P1 conflicting approved memories remain simultaneously eligible indefinitely. **ADAPTATION:** new record proposes explicit `supersedes`; approval validates predecessor hash/status, atomically records lifecycle transition; default retrieval returns active only; historical direct access remains possible with successor/rationale/evidence. Retry is idempotent; self/cyclic/cross-project/dangling references rejected. **BENEFIT:** obsolete architecture decisions stop polluting context without erasing history. **COST:** M. **LICENSE:** Apache-2.0. **RISKS:** partial multi-file transitions and crash recovery; automatic forgetting based solely on age would delete useful knowledge. **RECOMMENDATION:** ADAPT, accepted P1; REJECT silent overwrite/automatic deletion; KEEP current review policies. **EVIDENCE:** [operations.go](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/memory/operations.go), [staging.go](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/memory/staging.go), [archival tests](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/memory/archival_ops_test.go).

### K11: labeled retrieval evaluation and discrimination

**PROJECT:** xChuCx/agent-memory. **SUBSYSTEM:** memory retrieval evaluation. **FEATURE:** section search, BM25, negative probes, recall/MRR/nDCG floors. **HOW IT WORKS:** SQLite FTS5 ranks OR-matched literal terms after stopword filtering; a labeled corpus tests ranking and off-topic queries. **WHY EFFECTIVE:** catches the gap between a search returning something and returning the right section. **ORQALIS CURRENT:** lexical count search and integration tests; identifier terms improve lexical segmentation but do not establish relevance. **GAP:** P1 evidence gap until a stable varied labeled corpus exists. **ADAPTATION:** deterministic source/memory/task fixtures with gold sets and held-out queries; measure relevance and context size separately; a small in-process BM25 implementation or optional rebuildable local index can be compared without a mandatory database. **BENEFIT:** objective ranking changes with regression protection. **COST:** M. **LICENSE:** Apache-2.0. **RISKS:** upstream published scores are corpus-specific; paraphrase with zero shared terms is a known lexical limit; copying their corpus alone would not cover Orqalis. **RECOMMENDATION:** ADAPT evaluation; DEFER search dependency until measured benefit. **EVIDENCE:** [query.go](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/index/query.go), [eval harness](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/eval/retrieval_test.go), [method/limitations](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/docs/eval/retrieval.md).

### K12: memory graph and cross-assistant simplicity

**PROJECT:** official MCP memory server. **SUBSYSTEM:** memory interface/persistence. **FEATURE:** entities, directed relations, observations, search/open-node navigation. **HOW IT WORKS:** JSONL stores graph records; mutations load/update/save; current save writes a temporary file then renames; search is substring matching and returns induced relations. **WHY EFFECTIVE:** a compact standard tool surface demonstrates persistence independent of assistant conversation. **ORQALIS CURRENT:** stronger project binding, categories, source freshness and reviewed proposals; MCP already exposes shared core. **GAP:** durable memory navigation is missing but the generic store is not a superior replacement. **ADAPTATION:** apply relation/navigation semantics over curated records, with explicit bounded query/get and resource notifications if demanded. **BENEFIT:** provider portability without another authority. **COST:** S/M. **LICENSE:** current mixed MIT/Apache code transition; docs CC-BY-4.0 per root notice. **RISKS:** a global/default memory-file location would violate repo isolation; simple substring search lacks ranking/freshness; reference implementation is not a production security certification. **RECOMMENDATION:** KEEP Orqalis store/MCP, ADAPT navigation, REJECT store replacement. **EVIDENCE:** [index.ts](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/src/memory/index.ts), [license](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/LICENSE).

### K13: bounded core memory and detailed memory

**PROJECT:** Letta current letta-code, with historical MemGPT concept lineage. **SUBSYSTEM:** memory projection. **FEATURE:** core memory vs referenced detail, filesystem constraints and versioned memory workflows. **HOW IT WORKS:** current `memory-format.ts` distinguishes formats; v2 root Markdown is core, nested material is projected only through directory `MEMORY.md` indexes, and skill files are excluded from that projection; memory constraints count whole staged files including frontmatter. **WHY EFFECTIVE:** a compact stable orientation can guide selective detail retrieval without unbounded persistent context. **ORQALIS CURRENT:** categories initialized and context is capped, but full matching records are indivisible; no explicit summary/detail tier. **GAP:** P1 progressive body-loading overlaps K08/K09; do not create another subsystem. **ADAPTATION:** summarize metadata then fetch selected records/references under one Context Pack budget; protect project-level policy memories through core service policy. **BENEFIT:** smaller onboarding and repeat-task context. **COST:** M. **LICENSE:** Apache-2.0. **RISKS:** user/global/agent memory conflation would break project isolation; cloud default is not suitable as Orqalis authority; current Letta supports local use, so rejecting it as necessarily remote would be inaccurate. **RECOMMENDATION:** ADAPT tier concept, KEEP `.orqalis` root and provider independence, REJECT adopting Letta harness or cloud authority. **EVIDENCE:** [current source pointer](https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md), [memory-format.ts](https://github.com/letta-ai/letta-code/blob/5e420db9f2871bc3106ba14372d4f8d94c5e63ae/src/agent/memory-format.ts), [constraints](https://github.com/letta-ai/letta-code/blob/5e420db9f2871bc3106ba14372d4f8d94c5e63ae/src/agent/memory-constraints.ts).

### K14: temporal contradiction history and retrieval fusion

**PROJECT:** Graphiti. **SUBSYSTEM:** memory lifecycle/retrieval. **FEATURE:** valid/invalid and ingestion/expiration time, episode provenance, hybrid rank fusion. **HOW IT WORKS:** facts carry `valid_at`, `invalid_at`, `created_at`, `expired_at` and episode IDs; resolution can invalidate contradicted edges while preserving history; search combines full-text, embeddings and BFS with RRF/MMR/distance rerankers. **WHY EFFECTIVE:** past facts remain explainable while present context can suppress obsolete claims; independent search signals improve discovery. **ORQALIS CURRENT:** source hash freshness and task provenance, but curated lifecycle absent; rank signals are hand-added scores. **GAP:** P1 supersession overlaps K10; full bitemporal reasoning is not justified yet. **ADAPTATION:** explicit reviewed supersession and reason/time; compare rank fusion only after normalized lexical/graph gold eval. **BENEFIT:** factual history without stale recommendations. **COST:** M lifecycle, L full graph semantics. **LICENSE:** Apache-2.0 at inspected revision. **RISKS:** LLM contradiction inference is not approval; graph backend and embedding/model setup violate simple standard install if mandatory. **RECOMMENDATION:** ADAPT temporal audit idea, DEFER fusion/bitemporal queries, REJECT mandatory Graphiti/database runtime. **EVIDENCE:** [edges.py](https://github.com/getzep/graphiti/blob/ba4a9cb32495b6864160616f8dfa2b898f4a500c/graphiti_core/edges.py), [edge operations](https://github.com/getzep/graphiti/blob/ba4a9cb32495b6864160616f8dfa2b898f4a500c/graphiti_core/utils/maintenance/edge_operations.py), [search](https://github.com/getzep/graphiti/blob/ba4a9cb32495b6864160616f8dfa2b898f4a500c/graphiti_core/search/search.py).

### K15: scoped learned memory and explicit history

**PROJECT:** Mem0 OSS. **SUBSYSTEM:** memory curation. **FEATURE:** scoped fact extraction, configurable vector search, explicit update/delete/history. **HOW IT WORKS:** current `add` requires an identity scope, can bypass inference, uses additive fact extraction when enabled, writes confirmed additions to history; explicit mutation APIs record changes. **WHY EFFECTIVE:** persistent memory can be scoped and inspected outside a single chat. **ORQALIS CURRENT:** project filesystem is a stronger scope for engineering facts; curation is reviewable and source-bound; no vector service necessary. **GAP:** no need to adopt personalized conversational fact extraction to solve code memory; lifecycle overlaps K10. **ADAPTATION:** retain explicit structured proposals and audit lifecycle rather than auto-persist conversation; optional semantic retrieval only if lexical zero-overlap benchmark warrants it. **BENEFIT:** useful lineage without privacy leakage or new authority. **COST:** S concept, L SDK adoption. **LICENSE:** Apache-2.0. **RISKS:** provider cost, embedding drift, source/privacy exposure; user_id/agent_id/run_id is not automatically repository isolation; SQLite history and configurable vector backend add machinery. **RECOMMENDATION:** KEEP Orqalis boundaries, ADAPT history semantics, DEFER vector retrieval, REJECT mandatory Mem0 SDK or model-driven deletion. **EVIDENCE:** [main.py](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/mem0/memory/main.py).

### K16: onboarding, read-only knowledge and integrity

**PROJECT:** Serena, xChuCx/agent-memory. **SUBSYSTEM:** memory governance. **FEATURE:** onboarding/orientation, read-only memories, secret checks and integrity inspection. **HOW IT WORKS:** Serena offers discoverable project memories and read-only patterns; Agent-Memory validates paths/structured updates and tests drift/security; knowledge remains file based. **WHY EFFECTIVE:** assistants reuse team rules without silently overwriting them, and operators can diagnose memory damage. **ORQALIS CURRENT:** category bootstrap, source provenance validation, secret rejection, policy-based proposals and file locks; no per-record read-only state or full link/lifecycle integrity report. **GAP:** integrity checker P1 when references/lifecycle are added; read-only policy P2 unless mutable protected records introduced. **ADAPTATION:** `memory check` should validate schema, unique IDs, source paths, hashes, proposal/lifecycle targets and reference consistency; read-only restrictions belong in the shared application service, not a prompt. **BENEFIT:** cross-assistant continuity and explainable faults. **COST:** M. **LICENSE:** Serena app GPL, Agent-Memory Apache. **RISKS:** directory/category placeholders are not evidence of completed semantic onboarding; secret detector coverage must not be described as perfect. **RECOMMENDATION:** KEEP existing safeguards, ADD integrity alongside accepted references/lifecycle, DEFER extra read-only modes until concrete need. **EVIDENCE:** [Serena manager](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/src/serena/memories/memory_manager.py), [Agent-Memory secrets tests](https://github.com/xChuCx/agent-memory/blob/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2/internal/memory/secrets_test.go), local curated-memory tests.

## Executed finding and bounded implementation proposal

No new P0 was established by this scoped audit. This does not certify absence of P0 issues elsewhere.

P1 K01 minimal fixture:

```python
# unrelated.py
def helper():
    return 1

# caller.py
def run(client):
    return client.helper()
```

Executed using the current `_PythonCollector`, `_ParsedSource`, and `ProjectGraphEngine._assemble` without modifying source files. Output: `run -> unrelated.py::helper`, relation `CALLS`, `EXTRACTED`, confidence `1.0`, evidence `caller.py:2`. This incorrectly binds an unknown receiver to the only global function with the same last component. A corresponding inheritance fixture `class Local(remote.Base): ...` plus an unrelated `Base` triggers the same resolver risk.

Bounded correction: return a typed resolution result/basis, keep unresolved expression nodes scoped to source and call location, eliminate global suffix-only exact binding, preserve supported local/class/import paths, mark candidates honestly, and version parser/graph cache. Add fixtures for unknown receiver, duplicate names, import aliases, lexical shadowing, qualified module calls, nested scope, inheritance, unresolved references, and incremental/full-rebuild agreement. An EXTRACTED call-to-reference edge means the expression occurs in source, not that Python runtime resolves a particular implementation. A source/target explanation must retain that distinction through query filters.

Bounded memory design to synthesize before implementation: immutable new records plus one atomic project-local lifecycle projection/document under the memory lock can make approval/supersession idempotent without rewriting multiple record bodies. Its authority and schema must be explicit, with recovery tests; it is canonical lifecycle metadata, not a disposable search index. Validate the expected predecessor record digest and active state at approval. Store actor/reason/evidence/time and successor; default search/context filter inactive IDs. Pending/rejected proposals never hide an active predecessor. Direct historical reads return status and successor; references do not silently follow a successor without reporting it. Preserve record content and historical proposal files. This is smaller than copying section-splicing or adding a DB and can later support explicit archive-with-reason.

## Objective benchmark and acceptance cases

Baseline and candidate run the **same fixed corpus/query labels/budgets** from isolated revisions; immutable release remains untouched. Include current-development comparator separately from the released comparator so earlier wave improvements are not credited twice. At least two complete benchmark/audit passes must follow accepted gap closure; two repeats of a tiny happy-path suite do not establish convergence.

| ID | Representative engineering case | Gold/negative evidence and required acceptance |
|---|---|---|
| G01 | Python helper refactor with imports, aliases and duplicate names | Gold definitions/imports/call witnesses independently labeled. Zero falsely EXTRACTED target bindings for unknown receivers or unrelated names; every edge has evidence. |
| G02 | TS/TSX frontend callback/component fix | Functions/classes/interfaces/imports produce non-file nodes with exact source locations; unsupported relations explicitly reported. Include multiline, decorators/generics, export aliases, JSX and partial syntax. No regex-only claim of full parser parity. |
| G03 | Backend class implementation/inheritance | Known inheritance vs imported alias vs dynamic factory bases; expected ambiguity is preserved. Exact body reads never select a different same-name symbol. |
| G04 | Unfamiliar module and architecture dependency path | Shortest path returns actual directed witnesses, hop count and truncation; cycles/disconnected graph/budgets covered. Impact means inspection candidates, never complete runtime proof. |
| G05 | Dirty/branch/rename/delete/untracked file changes | Incremental graph semantically equals full rebuild; unchanged warm parse misses zero; one changed file is parsed once; removed targets do not persist. Record total hashing/read/assembly cost too. |
| G06 | Hash cache corruption/parser revision/source changed during read | Rebuild or explicit stale result, never silently use old lines; symbol body source hash is validated before returning or writing. |
| R01 | Mixed architecture, bug, tests, docs, frontend, backend queries | At least 24 labeled queries across multiple fixture shapes; report Recall@5/10, MRR, nDCG@5 and Precision@5 for memory and graph separately; include cold unfamiliar-module and history-only knowledge. |
| R02 | Identifier and natural-language variants | Exact identifier, snake_case, CamelCase/acronyms, ordinary prose; compare baseline/current/candidate; include zero-shared-word paraphrases and disclose lexical misses. Do not claim semantic recall from identifier split tests. |
| R03 | Negative/off-topic and ubiquitous hub words | No false memory match on unrelated queries; unrelated central nodes must be omitted or explicitly marked orientation fallback. Record irrelevant bytes and false-positive rate. |
| R04 | Context budgets 1k/4k/12k/20k chars | Serialized result fits cap including metadata; gold recall per 1,000 bytes measured; long high-value memory doesn't disappear without a preview/reference; repeated neighbors do not consume unbounded budget. |
| R05 | Repeated repository task with durable memory | Compare full-source rediscovery vs selective memory+graph+history: actual files opened, memories opened, source bytes, context bytes, tool calls and time to first useful gold item. Task success checked by deterministic artifact assertions or actual task run; context shrink alone is not task success. |
| M01 | Architecture decision superseded after accepted task | Before approval old active only; after approval new active only, old retrievable with successor/reason/evidence; rejected proposal leaves old active; repeated approval idempotent. |
| M02 | Stale staged supersession and concurrent approvals | Expected predecessor hash/status mismatch rejects with conflict; no double-active contradictory transition; simulate crash around record/lifecycle/proposal persistence and recover without losing history. |
| M03 | Explicit memory references and progressive read | Fetch selected overview without all linked bodies; selected next hop returns exact ID/provenance; missing/self/cyclic/cross-project references safely reported; total depth/nodes/bytes bounded. |
| M04 | Branch/worktree-aware memory freshness | Changed/deleted provenance stale; unchanged hashes stay fresh across commit change; unrelated repo rejected; a memory's age alone does not prove it is stale. |
| M05 | Secret/link/path/corrupt-memory probes | Existing secret/path protection preserved on proposals, metadata and lifecycle reasons; malformed schema/dangling IDs reported; no ignored corrupt canonical record silently treated as absent. |
| M06 | Assistant A writes, assistant B resumes | Two fresh service instances read identical approved memory/lifecycle/context from the same project; project B cannot observe project A; no chat/provider state required. |
| S01 | Outline/body/references with stale source | Qualified symbol, nested function, duplicate names, decorators, Unicode and stale hash; bounded exact body or explicit ambiguity/staleness. Semantic reference coverage labeled by backend capability. |

Measurement rules: report warm and cold p50/p95 with sample counts/environment; monotonic timings; parser misses vs complete file reads; UTF-8 bytes and Unicode character count separately. Use an identified tokenizer where installed or mark tokens unavailable/estimated; never call `chars/4` observed usage. A retrieval precision gain should have no unacceptable recall regression on held-out cases. Record actual model requests/tokens/tool events only when produced by real provider runs; deterministic retrieval tests are useful but cannot fill missing end-to-end task-success metrics with fabricated zeroes.

Acceptance priorities: K01 provenance correction, K10 curated supersession, K08/K09 progressive memory references, K06 bounded symbolic reads, K02 JS/TS parser capability, and K11 reproducible held-out evaluation are high-value gaps to close before knowledge-subsystem convergence. Personalization, BM25, communities, vectors, LSP/SCIP, full bitemporal queries and broad multimodal ingestion remain benchmark-led opportunities, not reasons to install a collection of external runtimes.


## Development follow-up (2026-09-26; not a baseline rewrite)

The initial observations above remain the before-state evidence. Subsequent accepted work
implemented K01 conservative provenance, K10 reviewed atomic curated-memory supersession,
K08/K09 stable references and bounded discovery/body pages, and K16 integrity checks.
`memory/lifecycle.json` is canonical transition authority; immutable successor markers hide
unpublished successors across crashes. Default search/context/index lists only active records.
Operator CLI inspection/approval/rejection preserves the review boundary; MCP has read and
proposal operations, not unrestricted approval. Long relevant memories retain previews in
Context Packs, provider projections and capsule evidence. Graph ranking now exposes reasons
and explicitly labels centrality-only orientation results, without introducing a new ranker.

Focused verification: 40 memory lifecycle/navigation/interface/context tests passed, including
three injected approval interruption boundaries, competing approvals, source review drift,
cycle checks, cross-project reads, MCP root validation, CLI approval, Unicode body pagination,
and 1k/4k/12k Context Pack budgets. The discovery fixture uses more than 20 times fewer
response characters than its complete body; this is a deterministic fixture measurement,
not a real-provider task-success claim. Root-owned benchmarks provide aggregate/held-out
results and convergence accounting. Symbolic read and JS/TS extraction work is tracked by
the parent enhancement wave; no claim of LSP semantic completeness is made here.


K06 symbolic-read acceptance is now implemented in `graph/symbols.py`, the SDK and four
read-only MCP wrappers. Discovery retains duplicate names as distinct IDs; complete body
reads require the discovered SHA-256 and exact UTF-8 byte span, with stale/deleted-source
conflicts and explicit oversized-body errors. References retain static candidate provenance.
Bounded `source_coverage` diagnostics report parser extraction limits without claiming LSP
completeness. At this verification stage, root-owned parser v4 supplied Python decorator spans and
Tree-sitter JS/TS/TSX spans. The subsequent v5 correction derives native-parser coordinates
from source bytes rather than Point property getters; see the [frozen-source audit](KNOWLEDGE_RESEARCH.md#knowledge-audit-iteration-1)
and [native failure evidence](KNOWLEDGE_RESEARCH.md#native-parser-preflight-correction). No symbolic source writes
were introduced.

Final focused follow-up: 20 tests passed in 26.83 seconds (nine symbolic-read cases, ten
navigation cases, one operator/SDK/MCP integration scenario). These include same-line JS
symbols, Unicode TS methods, decorated Python, duplicate names, inferred-reference filtering,
malformed non-object memory frontmatter, bounded parser diagnostics and stale-preview health.
Ruff and strict mypy passed for the 12 scoped source/test files. Earlier lifecycle/context
suite evidence above remains applicable; this follow-up does not replace the parent's full
regression run or fixed-corpus benchmark convergence requirements.

---

## Project Memory storage and read optimization

Reviewed 2026-09-27. This is a bounded storage/performance review after the user's request
to learn from Graphify and other memory projects. No upstream code or prose was copied.
The immutable `v2.0.0` baseline and earlier candidate source freeze remain unchanged;
this in-development change needs final whole-project qualification.

### What Graphify's three files mean

Current [Graphify README at `4377ee93`](https://github.com/Graphify-Labs/graphify/blob/4377ee93aa6a00401bd079c5c1ce9ae15674d49d/README.md#L58-L65)
lists `graph.html`, `GRAPH_REPORT.md`, and `graph.json` as user-facing outputs.
It also describes [manifests and caches](https://github.com/Graphify-Labs/graphify/blob/4377ee93aa6a00401bd079c5c1ce9ae15674d49d/README.md#L449-L463).
The [query server](https://github.com/Graphify-Labs/graphify/blob/4377ee93aa6a00401bd079c5c1ce9ae15674d49d/graphify/serve.py#L121-L180)
loads graph JSON into memory and refreshes its derived trigram index on an `(mtime_ns, size)`
change. These are useful output/query patterns, not evidence that durable project memory
should be replaced with three authoritative files. Orqalis keeps its reviewable
`.orqalis/memory/records`, lifecycle ledger, project scope and explicit history.

The [official MCP memory server](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/src/memory/index.ts#L89-L205)
uses a small JSONL store but reads and rewrites the whole graph; its search is
[substring based](https://github.com/modelcontextprotocol/servers/blob/f46d9578190b476b3501923ea8977d899e8db2cb/src/memory/index.ts#L310-L355).
[Mem0](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/mem0/configs/base.py#L11-L45)
adds vector storage and SQLite history, with different runtime/storage costs.
[Letta Code](https://github.com/letta-ai/letta-code/blob/f281bed3feca7a9389ce000c24413b746c209e70/src/backend/local/system-prompt-compilation.ts#L81-L142)
selectively projects committed Markdown memory. Orqalis already has bounded summaries,
references and explicit body access; neither project demonstrates a safe drop-in replacement
for the local, reviewed canonical records.

### Change and observed result

`CuratedMemoryStore.statuses` checks one result set with one lifecycle document and a
request-local hash per distinct source path. Context Pack, SDK search/status and discovery
use it. Individual `status` preserves its public behavior through the same routine. No
persistent cache, new file format, hosted component or additional authority was added.
Long-body paging now caps serialized trial slices by the response budget; the existing
character offsets and exact page content remain unchanged.

[Fixed-corpus before/after smoke](../evidence/memory-batch-comparison.json) uses the same
three cases, nine workflows, dataset, script and dependencies. Every exact answer,
response size, budget and history witness remained unchanged. For the three
`full_rediscovery` workflows together, metadata opens fell **66 to 48** (27.3%) and
metadata returned bytes fell **76,951 to 69,175** (10.1%). Each case's Context Pack and
all-active listing used two lifecycle reads instead of five, so lifecycle reads across
both calls fell from ten to four per case. Source and canonical memory record reads did
not change. The focused batch test verified one source hash for three records sharing a
path, a fresh hash on the next request after an edit, an alternate source root, and correct
supersession. The broader memory/context/API set passed 46 checks; the final paging and
lifecycle subset passed 19. Ruff, formatting and strict mypy passed.

[Order-reversed measured captures](../evidence/memory-batch-timing-review.json) keep raw
case samples and matched environments. They vary substantially in both directions across
workflows unaffected by this edit, so elapsed-time improvement is **unproven**. This
optimization establishes less duplicate metadata I/O and bounded temporary page trials;
it does not establish less canonical-record I/O or lower whole-workflow latency.
`discover` still parses all canonical records; each separately requested body page still
loads its record. A request-local hash is a point-in-time freshness check, not an atomic
snapshot of concurrently edited repository files. Full regression, comparative contracts,
package checks and two clean global audit iterations remain pending.

### Decision

KEEP the simple canonical record and reviewed lifecycle design. ADAPT Graphify's idea of
avoiding repeat work only within one request, where no cross-request stale cache is needed.
DEFER a persistent memory index or `(mtime, size)` cache until a larger held-out workload
proves a net benefit and an invalidation policy preserves hand edits and source freshness.
DEFER vector/database adoption for the same reason and to keep normal installation local.

---

## Native parser preflight correction

Observed 2026-09-26 on CPython 3.12.14 / Windows with tree-sitter 0.26.0,
JavaScript 0.25.0 and TypeScript 0.23.2. This was a P1 finding in G02, not a clean
qualification iteration.

The fixed engineering corpus reproducibly exited with access violation 0xC0000005
while initializing its graph. The same failure reproduced by parsing the immutable
baseline `web/src/MetricsView.tsx` alone. A minimal own-source fixture containing
300 newlines followed by one function/call also terminated its isolated Python
process. [The original fault trace](../evidence/parser-native-crash-preflight.log) is retained.

The defect is consistent with the reference ownership problem visible in the pinned
[binding Point getters](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c):
those property getters return a borrowed tuple element. Small coordinates had masked
this in earlier fixtures. An [upstream report](https://github.com/tree-sitter/py-tree-sitter/issues/487)
describes a related Point-access crash with a different grammar/platform; it is
supporting evidence, not proof that the upstream reporter ran this Orqalis fixture.

Orqalis now derives row and byte-column coordinates from its own immutable source
bytes, avoiding every native Point getter. Rows retain the grammar's LF semantics;
CRLF counts once, and a Unicode line-separator inside a comment does not alter the
physical LF row. Exact source byte spans remain authoritative. Parser identity moved
to `source-ast-v5`, invalidating prior derived parser caches. No upstream source was
vendored or dependency version changed.

After the correction, 30 minimal reproducer passes and ten passes each of the frozen
MetricsView/types files completed. The permanent subprocess regression adds 60
parses across JS, TS and TSX, with high row/column values, UTF-8 text, duplicate names,
exact byte slices and call locations. [Focused JUnit](../evidence/parser-v5-regression.xml)
records the graph/provenance/symbol checks. The full corpus, package and final-source
regression still require their own subsequent evidence; old captures remain preflight.

---

## Knowledge audit, iteration 1

Audit date: 2026-09-26. Scope: repository intelligence, durable memory research, browser/constrained benchmark integrity, and the native parser coordinate correction. Baseline remains immutable `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / v2.0.0. This is a scoped independent review, not a declaration of global convergence or a timed performance result.

### Fresh upstream verification

A fresh `git ls-remote --symref https://github.com/OWNER/PROJECT.git HEAD` check completed for every knowledge reference at **2026-09-26 16:12:13-16:12:17 UTC**. Exact remote `HEAD` lines were compared with the previously source-inspected local checkout's `git log -1`; all 13 matched. The extra `refs/remotes/origin/HEAD` advertised by letta is not its remote HEAD. [Raw command evidence](knowledge-upstream-heads-iteration-1.json) retains timestamps, status, remote output and commit date/message. No inference of maintenance quality is made from recent dates alone; Aider and nova-land have older default-branch tips and were not relabeled abandoned.

| Reference | Remote HEAD | Commit timestamp | Change since initial source audit |
|---|---|---|---|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify/tree/4139885a1212956cf69a76946fbde0d181ab85e9) | `4139885a1212` | 2026-09-26T14:02:32+01:00 | Unchanged |
| [Aider-AI/aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490bb35f` | 2026-05-22T07:02:20-07:00 | Unchanged |
| [oraios/serena](https://github.com/oraios/serena/tree/7a2968335f2198b966864de1ce3655c8e485a653) | `7a2968335f21` | 2026-09-24T10:57:40+02:00 | Unchanged |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter/tree/dcdc8cc55e5dfedfc858080835f153999a29ec40) | `dcdc8cc55e5d` | 2026-09-24T10:39:55+02:00 | Unchanged |
| [microsoft/multilspy](https://github.com/microsoft/multilspy/tree/b9a0ef1bc221e5575787be80493059b01f03c37a) | `b9a0ef1bc221` | 2026-08-20T21:51:04+05:30 | Unchanged |
| [sourcegraph/scip](https://github.com/sourcegraph/scip/tree/08b592d981d675d46de9301b50c66ed9064dc759) | `08b592d981d6` | 2026-09-25T21:51:38+02:00 | Unchanged |
| [nova-land/coding-agent-memory-mcp](https://github.com/nova-land/coding-agent-memory-mcp/tree/efa89c0e9f2765a71b0e9e31a7127588644fd36a) | `efa89c0e9f27` | 2026-05-30T14:38:54+01:00 | Unchanged |
| [xChuCx/agent-memory](https://github.com/xChuCx/agent-memory/tree/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2) | `4f4c6ef30af0` | 2026-09-25T15:51:01+03:00 | Unchanged |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/f46d9578190b476b3501923ea8977d899e8db2cb) | `f46d9578190b` | 2026-09-22T07:30:15-07:00 | Unchanged |
| [letta-ai/letta](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) | `5bcdd177d70f` | 2026-09-10T10:59:06-07:00 | Unchanged |
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code/tree/5e420db9f2871bc3106ba14372d4f8d94c5e63ae) | `5e420db9f287` | 2026-09-25T20:14:46-07:00 | Unchanged |
| [getzep/graphiti](https://github.com/getzep/graphiti/tree/ba4a9cb32495b6864160616f8dfa2b898f4a500c) | `ba4a9cb32495` | 2026-09-25T18:14:51-05:00 | Unchanged |
| [mem0ai/mem0](https://github.com/mem0ai/mem0/tree/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd) | `94c3fe9f238f` | 2026-09-25T23:04:12+05:30 | Unchanged |

These unchanged revisions preserve the code-backed findings in [KNOWLEDGE_RESEARCH.md](KNOWLEDGE_RESEARCH.md). The [current Serena license](https://github.com/oraios/serena/blob/7a2968335f2198b966864de1ce3655c8e485a653/LICENSE) still distinguishes GPL-3.0-or-later application code from MIT SolidLSP; earlier blanket MIT descriptions must not be reused. Current Orqalis additions are independent implementations of behaviors, not copied Serena application code. [Graphify's pinned license](https://github.com/Graphify-Labs/graphify/blob/4139885a1212956cf69a76946fbde0d181ab85e9/LICENSE) is Apache-2.0 with the separate historical notices documented in the original audit. [Letta's current pointer README](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) means active-harness comparison must include letta-code rather than silently treating the archived v1 server as current. The official MCP server's mixed historical notice and each grammar/server component's own terms remain separate checks.

### Re-evaluated knowledge decisions

| Capability | Decision after implementation and audit | Evidence and remaining limit |
|---|---|---|
| K01 conservative graph evidence | KEEP native provenance correction | Per-occurrence unresolved references and inferred resolution labels avoid claiming static certainty. Reference occurrences must remain distinct from declarations in ordinary retrieval; newly visible caller paths can otherwise inflate context/search noise. |
| K02 multi-language syntax extraction | KEEP bounded Python/JS/TS/TSX extraction; DEFER broad language claim | Exact byte spans, static budgets and visible extraction diagnostics are useful. Tree-sitter syntax does not establish LSP-grade binding. Native binding defect found during corpus qualification required v5 correction described below. |
| K03 incremental graph freshness | KEEP content-addressed cache and deterministic rebuild | Reusing unchanged parse results is useful. Inventory hashing and graph assembly still occur; no constant-time incremental-index claim. |
| K04 graph navigation and heterogeneous ingestion | KEEP bounded impact/path tools; DEFER communities and multimedia | Implemented tools are directly testable; broader graph community or non-code ingestion needs a demonstrated task and corpus. |
| K05 personalized repo maps | DEFER personalization/centrality tuning | Current lexical and graph evidence must first be discriminated against held-out precision/recall negatives. Recent upstream activity is not evidence to copy a ranker. |
| K06 symbolic operations | KEEP hash-checked, exact-byte, bounded reads and candidate references; DEFER automatic edits | Exact symbol IDs and source digest checks are reviewable and stale-safe. References stay syntactic candidates; replacement/rename/refactor needs a distinct safety and correctness contract. |
| K07 semantic index ingestion | DEFER optional LSP/SCIP integration | Component/runtime/license cost and semantic-resolution benefit need a specific language corpus. No mandatory database or language-server daemon is justified by current evidence. |
| K08/K09 progressive memory | KEEP summaries, references, bounded body pages and incomplete-body previews; DEFER BM25/vector additions | Durable fact discovery can reduce returned context. Individual pages still load a complete record locally; total local bytes can exceed a less-selective read. No claim that automatic ContextPack stops scanning source. |
| K10 lifecycle and stale proposals | KEEP immutable facts plus reviewed atomic supersession | Active-only context/index and explicit historical access preserve authority. Lock-protected predecessor digest/current-active checks, conflict/cycle/recovery tests are the acceptance evidence, not upstream feature lists. |
| K11 retrieval evaluation | KEEP labeled gold and negative cases; ADAPT methodology before ranking | Fixture witnesses must bind exact record/source, reject contradictions and avoid arbitrary-payload substring PASS. The memory benchmark has a separately owned hardening review; preliminary figures are not final acceptance. |
| K12 simple memory graph | KEEP local memory-to-memory references; REJECT replacing authority with a generic graph DB | Project-bound `.orqalis` remains authoritative and restartable. Generic entity/relation APIs do not alone provide approval or supersession semantics. |
| K13 core/detail memory | KEEP bounded discovery and explicit retained-ID reads | Fresh-SDK workflow fixture establishes continuity. It is a current-version workflow comparison, not automatically a v2 speed comparison or a no-source-read guarantee. |
| K14 temporal graph/retrieval fusion | DEFER Graphiti-style temporal fusion and backend adoption | Reviewed immutable supersession closes the concrete lifecycle defect with fewer required services. General temporal claims, embeddings and conflict inference need separate truth labels. |
| K15 learned memory | KEEP explicit scoped history; DEFER automatic fact extraction/update | Do not confuse an inference provider's proposed fact with reviewed project truth; mem0 behavior is described at its actual pinned current revision. |
| K16 onboarding and integrity | KEEP bounded discovery/check workflows; DEFER generalized executable-memory policy | Integrity reports preserve parse errors, stale references and lifecycle visibility. Operator approval stays separate from assistant proposal/read tools. |

Current benchmark evidence found a concrete retrieval-category issue: new occurrence references have their own source paths, whereas baseline unresolved global references had no file path. Treating occurrences identically to declarations can place callers ahead of definitions. The bounded recommendation is a distinct index reference kind with definition preference for equal lexical scores, and omission of occurrence nodes from ordinary context seeds/candidates while retaining graph edges and explicit reference access. This is a semantic distinction, not a corpus-label-specific boost. Acceptance requires renamed fixtures, many callers, a real definition, reference-only queries and unchanged negative-query orientation labels. Broader query-expansion precision remains a separate tradeoff.

### Benchmark integrity findings and corrections

| Finding | Concrete false-positive or fairness risk | Correction and acceptance |
|---|---|---|
| UI accepted arbitrary frontend | A current bundle could be paired with baseline backend and labeled baseline solely because it had an `index.html` and a stable hash. | `build_benchmark_frontend.py` builds an isolated source copy and requires selected-source lock equality with the reused dependencies. Manifest binds source/web, all actual dependency files, node binary/version, builder, pipeline and resulting artifacts. Benchmark rejects wrong-revision or altered bundles. |
| Unbound benchmark helper | Both reviewed scripts execute `benchmark_quality.py`; omitting its hash means helper behavior can change without harness evidence changing. | UI binds helper, builder, browser script, own script and build manifest before/after. Root-owned constrained correction binds helper/self/environment. |
| UI state alone lacked correlation | Seeing PAUSED after POST did not prove the same run or the corresponding persisted event/snapshot was rendered. | Each sample binds run ID, unique command key, durable event ID/type/key, before/event/persisted/snapshot/DOM sequences, and exact route. Footer sequence and state must match the observed WebSocket snapshot; unrelated/replayed witnesses fail. |
| Failed capture left old PASS | Reusing an output path after an early subprocess error could leave prior successful evidence visible. | Output is invalidated to RUNNING before work and exceptions write FAIL; subprocess calibration starts with an old PASS and requires its replacement. |
| Constrained success accepted any path | Nonempty `relevant_files` could pass with only an unrelated path. | Root-owned correction requires an actual fixture service path under each context cap. This is a small local init/graph/context qualification, not autonomous coding success. |
| Constrained elapsed interval included evidence work | End fingerprint/dependency enumeration can add revision-size-dependent work unrelated to the intended workload. | Root-owned correction records elapsed immediately after workload, before verification metadata. Smoke emits no timing. |
| Cap evidence ambiguity | Requested cap alone does not prove kernel-enforced cap; a per-process commit cap is not total machine RAM or RSS. | Root-owned implementation reads Job Object settings back, requires one allowed CPU and 256 MiB per-process commit limit, and reports measured peak process commit under that bound. Scope remains explicit. |

The UI builder creates a temporary Git boundary and ignores its dependency junction and build output so Tailwind cannot walk shared dependencies as project source. It never builds in the baseline archive or root production web directory. Generated directories are excluded only at the web root; a real `src/dist` directory remains an input. Only a checked junction/symlink is removed before temporary-workspace cleanup. Existing build outputs cannot be reused as new build directories.

[Adversarial calibration](../../../tests/unit/test_benchmark_ui_evidence.py) currently has 25 passing tests covering wrong revision, artifact additions/changes, dependency/lock changes, unqualified manifests, unrelated run/command/type, replayed events, cursor mismatch, non-integer cursor and non-finite/inconsistent latency. Ruff and strict mypy passed on the builder, UI harness and these tests. The retained smoke captures are [current](../evidence/ui-current-smoke-qualified.json) and [baseline](../evidence/ui-baseline-smoke-qualified.json). Both final repeated smokes PASS with stable source/harness/build inputs and six exactly correlated transitions (three pause/resume pairs), with every latency field and aggregate timing set to null. Current source fingerprint is `a37dda9e2ca4d37e58ffc6fcab606324df31e16b02dc1261a3371cd44792a757`; baseline is `7dcede8468792d5c51805bb3fc865f09370892ba6ca101d40dcfd6b840fcbad7`.

One earlier current preflight lacked a correlation witness before detailed diagnostics existed. It did not reproduce in the next diagnostic or six-transition frozen smoke, but its original cause remains unestablished; this review does not claim a causal production fix. The next diagnostic completed both transitions and correctly rejected concurrent source/helper drift. [Calibration history and limitations](../../../benchmarks/README.md#ui-calibration-development-history) retain these failures rather than hiding development retries. The correlation predicate was not weakened. Failures now retain bounded socket/event/snapshot/DOM/server diagnostics and replace prior output with FAIL; a subprocess test proves stale PASS output cannot survive. Formal repeated timing still requires a later quiet capture from final frozen sources and harness.


### Independent native parser correction review

The v5 change in `graph/ecmascript.py` derives coordinates from immutable source bytes: one initial LF-byte-offset array, then `bisect_right(offset) - 1`. This produces one-based physical rows and zero-based byte columns, including offsets immediately after LF and multibyte UTF-8 text. The reviewed collector uses start/end byte offsets for symbol lines, duplicate-name location keys, import locations and calls; no native `start_point`/`end_point` property getter remains there. Exclusive symbol byte spans are preserved. No defect was found in this bounded coordinate review.

The parent retained the [native failure and correction evidence](KNOWLEDGE_RESEARCH.md#native-parser-preflight-correction), including the pinned [0.26.0 Point binding source](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c), supporting [upstream issue 487](https://github.com/tree-sitter/py-tree-sitter/issues/487), and an isolated high-row/high-column subprocess regression across JS/TS/TSX. Those upstream facts support the workaround; the independent read does not replace full-corpus and final-source regression qualification.

### Remaining scope

No upstream HEAD change alone reopened a KEEP/DEFER decision. Final retrieval results, memory witness hardening, final-source regression/package checks and quiet timing belong to their separate evidence owners. A successful UI smoke proves this correlated local flow and input stability only. This document does not assert repository-wide convergence, full semantic reference accuracy, universal memory savings or successful live-provider autonomy.

---

### Final scoped audit: knowledge

Date: 2026-09-26. Source freeze: **2026-09-26 16:50:12 UTC**, source inventory SHA-256 **`a37dda9e2ca4d37e58ffc6fcab606324df31e16b02dc1261a3371cd44792a757`**. This source freeze remains provisional while global preflight failure analysis and qualification are pending. Its [retention manifest](../evidence/preflight-ranking-evidence-manifest.json) verifies the byte-identical copy; the fingerprint is unchanged. The complete package/lock inventory was rehashed for this report and exactly matched [the frozen inventory](../evidence/final-source-freeze.json). Baseline remains immutable commit `b8506f7d9c471516fe4b21c9caa735a7a7909af6` / v2.0.0.

**Scoped disposition: candidate clean for the reviewed knowledge criteria; global qualification remains pending.** This audit found no new concrete P0/P1 knowledge defect after the documented provenance, native parser, memory lifecycle, bounded read and occurrence-ranking corrections. It does not override failed benchmark metrics, the full-suite/package gates, the historical UI preflight failure, or later quiet measurements. No production edit, benchmark launch, label change or PASS-report rewrite was performed as part of this final audit.

#### Fresh primary-source check

All 13 public remote HEADs were checked again during **2026-09-26T16:51:23.730983+00:00 through 2026-09-26T16:51:27.442916+00:00** using `git ls-remote --symref ... HEAD`. [Raw final check](knowledge-upstream-heads-final-audit-1.json) retains exact output, inspected SHA, new SHA, status and timestamp. Twelve were unchanged; Letta Code advanced during this session.

| Reference | Fresh remote HEAD | Compared with source-inspected pin |
|---|---|---|
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify/tree/4139885a1212956cf69a76946fbde0d181ab85e9) | `4139885a1212` | unchanged |
| [Aider-AI/aider](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | `5dc9490bb35f` | unchanged |
| [oraios/serena](https://github.com/oraios/serena/tree/7a2968335f2198b966864de1ce3655c8e485a653) | `7a2968335f21` | unchanged |
| [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter/tree/dcdc8cc55e5dfedfc858080835f153999a29ec40) | `dcdc8cc55e5d` | unchanged |
| [microsoft/multilspy](https://github.com/microsoft/multilspy/tree/b9a0ef1bc221e5575787be80493059b01f03c37a) | `b9a0ef1bc221` | unchanged |
| [sourcegraph/scip](https://github.com/sourcegraph/scip/tree/08b592d981d675d46de9301b50c66ed9064dc759) | `08b592d981d6` | unchanged |
| [nova-land/coding-agent-memory-mcp](https://github.com/nova-land/coding-agent-memory-mcp/tree/efa89c0e9f2765a71b0e9e31a7127588644fd36a) | `efa89c0e9f27` | unchanged |
| [xChuCx/agent-memory](https://github.com/xChuCx/agent-memory/tree/4f4c6ef30af0a6dc9b63d4ff1400c75565d358e2) | `4f4c6ef30af0` | unchanged |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/f46d9578190b476b3501923ea8977d899e8db2cb) | `f46d9578190b` | unchanged |
| [letta-ai/letta](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) | `5bcdd177d70f` | unchanged |
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code/tree/115779008e69b8aedd5251a943dba7cf5f62631a) | `115779008e69` | advanced; inspected delta below |
| [getzep/graphiti](https://github.com/getzep/graphiti/tree/ba4a9cb32495b6864160616f8dfa2b898f4a500c) | `ba4a9cb32495` | unchanged |
| [mem0ai/mem0](https://github.com/mem0ai/mem0/tree/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd) | `94c3fe9f238f` | unchanged |

The exact [Letta Code commit](https://github.com/letta-ai/letta-code/commit/115779008e69b8aedd5251a943dba7cf5f62631a) was fetched into the isolated research checkout and inspected with Git after the web renderer could not fetch it. Commit date is 2026-09-26 09:33:16 -07:00 (16:33:16 UTC). Its only change is five added lines in `scripts/isolated-unit-tests.json`, adding `src/websocket/app-server-openai.test.ts` to the isolated test list with a 30-second timeout because it starts a real app server and changes process-global backend state while testing persistent local conversations. There is **no production memory/runtime or license change** in this delta. The practical lesson is test isolation for process-global backends; Orqalis's disposable processes/repositories already provide the corresponding benchmark separation. K13 and the other knowledge KEEP/DEFER decisions remain unchanged.

The [initial source-backed research](KNOWLEDGE_RESEARCH.md) and [iteration-1 reassessment](KNOWLEDGE_RESEARCH.md#knowledge-audit-iteration-1) remain the detailed capability and license records. In particular, current Serena application GPL-3.0-or-later and MIT SolidLSP are distinct; the official MCP server mixed historical notices, Graphify historical notices, and Tree-sitter grammar/binding terms remain component-specific. A recent commit alone is not a quality score, and older Aider/nova-land tips are not proof of abandonment.

#### Frozen-source acceptance review

| Criterion | Reviewed mechanism/evidence | Bounded disposition |
|---|---|---|
| Conservative graph relations | Per-occurrence unresolved references; explicit inferred resolution basis; deterministic cache invalidation and provenance tests | KEEP. No claim of Python/TS runtime or LSP-complete resolution. |
| Native multi-language extraction | v5 collector derives rows/byte columns from immutable LF byte offsets; no native Point getters remain in ECMAScript positions; exact UTF-8 byte spans and visible extraction diagnostics | KEEP. Independent coordinate read found no defect. [Native failure/correction evidence](KNOWLEDGE_RESEARCH.md#native-parser-preflight-correction) and existing high-coordinate subprocess regression remain authoritative. |
| Symbol reads and references | Exact discovered symbol ID and source SHA required; current bytes rehashed; exclusive span validated; complete body either fits serialized cap or fails; bounded source-coverage warnings; references explicitly candidate-only | KEEP. A stale symbol cannot silently return unrelated source. No automatic rename/edit safety claim. |
| Durable memory authority | Canonical `.orqalis` records immutable across supersession; reviewed lifecycle marker; predecessor digest/current-active validation under the same file lock; pending successor hidden until publication | KEEP. Existing lifecycle conflict, cycle, crash/idempotency/history tests support the mechanism; global final-source rerun remains a separate gate. |
| Progressive memory | Active-only bounded discovery; explicit record/history read with summaries, references, source/freshness metadata and advancing character cursor; ContextPack incomplete-body preview when complete record does not fit | KEEP. Response caps do not imply bounded local file reads or zero source inspection. Historical records stay explicitly accessible. |
| Memory integrity and operator boundary | Integrity checks run under the memory lock; malformed/missing/stale references surfaced; CLI/direct operator approval remains separate from MCP proposal/read tools | KEEP. Assistant write authorization does not grant self-approval. |
| Index/context distinction | `IndexRecordKind.REFERENCE`, `lexical-v3` cache invalidation, equal-score declaration preference, occurrence nodes excluded from ordinary context seeds/candidates while graph relations/reference tools remain | KEEP. Exact declaration witnesses pass; broad partial-token noise remains measurable. |
| Negative-query context | Lexical/dependency/changed signals remain distinct from centrality-only orientation; report preserves orientation counts | KEEP. Empty matched paths do not mean an empty context pack. |
| Local-first/restart model | No mandatory graph/vector database introduced; canonical records/history remain separate from rebuildable graph/index caches | KEEP. New parser dependencies do not change authority location. |

This pass re-read the frozen symbol-body checks, memory discovery/body/history paths, active-lifecycle filtering and the exact parser position logic. Previously executed focused tests are documented in their owning reports; this read-through does not mislabel those as a new full-suite run.

#### Retrieval disposition without label changes

[RANKING_REVIEW.md](RANKING_REVIEW.md) independently reviews **all 29** fixed cases and their baseline/current path orders against frozen source and doc sections. It preserves primary-target labels and the real regressions: the memory doc leaves index top five; documentation MRR falls from rank 2 to 5; provider-refactor first-hit rank falls because the actual request/response contract now comes first. These are bounded accepted tradeoffs in this corpus, not fabricated improvements or permission to edit the comparison status.

The exact caller-before-definition defect is corrected: `source_hashes`, `PermissionProfile`, and the other held-out exact declarations are first in their defining paths. Added lower-ranked consumers/contracts are often useful, but generic source/type/input/task matches can be weak. Index positive-case mean recall is 87.04% versus 72.22%; context is 87.04% versus 85.19% in the scoped capture. These figures do not establish full coding success or erase per-case losses. The ranking report's implementation fingerprint predates the unrelated cancellation freeze; its witness corpus/ranking mechanism is identified explicitly there.

Existing misses remain: Markdown section retrieval, the frontend type contract, interrupted-task paraphrase, and broad hub disambiguation. **DEFER** full semantic/LSP/SCIP, vector/BM25, personalization and generalized temporal-graph additions until a new held-out task demonstrates benefit with acceptable precision/cost. **REJECT** query-specific synonym rules, boosts of these gold paths, or retroactive relabeling merely to improve metrics.

#### UI/constrained evidence boundary

The final [current](../evidence/ui-current-smoke-qualified.json) and [baseline](../evidence/ui-baseline-smoke-qualified.json) correctness captures both passed six transitions with stable source/build/helper/tool inputs; current source equals this freeze. Each command has a unique key and the matching persisted event/run/sequence, WebSocket snapshot and DOM footer sequence. All action timings and the aggregate are null. The build is a selected-source isolated copy, lock-matched to actual dependency files and protected by a temporary Git ignore boundary. Neither the baseline archive nor production frontend was built in place.

Twenty-five UI adversarial calibration tests passed, with Ruff/strict mypy and browser syntax checks. Wrong source artifacts, altered dependencies, wrong/replayed events, mismatched cursor/run and stale PASS output are rejected. The [calibration notes](../../../benchmarks/README.md#ui-calibration-development-history) retain one earlier uninstrumented missing-witness preflight. It did not recur in later exact-witness repeats; its cause is unestablished, and no causal production fix is claimed. The stricter witness was never weakened. If it recurs in formal capture, preserve and diagnose the detailed failure rather than retrying it out of evidence.

The root-owned constrained corrections reviewed earlier bind helper/self/environment, require a real service fixture path, stop the workload timer before evidence hashing, and read the actual one-CPU/256-MiB-per-process commit cap back from the kernel. This scope is not a whole-machine RAM, RSS, browser or live-provider qualification. Final repeated measurements and global report decisions belong to the root audit; this scoped read does not auto-promote them to PASS.

#### Remaining gates

Full final-source regression, package/install qualification, final measured memory capture, constrained qualification, quiet repeated comparison and a subsequent independent audit remain separate evidence requirements. No new benchmark process was launched for this final audit. Upstream refresh and source review alone do not establish global convergence.
