"""Bounded metadata discovery and explicit reads of canonical project memory.

Inspired by Serena memory references and Letta tiered memory; this implementation
uses Orqalis IDs, provenance and filesystem authority and does not copy their code.
"""

from typing import cast

from pydantic import Field

from orqalis.domain.base import Contract
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.memory.curated import (
    CuratedMemoryStore,
    DurableMemoryRecord,
    MemoryCategory,
    MemoryFreshness,
    MemoryLifecycle,
    MemoryProvenance,
    MemoryRecordStatus,
    _parse_record,
)
from orqalis.persistence.filesystem.locking import FileLock
from orqalis.retrieval import lexical_terms


class MemoryDiscoveryItem(Contract):
    id: str
    title: str
    category: MemoryCategory
    preview: str
    content_chars: int = Field(ge=0)
    references: tuple[str, ...] = ()
    reference_count: int = Field(ge=0)
    freshness: MemoryFreshness
    lifecycle: MemoryLifecycle
    superseded_by: str | None = None
    score: float = Field(ge=0)
    matched_on: tuple[str, ...] = ()


class MemoryDiscoveryResult(Contract):
    items: tuple[MemoryDiscoveryItem, ...] = ()
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)
    truncated: bool = False


class MemoryReadPage(Contract):
    item: MemoryDiscoveryItem
    source: MemoryProvenance
    verified_commit: str | None
    content: str
    offset: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    references: tuple[str, ...] = ()
    size_chars: int = Field(ge=0)
    max_chars: int = Field(ge=1000)


class MemoryIntegrityIssue(Contract):
    kind: str
    record_id: str | None = None
    target: str | None = None


class MemoryIntegrityReport(Contract):
    ok: bool
    records_checked: int = Field(ge=0)
    references_checked: int = Field(ge=0)
    issues: tuple[MemoryIntegrityIssue, ...] = ()
    truncated: bool = False


def memory_preview(
    record: DurableMemoryRecord,
    status: MemoryRecordStatus,
    query: str = "",
    score: float = 0,
) -> MemoryDiscoveryItem:
    terms = set(lexical_terms(query))
    fields = {
        "title": record.title,
        "category": record.category.value,
        "summary": record.summary or "",
        "body": record.content,
    }
    matched = tuple(
        name for name, text in fields.items() if terms.intersection(lexical_terms(text))
    )
    preview = " ".join((record.summary or record.content).split())[:160]
    return MemoryDiscoveryItem(
        id=record.id,
        title=record.title,
        category=record.category,
        preview=preview,
        content_chars=len(record.content),
        references=record.references[:4],
        reference_count=len(record.references),
        freshness=status.freshness,
        lifecycle=status.lifecycle,
        superseded_by=status.superseded_by,
        score=score,
        matched_on=matched,
    )


def _budget(max_chars: int) -> None:
    if not 1000 <= max_chars <= 200_000:
        raise InputError("Memory response budget must be between 1000 and 200000 characters")


def _size[T: MemoryDiscoveryResult | MemoryReadPage](value: T) -> T:
    for _ in range(4):
        actual = len(value.model_dump_json())
        if actual == value.size_chars:
            return value
        value = cast(T, value.model_copy(update={"size_chars": actual}))
    return value


