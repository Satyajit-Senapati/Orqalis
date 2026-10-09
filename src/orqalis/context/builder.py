"""Rank graph, curated memory, task history, and Git state into a small pack."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from heapq import nsmallest
from pathlib import Path

from orqalis.context.models import (
    GraphContextItem,
    HistoricalTaskContext,
    MemoryContextItem,
    ProjectContextPack,
)
from orqalis.domain.errors import InputError
from orqalis.git.contracts import GitService
from orqalis.git.service import LocalGitService
from orqalis.graph import GraphNodeKind, ProjectGraph, ProjectGraphEngine
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryFreshness,
    MemoryLifecycle,
    MemoryRecordStatus,
)
from orqalis.memory.navigation import MemoryDiscoveryItem, memory_preview
from orqalis.persistence.filesystem.io import ensure_no_filesystem_links, read_json_object
from orqalis.persistence.filesystem.layout import ProjectLayout, load_manifest, resolve_project_root
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore
from orqalis.retrieval import lexical_terms


def _terms(value: str) -> tuple[str, ...]:
    return lexical_terms(value)[:64]


def _contains_score(text: str, terms: tuple[str, ...]) -> float:
    available = set(lexical_terms(text))
    return float(sum(1 for term in terms if term in available))


def _centrality(graph: ProjectGraph) -> dict[str, float]:
    ids = {node.id for node in graph.nodes}
    if not ids:
        return {}
    outgoing: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        if edge.source_id in ids and edge.target_id in ids:
            outgoing[edge.source_id].add(edge.target_id)
    rank = {identifier: 1.0 / len(ids) for identifier in ids}
    damping = 0.85
    for _ in range(8):
        next_rank = {identifier: (1.0 - damping) / len(ids) for identifier in ids}
        dangling = sum(rank[node] for node in ids if not outgoing[node]) / len(ids)
        for identifier in ids:
            next_rank[identifier] += damping * dangling
        for source, targets in outgoing.items():
            if not targets:
                continue
            contribution = damping * rank[source] / len(targets)
            for target in targets:
                next_rank[target] += contribution
        rank = next_rank
    maximum = max(rank.values(), default=1.0)
    return {identifier: value / maximum for identifier, value in rank.items()}


def _adjacency(graph: ProjectGraph) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        result[edge.source_id].add(edge.target_id)
        result[edge.target_id].add(edge.source_id)
    return result


def _distances(adjacent: dict[str, set[str]], seeds: set[str], limit: int = 3) -> dict[str, int]:
    distances = {seed: 0 for seed in seeds}
    queue = deque(seeds)
    while queue:
        source = queue.popleft()
        distance = distances[source]
        if distance >= limit:
            continue
        for target in adjacent[source]:
            if target not in distances:
                distances[target] = distance + 1
                queue.append(target)
    return distances


@dataclass(frozen=True, slots=True)
class _Candidate:
    kind: str
    score: float
    value: object
    size: int


class ProjectContextBuilder:
    """Build project-root-isolated context without injecting an entire repository."""

    def __init__(
        self,
        root: Path,
        *,
        source_root: Path | None = None,
        git: GitService | None = None,
    ) -> None:
        self.git = git or LocalGitService()
        self.root = resolve_project_root(root)
        self.layout = ProjectLayout(self.root)
        self.manifest = load_manifest(self.layout)
        self.graph_engine = ProjectGraphEngine(
            self.root,
            source_root=source_root,
            git=self.git,
        )
        self.source_root = self.graph_engine.root
        self.memory = CuratedMemoryStore(self.layout)
        self.tasks = TaskCapsuleStore(self.layout)

    def build(self, task: str, max_chars: int | None = None) -> ProjectContextPack:
        return self.build_with_graph(task, max_chars)[0]

    def build_with_graph(
        self, task: str, max_chars: int | None = None
    ) -> tuple[ProjectContextPack, ProjectGraph]:
        if not task.strip() or len(task) > 10_000:
            raise InputError("Context task must contain 1..10000 characters")
        budget = max_chars if max_chars is not None else self._configured_budget()
        if not 1000 <= budget <= 200_000:
            raise InputError("Context budget must be between 1000 and 200000 characters")
        refreshed, status = self.graph_engine.refresh_with_status()
        dirty_paths = tuple(
            path
            for path in status.changed_paths
            if path != ".orqalis" and not path.startswith(".orqalis/")
        )
        terms = _terms(task)
        graph = refreshed.graph
        graph_items = self._rank_graph(graph, terms, set(dirty_paths))
        memory_items = self._rank_memory(terms, status.head)
        task_items = self._rank_tasks(terms)
        previews = tuple(
            memory_preview(
                item.record,
                MemoryRecordStatus(record=item.record, freshness=item.freshness),
                task,
                item.score,
            )
            for item in memory_items
        )

        project = self.manifest["project"]
        assert isinstance(project, dict)
        base = ProjectContextPack(
            task=task,
            project_id=str(project["id"]),
            project_name=str(project["name"]),
            branch=status.branch,
            head_commit=status.head,
            dirty_paths=dirty_paths,
            size_chars=0,
            max_chars=budget,
        )
        while len(base.model_dump_json()) > budget and base.dirty_paths:
            base = base.model_copy(
                update={
                    "dirty_paths": base.dirty_paths[:-1],
                    "truncated": True,
                }
            )
        base_size = len(base.model_dump_json())
        if base_size > budget:
            raise InputError(
                "Context task and required project metadata exceed the configured budget"
            )
        candidates = [
            *(
                _Candidate("graph", item.score, item, len(item.model_dump_json()))
                for item in graph_items
            ),
            *(
                _Candidate("memory", item.score + 0.5, item, len(item.model_dump_json()))
                for item in memory_items
            ),
            *(
                _Candidate("memory_preview", item.score + 0.5, item, len(item.model_dump_json()))
                for item in previews
            ),
            *(
                _Candidate("task", item.score, item, len(item.model_dump_json()))
                for item in task_items
            ),
        ]
        candidates.sort(key=lambda item: (-item.score, item.kind, item.size))
        selected_graph: list[GraphContextItem] = []
        selected_memory: list[MemoryContextItem] = []
        selected_previews: list[MemoryDiscoveryItem] = []
        selected_tasks: list[HistoricalTaskContext] = []
        size = base_size
        truncated = base.truncated
        for candidate in candidates:
            if candidate.kind == "memory_preview":
                assert isinstance(candidate.value, MemoryDiscoveryItem)
                if any(item.record.id == candidate.value.id for item in selected_memory):
                    continue
            if size + candidate.size > budget:
                truncated = True
                continue
            size += candidate.size
            if candidate.kind == "graph":
                assert isinstance(candidate.value, GraphContextItem)
                selected_graph.append(candidate.value)
            elif candidate.kind == "memory":
                assert isinstance(candidate.value, MemoryContextItem)
                selected_memory.append(candidate.value)
            elif candidate.kind == "memory_preview":
                assert isinstance(candidate.value, MemoryDiscoveryItem)
                selected_previews.append(candidate.value)
            else:
                assert isinstance(candidate.value, HistoricalTaskContext)
                selected_tasks.append(candidate.value)
        relevant = {
            item.node.file_path for item in selected_graph if item.node.file_path is not None
        }
        relevant.update(path for item in selected_memory for path in item.record.source.paths)
        decisions = tuple(
            item.record.id
            for item in selected_memory
            if item.record.category == MemoryCategory.DECISION
        )
        result = base.model_copy(
            update={
                "relevant_files": tuple(sorted(relevant)),
                "graph": tuple(selected_graph),
                "memory": tuple(selected_memory),
                "memory_discovery": tuple(selected_previews),
                "decisions": decisions,
                "related_tasks": tuple(selected_tasks),
                "size_chars": size,
                "truncated": truncated,
            }
        )
        # Model overhead changes slightly when selected arrays are populated. Remove the
        # lowest-ranked tail until the serialized contract itself fits the hard budget.
        return self._fit(result), graph

    def _configured_budget(self) -> int:
        if not self.layout.config.is_file():
            return 20_000
        config = read_json_object(self.layout.config)
        context = config.get("context")
        value = context.get("max_chars") if isinstance(context, dict) else None
        return value if isinstance(value, int) and not isinstance(value, bool) else 20_000

    def _rank_graph(
        self, graph: ProjectGraph, terms: tuple[str, ...], dirty: set[str]
    ) -> tuple[GraphContextItem, ...]:
        centrality = _centrality(graph)
        # Many symbols share a source path/name. Reuse exact lexical scores only
        # within this query; later requests always observe newly read source.
        text_scores: dict[str, float] = {}

        def text_score(text: str) -> float:
            if text not in text_scores:
                text_scores[text] = _contains_score(text, terms)
            return text_scores[text]

        lexical: dict[str, float] = {}
        lexical_reasons: dict[str, tuple[str, ...]] = {}
        for node in graph.nodes:
            # Call occurrences are available through explicit reference tools. They are
            # evidence for callers, not additional declarations or lexical context seeds.
            if node.kind == GraphNodeKind.REFERENCE:
                continue
            name = text_score(node.name) * 4.0
            path = text_score(node.file_path or "") * 2.0
            lexical[node.id] = name + path
            lexical_reasons[node.id] = tuple(
                reason for reason, signal in (("name", name), ("path", path)) if signal > 0
            )
        seeds = {identifier for identifier, score in lexical.items() if score > 0}
        adjacent = _adjacency(graph)
        distances = _distances(adjacent, seeds)
        names = {node.id: node.name for node in graph.nodes}
        ranked = []
        for node in graph.nodes:
            if node.kind == GraphNodeKind.REFERENCE:
                continue
            distance = distances.get(node.id)
            proximity = 2.0 / (distance + 1) if distance is not None else 0.0
            recent = 1.5 if node.file_path in dirty else 0.0
            score = lexical[node.id] + centrality.get(node.id, 0.0) + proximity + recent
            if score <= 0:
                continue
            neighbors = tuple(
                nsmallest(20, (names[item] for item in adjacent[node.id] if item in names))
            )
            ranked.append(
                GraphContextItem(
                    node=node,
                    score=score,
                    distance=distance,
                    neighbors=neighbors,
                    match_reasons=lexical_reasons[node.id]
                    + tuple(
                        reason
                        for reason, present in (
                            ("dependency", distance is not None and distance > 0),
                            ("changed_file", recent > 0),
                            ("centrality", centrality.get(node.id, 0.0) > 0),
                        )
                        if present
                    ),
                    orientation_only=not (
                        lexical[node.id] > 0 or distance is not None or recent > 0
                    ),
                )
            )
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.node.name)))

    def _rank_memory(
        self, terms: tuple[str, ...], current_commit: str
    ) -> tuple[MemoryContextItem, ...]:
        scored = []
        for record in self.memory.list():
            score = _contains_score(
                f"{record.title} {record.category.value} {record.summary or ''} {record.content}",
                terms,
            )
            if score > 0:
                scored.append((record, score))
        statuses = self.memory.statuses(
            tuple(record for record, _ in scored),
            current_commit,
            source_root=self.source_root,
        )
        values = []
        for (record, score), status in zip(scored, statuses, strict=True):
            if status.lifecycle != MemoryLifecycle.ACTIVE:
                continue
            if status.freshness == MemoryFreshness.STALE:
                score *= 0.5
            values.append(MemoryContextItem(record=record, freshness=status.freshness, score=score))
        return tuple(sorted(values, key=lambda item: (-item.score, item.record.title)))

    def _rank_tasks(self, terms: tuple[str, ...]) -> tuple[HistoricalTaskContext, ...]:
        # Canonical summaries are checked, with no unchanged index replacement.
        entries = self.tasks.read_index()
        values = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            title, identifier = entry.get("title"), entry.get("id")
            if not isinstance(title, str) or not isinstance(identifier, str):
                continue
            completed_at = entry.get("completed_at")
            if not isinstance(completed_at, str):
                continue
            score = _contains_score(title, terms)
            if score <= 0:
                continue
            summary_path = self.layout.task(identifier) / "final" / "summary.md"
            summary = None
            if summary_path.is_file():
                summary = ensure_no_filesystem_links(summary_path).read_text(encoding="utf-8")[
                    :4000
                ]
            values.append(
                HistoricalTaskContext(
                    id=identifier,
                    title=title,
                    status=str(entry.get("status", "UNKNOWN")),
                    branch=entry.get("branch") if isinstance(entry.get("branch"), str) else None,
                    completed_at=completed_at,
                    summary=summary,
                    score=score,
                )
            )
        return tuple(sorted(values, key=lambda item: (-item.score, item.id)))

    @staticmethod
    def _fit(pack: ProjectContextPack) -> ProjectContextPack:
        graph = list(pack.graph)
        memory = list(pack.memory)
        previews = list(pack.memory_discovery)
        tasks = list(pack.related_tasks)
        while len(pack.model_dump_json()) > pack.max_chars and (
            graph or memory or previews or tasks
        ):
            tails = []
            if graph:
                tails.append((graph[-1].score, "graph"))
            if memory:
                tails.append((memory[-1].score, "memory"))
            if previews:
                tails.append((previews[-1].score, "preview"))
            if tasks:
                tails.append((tasks[-1].score, "task"))
            _, kind = min(tails)
            if kind == "graph":
                graph.pop()
            elif kind == "memory":
                memory.pop()
            elif kind == "preview":
                previews.pop()
            else:
                tasks.pop()
            relevant = {item.node.file_path for item in graph if item.node.file_path is not None}
            relevant.update(path for item in memory for path in item.record.source.paths)
            decisions = tuple(
                item.record.id for item in memory if item.record.category == MemoryCategory.DECISION
            )
            pack = pack.model_copy(
                update={
                    "graph": tuple(graph),
                    "memory": tuple(memory),
                    "memory_discovery": tuple(previews),
                    "relevant_files": tuple(sorted(relevant)),
                    "decisions": decisions,
                    "related_tasks": tuple(tasks),
                    "truncated": True,
                }
            )
        for _ in range(4):
            actual = len(pack.model_dump_json())
            if pack.size_chars == actual:
                break
            pack = pack.model_copy(update={"size_chars": actual})
        if len(pack.model_dump_json()) > pack.max_chars:
            raise InputError("Required project context metadata exceed the configured budget")
        return pack
