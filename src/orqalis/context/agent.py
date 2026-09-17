"""Adapter from the local-first project pack to the stable agent context contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid5

from orqalis.context.models import ProjectContextPack
from orqalis.domain.errors import ConflictError
from orqalis.domain.memory import (
    ContextPack,
    MemoryHealth,
    MemoryItem,
    MemoryMatch,
    MemorySource,
    MemoryStatus,
    MemoryType,
)
from orqalis.domain.project import Project
from orqalis.memory.curated import MemoryCategory, MemoryFreshness

_CATEGORY_TYPES = {
    MemoryCategory.PRODUCT: MemoryType.DOMAIN,
    MemoryCategory.ARCHITECTURE: MemoryType.ARCHITECTURE,
    MemoryCategory.TECHNOLOGY: MemoryType.ARCHITECTURE,
    MemoryCategory.CONVENTIONS: MemoryType.CONVENTION,
    MemoryCategory.DOMAIN: MemoryType.DOMAIN,
    MemoryCategory.WORKFLOWS: MemoryType.CONVENTION,
    MemoryCategory.TESTING: MemoryType.CONVENTION,
    MemoryCategory.PITFALLS: MemoryType.KNOWN_ISSUE,
    MemoryCategory.MODULE: MemoryType.ARCHITECTURE,
    MemoryCategory.DECISION: MemoryType.DECISION,
}


@dataclass(frozen=True, slots=True)
class _Candidate:
    score: float
    match: MemoryMatch


def _score(value: float) -> float:
    return 0.0 if value <= 0 else min(1.0, value / (value + 1.0))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source(
    project: Project,
    identity: str,
    source_type: str,
    source_ref: str,
    content_hash: str,
    commit: str,
) -> MemorySource:
    return MemorySource(
        id=uuid5(project.id, f"context-source:{identity}:{source_type}:{source_ref}"),
        memory_item_id=uuid5(project.id, f"context-item:{identity}"),
        source_type=source_type,
        source_ref=source_ref,
        content_hash=content_hash,
        commit_sha=commit,
    )


def agent_context(project: Project, pack: ProjectContextPack) -> ContextPack:
    """Translate a bounded filesystem pack without re-scanning the repository."""

    if pack.project_id != str(project.id):
        raise ConflictError("Project Context Pack belongs to another project")
    candidates: list[_Candidate] = []
    stale_paths: set[str] = set()

    for memory_value in pack.memory:
        record = memory_value.record
        identity = f"memory:{record.id}"
        commit = record.verified_commit or pack.head_commit
        item = MemoryItem(
            id=uuid5(project.id, f"context-item:{identity}"),
            created_at=record.last_verified_at,
            project_id=project.id,
            type=_CATEGORY_TYPES[record.category],
            title=record.title,
            content=record.content,
            confidence=record.confidence,
            status=(
                MemoryStatus.STALE
                if memory_value.freshness == MemoryFreshness.STALE
                else MemoryStatus.ACTIVE
            ),
            source_commit=commit,
            last_verified_at=record.last_verified_at,
        )
        sources = tuple(
            _source(
                project,
                identity,
                record.source.type,
                path,
                record.source.content_hashes.get(path, _digest(record.content)),
                commit,
            )
            for path in record.source.paths
        ) or (
            _source(
                project,
                identity,
                record.source.type,
                record.id,
                _digest(record.content),
                commit,
            ),
        )
        if memory_value.freshness == MemoryFreshness.STALE:
            stale_paths.update(record.source.paths)
        candidates.append(
            _Candidate(
                memory_value.score + 0.5,
                MemoryMatch(
                    item=item,
                    sources=sources,
                    score=_score(memory_value.score),
                ),
            )
        )

    for graph_value in pack.graph:
        node = graph_value.node
        identity = f"graph:{node.id}"
        location = node.file_path or "repository"
        if node.line_start is not None:
            location = f"{location}:{node.line_start}-{node.line_end}"
        neighbors = ", ".join(graph_value.neighbors) if graph_value.neighbors else "none selected"
        content = f"{node.kind} {node.name} at {location}. Ranked graph neighbors: {neighbors}."
        item = MemoryItem(
            id=uuid5(project.id, f"context-item:{identity}"),
            project_id=project.id,
            type=MemoryType.REPOSITORY_MAP,
            title=f"{node.kind}: {node.name}",
            content=content,
            confidence=1.0,
            source_commit=pack.head_commit,
        )
        sources = (
            _source(
                project,
                identity,
                "file" if node.file_path else "repository_graph",
                node.file_path or node.id,
                node.source_hash or _digest(content),
                pack.head_commit,
            ),
        )
        candidates.append(
            _Candidate(
                graph_value.score,
                MemoryMatch(
                    item=item,
                    sources=sources,
                    score=_score(graph_value.score),
                ),
            )
        )

    for task_value in pack.related_tasks:
        identity = f"task:{task_value.id}"
        content = task_value.summary or (
            f"Related historical task {task_value.id} ended as {task_value.status}."
        )
        item = MemoryItem(
            id=uuid5(project.id, f"context-item:{identity}"),
            project_id=project.id,
            type=MemoryType.PREVIOUS_RUN,
            title=f"{task_value.id}: {task_value.title}",
            content=content,
            confidence=1.0,
            source_commit=pack.head_commit,
        )
        sources = (
            _source(
                project,
                identity,
                "task_capsule",
                task_value.id,
                _digest(content),
                pack.head_commit,
            ),
        )
        candidates.append(
            _Candidate(
                task_value.score,
                MemoryMatch(
                    item=item,
                    sources=sources,
                    score=_score(task_value.score),
                ),
            )
        )

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.match.item.title))
    selected: list[MemoryMatch] = []
    size = 0
    for candidate in candidates:
        candidate_size = len(candidate.match.model_dump_json())
        if size + candidate_size > pack.max_chars:
            continue
        selected.append(candidate.match)
        size += candidate_size

    relevant = set(pack.relevant_files)
    targeted = stale_paths | (relevant & set(pack.dirty_paths))
    confidence = max(
        (match.score * match.item.confidence for match in selected),
        default=0.0,
    )
    fresh = not stale_paths and not pack.dirty_paths
    requires_inspection = pack.truncated or not fresh or confidence < 0.7
    return ContextPack(
        project_id=project.id,
        task=pack.task,
        items=tuple(selected),
        relevant_files=tuple(sorted(relevant)),
        freshness=MemoryHealth(
            project_id=project.id,
            indexed_commit=pack.head_commit,
            current_commit=pack.head_commit,
            fresh=fresh,
            dirty_paths=pack.dirty_paths,
            active_items=len(selected),
        ),
        confidence=confidence,
        targeted_inspection_paths=tuple(sorted(targeted)),
        requires_inspection=requires_inspection,
        size_chars=size,
    )


__all__ = ["agent_context"]
