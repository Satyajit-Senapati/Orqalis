"""Rank graph, curated memory, task history, and Git state into a small pack."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from orqalis.context.models import (
    GraphContextItem,
    HistoricalTaskContext,
    MemoryContextItem,
    ProjectContextPack,
)
from orqalis.domain.errors import InputError, PolicyDeniedError
from orqalis.git.contracts import GitService
from orqalis.git.service import LocalGitService
from orqalis.graph import ProjectGraph, ProjectGraphEngine
from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryFreshness
from orqalis.persistence.filesystem.io import ensure_no_filesystem_links, read_json_object
from orqalis.persistence.filesystem.layout import ProjectLayout, load_manifest, resolve_project_root
from orqalis.persistence.filesystem.task_store import TaskCapsuleStore


def _terms(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9_]{2,}", value.casefold())))[:64]


def _contains_score(text: str, terms: tuple[str, ...]) -> float:
    lowered = text.casefold()
    return float(sum(1 for term in terms if term in lowered))


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


def _distances(graph: ProjectGraph, seeds: set[str], limit: int = 3) -> dict[str, int]:
    adjacent = _adjacency(graph)
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
        self.source_root = self.git.root(source_root or self.root)
        if self.git.common_directory(self.root) != self.git.common_directory(self.source_root):
            raise PolicyDeniedError(
                "Context source does not belong to the canonical project repository"
            )
        self.layout = ProjectLayout(self.root)
        self.manifest = load_manifest(self.layout)
        self.graph_engine = ProjectGraphEngine(
            self.root,
            source_root=self.source_root,
            git=self.git,
        )
        self.memory = CuratedMemoryStore(self.layout)
        self.tasks = TaskCapsuleStore(self.layout)

    def build(self, task: str, max_chars: int | None = None) -> ProjectContextPack:
        if not task.strip() or len(task) > 10_000:
            raise InputError("Context task must contain 1..10000 characters")
        budget = max_chars if max_chars is not None else self._configured_budget()
        if not 1000 <= budget <= 200_000:
            raise InputError("Context budget must be between 1000 and 200000 characters")
        status = self.git.status(self.source_root)
        dirty_paths = tuple(
            path
            for path in status.changed_paths
            if path != ".orqalis" and not path.startswith(".orqalis/")
        )
        terms = _terms(task)
        graph = self.graph_engine.refresh().graph
        graph_items = self._rank_graph(graph, terms, set(dirty_paths))
        memory_items = self._rank_memory(terms, status.head)
        task_items = self._rank_tasks(terms)

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
                _Candidate("task", item.score, item, len(item.model_dump_json()))
                for item in task_items
            ),
        ]
        candidates.sort(key=lambda item: (-item.score, item.kind, item.size))
        selected_graph: list[GraphContextItem] = []
        selected_memory: list[MemoryContextItem] = []
        selected_tasks: list[HistoricalTaskContext] = []
        size = base_size
        truncated = base.truncated
        for candidate in candidates:
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
                "decisions": decisions,
                "related_tasks": tuple(selected_tasks),
                "size_chars": size,
                "truncated": truncated,
            }
        )
        # Model overhead changes slightly when selected arrays are populated. Remove the
        # lowest-ranked tail until the serialized contract itself fits the hard budget.
        return self._fit(result)

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
        lexical: dict[str, float] = {}
        for node in graph.nodes:
            name = _contains_score(node.name, terms) * 4.0
            path = _contains_score(node.file_path or "", terms) * 2.0
            lexical[node.id] = name + path
        seeds = {identifier for identifier, score in lexical.items() if score > 0}
        distances = _distances(graph, seeds)
        adjacent = _adjacency(graph)
        names = {node.id: node.name for node in graph.nodes}
        ranked = []
        for node in graph.nodes:
            distance = distances.get(node.id)
            proximity = 2.0 / (distance + 1) if distance is not None else 0.0
            recent = 1.5 if node.file_path in dirty else 0.0
            score = lexical[node.id] + centrality.get(node.id, 0.0) + proximity + recent
            if score <= 0:
                continue
            neighbor_names = sorted(names[item] for item in adjacent[node.id] if item in names)
            neighbors = tuple(neighbor_names[:20])
            ranked.append(
                GraphContextItem(
                    node=node,
                    score=score,
                    distance=distance,
                    neighbors=neighbors,
                )
            )
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.node.name)))

    def _rank_memory(
        self, terms: tuple[str, ...], current_commit: str
    ) -> tuple[MemoryContextItem, ...]:
        values = []
        for record in self.memory.list():
            score = _contains_score(
                f"{record.title} {record.category.value} {record.content}", terms
            )
            if score <= 0:
                continue
            status = self.memory.status(record, current_commit, source_root=self.source_root)
            if status.freshness == MemoryFreshness.STALE:
                score *= 0.5
            values.append(MemoryContextItem(record=record, freshness=status.freshness, score=score))
        return tuple(sorted(values, key=lambda item: (-item.score, item.record.title)))

    def _rank_tasks(self, terms: tuple[str, ...]) -> tuple[HistoricalTaskContext, ...]:
        index = self.layout.tasks / "index.json"
        # Task history is canonical in capsule directories; never trust a stale or
        # hand-edited derived index over those source documents.
        self.tasks.rebuild_index()
        document = read_json_object(index)
        entries = document.get("tasks")
        if not isinstance(entries, list):
            return ()
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
        tasks = list(pack.related_tasks)
        while len(pack.model_dump_json()) > pack.max_chars and (graph or memory or tasks):
            tails = []
            if graph:
                tails.append((graph[-1].score, "graph"))
            if memory:
                tails.append((memory[-1].score, "memory"))
            if tasks:
                tails.append((tasks[-1].score, "task"))
            _, kind = min(tails)
            if kind == "graph":
                graph.pop()
            elif kind == "memory":
                memory.pop()
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