class MemoryNavigationService:
    def __init__(self, store: CuratedMemoryStore) -> None:
        self.store = store

    def discover(
        self,
        query: str,
        *,
        current_commit: str | None = None,
        limit: int = 10,
        max_chars: int = 6000,
    ) -> MemoryDiscoveryResult:
        _budget(max_chars)
        if len(query) > 10_000 or not 1 <= limit <= 100:
            raise InputError(
                "Memory discovery requires limit 1..100 and query up to 10000 characters"
            )
        records = self.store.search(query, limit + 1)
        selected: list[MemoryDiscoveryItem] = []
        truncated = len(records) > limit
        terms = set(lexical_terms(query))
        statuses = self.store.statuses(records[:limit], current_commit)
        for record, status in zip(records[:limit], statuses, strict=True):
            if status.lifecycle != MemoryLifecycle.ACTIVE:
                continue
            score = float(
                len(
                    terms.intersection(
                        lexical_terms(
                            f"{record.title} {record.category} "
                            f"{record.summary or ''} {record.content}"
                        )
                    )
                )
            )
            item = memory_preview(record, status, query, score)
            candidate = _size(
                MemoryDiscoveryResult(
                    items=(*selected, item),
                    size_chars=0,
                    max_chars=max_chars,
                    truncated=truncated,
                )
            )
            if candidate.size_chars <= max_chars:
                selected.append(item)
            else:
                truncated = True
        result = _size(
            MemoryDiscoveryResult(
                items=tuple(selected),
                size_chars=0,
                max_chars=max_chars,
                truncated=truncated,
            )
        )
        return result

    def read(
        self,
        record_id: str,
        *,
        current_commit: str | None = None,
        offset: int = 0,
        max_chars: int = 10000,
    ) -> MemoryReadPage:
        _budget(max_chars)
        record = self.store.get(record_id)
        if not 0 <= offset <= len(record.content):
            raise InputError("Memory offset is outside the record body")
        status = self.store.status(record, current_commit)
        item = memory_preview(record, status)

        def page(end: int) -> MemoryReadPage:
            return _size(
                MemoryReadPage(
                    item=item,
                    source=record.source,
                    verified_commit=record.verified_commit,
                    content=record.content[offset:end],
                    offset=offset,
                    next_offset=end if end < len(record.content) else None,
                    references=record.references,
                    size_chars=0,
                    max_chars=max_chars,
                )
            )

        best = page(offset)
        if best.size_chars > max_chars:
            raise InputError(
                "Memory provenance metadata exceeds response budget; increase max_chars"
            )
        # A JSON page cannot hold more source characters than its total budget.
        # Bound trial slices before serializing a long record.
        low, high = offset, min(len(record.content), offset + max_chars)
        while low <= high:
            middle = (low + high) // 2
            candidate = page(middle)
            if candidate.size_chars <= max_chars:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        if best.next_offset == offset and offset < len(record.content):
            raise InputError("Memory response budget has no space for content; increase max_chars")
        return best

    def check(self, *, max_issues: int = 100) -> MemoryIntegrityReport:
        if not 1 <= max_issues <= 1000:
            raise InputError("Memory integrity issue limit must be between 1 and 1000")
        with FileLock(self.store.lock_path):
            return self._check(max_issues)

    def _check(self, max_issues: int) -> MemoryIntegrityReport:
        issues: list[MemoryIntegrityIssue] = []
        records: dict[str, DurableMemoryRecord] = {}
        paths = sorted(self.store.records.glob("MEM-*.md"))
        for path in paths:
            try:
                record = _parse_record(path)
                self.store._validate_sources(record)
                if record.id != path.stem or record.id in records:
                    issues.append(
                        MemoryIntegrityIssue(kind="identity_mismatch", record_id=record.id)
                    )
                records[record.id] = record
            except (OSError, ValueError, ConflictError, PolicyDeniedError):
                issues.append(MemoryIntegrityIssue(kind="invalid_record"))
        try:
            self.store.list(include_inactive=True)
        except (OSError, ValueError, ConflictError, PolicyDeniedError):
            issues.append(MemoryIntegrityIssue(kind="invalid_lifecycle_or_record"))
        count = 0
        for record in records.values():
            for reference in record.references:
                count += 1
                if reference not in records:
                    issues.append(
                        MemoryIntegrityIssue(
                            kind="missing_reference", record_id=record.id, target=reference
                        )
                    )
        # Iterative DFS handles long manually authored reference chains without
        # recursion limits. References are data; never traverse other directories.
        visited: set[str] = set()
        active: set[str] = set()
        for root in sorted(records):
            stack: list[tuple[str, bool]] = [(root, False)]
            while stack:
                current, exiting = stack.pop()
                if exiting:
                    active.discard(current)
                    continue
                if current in visited:
                    continue
                visited.add(current)
                active.add(current)
                stack.append((current, True))
                for target in reversed(records[current].references):
                    if target in active:
                        issues.append(
                            MemoryIntegrityIssue(
                                kind="reference_cycle", record_id=current, target=target
                            )
                        )
                    elif target in records and target not in visited:
                        stack.append((target, False))
        return MemoryIntegrityReport(
            ok=not issues,
            records_checked=len(paths),
            references_checked=count,
            issues=tuple(issues[:max_issues]),
            truncated=len(issues) > max_issues,
        )
