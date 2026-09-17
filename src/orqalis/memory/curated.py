"""Human-readable, project-local curated memory.

Repository graph data and task execution history deliberately live elsewhere.  This
module owns only durable knowledge that remains useful across tasks.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from orqalis.domain.base import Contract, utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.git.service import validate_relative_path
from orqalis.persistence.filesystem.io import (
    atomic_write_bytes,
    atomic_write_json,
    ensure_no_filesystem_links,
    read_json_object,
)
from orqalis.persistence.filesystem.layout import ProjectLayout
from orqalis.persistence.filesystem.locking import FileLock
from orqalis.security.redaction import safe_diagnostic

MEMORY_SCHEMA_VERSION = 1
_MEMORY_ID = re.compile(r"^MEM-[0-9]{8}-[0-9]{4}$")
_PROPOSAL_ID = re.compile(r"^MEM-PROP-[0-9]{8}-[0-9]{4}$")
_TASK_ID = re.compile(r"^ORQ-[0-9]{8}-[0-9]{4}$")


class MemoryCategory(StrEnum):
    PRODUCT = "product"
    ARCHITECTURE = "architecture"
    TECHNOLOGY = "technology"
    CONVENTIONS = "conventions"
    DOMAIN = "domain"
    WORKFLOWS = "workflows"
    TESTING = "testing"
    PITFALLS = "pitfalls"
    MODULE = "module"
    DECISION = "decision"


class DurableUpdatePolicy(StrEnum):
    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"


class MemoryFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"


class MemoryProvenance(Contract):
    type: Literal["repository", "task", "user"]
    paths: tuple[str, ...] = ()
    content_hashes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_repository_paths(self) -> Self:
        try:
            for path in self.paths:
                validate_relative_path(path)
            for path, digest in self.content_hashes.items():
                validate_relative_path(path)
                if path not in self.paths or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                    raise ValueError("Memory provenance hashes must match declared paths")
        except PolicyDeniedError as exc:
            raise ValueError("Memory provenance paths must be repository-relative") from exc
        return self


class DurableMemoryRecord(Contract):
    schema_version: int = MEMORY_SCHEMA_VERSION
    id: str = Field(pattern=r"^MEM-[0-9]{8}-[0-9]{4}$")
    category: MemoryCategory
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    source: MemoryProvenance
    verified_commit: str | None = None
    introduced_by_task: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    last_verified_at: AwareDatetime = Field(default_factory=utc_now)


class MemoryRecordStatus(Contract):
    record: DurableMemoryRecord
    freshness: MemoryFreshness
    changed_sources: tuple[str, ...] = ()


class MemoryRevalidationResult(Contract):
    """Outcome of an explicit, selective provenance revalidation."""

    current_commit: str = Field(min_length=1)
    statuses: tuple[MemoryRecordStatus, ...]
    revalidated_ids: tuple[str, ...] = ()
    unchanged_ids: tuple[str, ...] = ()
    stale_ids: tuple[str, ...] = ()


class MemoryProposal(Contract):
    schema_version: int = MEMORY_SCHEMA_VERSION
    id: str = Field(pattern=r"^MEM-PROP-[0-9]{8}-[0-9]{4}$")
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    policy: DurableUpdatePolicy
    record: DurableMemoryRecord
    rationale: str = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    created_at: AwareDatetime = Field(default_factory=utc_now)
    reviewed_at: AwareDatetime | None = None
    review_reason: str | None = None


_BASELINE = (
    MemoryCategory.PRODUCT,
    MemoryCategory.ARCHITECTURE,
    MemoryCategory.TECHNOLOGY,
    MemoryCategory.CONVENTIONS,
    MemoryCategory.DOMAIN,
    MemoryCategory.WORKFLOWS,
    MemoryCategory.TESTING,
    MemoryCategory.PITFALLS,
)


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.casefold()).strip("-.")
    if not normalized or normalized in {".", ".."}:
        raise PolicyDeniedError("Memory title cannot produce an unsafe path")
    return normalized[:100]


def _require_id(value: str, pattern: re.Pattern[str], label: str) -> str:
    if pattern.fullmatch(value) is None:
        raise PolicyDeniedError(f"Invalid {label}")
    return value


def _hash(path: Path) -> str | None:
    path = ensure_no_filesystem_links(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_path(root: Path, relative: str) -> Path:
    try:
        validate_relative_path(relative)
    except PolicyDeniedError as exc:
        raise PolicyDeniedError("Memory provenance path is unsafe") from exc
    resolved_root = root.resolve(strict=True)
    candidate = ensure_no_filesystem_links(resolved_root.joinpath(*PurePosixPath(relative).parts))
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(resolved_root):
        raise PolicyDeniedError("Memory provenance path escapes the project root")
    return candidate


def _ensure_secret_safe(*values: str) -> None:
    for value in values:
        if safe_diagnostic(value) != value:
            raise PolicyDeniedError("Durable project memory cannot contain credentials or secrets")


def _frontmatter(record: DurableMemoryRecord) -> bytes:
    metadata = record.model_dump(mode="json", exclude={"content"})
    payload = json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False)
    return f"---\n{payload}\n---\n\n# {record.title}\n\n{record.content.rstrip()}\n".encode()


def _parse_record(path: Path) -> DurableMemoryRecord:
    text = ensure_no_filesystem_links(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Invalid memory frontmatter: {path.name}")
    try:
        raw, body = text[4:].split("\n---\n", 1)
        metadata = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid memory frontmatter: {path.name}") from exc
    title = str(metadata.get("title", ""))
    content = body.strip()
    heading = f"# {title}"
    if content.startswith(heading):
        content = content[len(heading) :].strip()
    return DurableMemoryRecord.model_validate({**metadata, "content": content})


class CuratedMemoryStore:
    """Project-root-bound durable memory with reviewable promotion."""

    def __init__(self, layout: ProjectLayout) -> None:
        self.layout = layout
        self.records = layout.contained(layout.memory / "records")
        self.staging = layout.contained(layout.memory / "staging")
        self.history = layout.contained(layout.memory / "history")
        self.reservations = layout.contained(layout.runtime / "sessions" / "memory-ids")
        self.lock_path = layout.lock("memory")

    def initialize(self) -> None:
        self.layout.memory.mkdir(parents=True, exist_ok=True)
        for category in _BASELINE:
            path = self.layout.memory / f"{category.value}.md"
            if not path.exists():
                heading = category.value.replace("-", " ").title()
                atomic_write_bytes(
                    path,
                    (
                        f"# {heading}\n\n"
                        "Durable project knowledge in this category is curated by Orqalis. "
                        "Source-derived graph facts and task execution state are "
                        "stored separately.\n"
                    ).encode(),
                )

    def configured_policy(self) -> DurableUpdatePolicy:
        """Read the repository's durable-memory review policy."""

        try:
            config = read_json_object(self.layout.config)
            memory = config.get("memory")
            value = memory.get("durable_updates") if isinstance(memory, dict) else None
            if not isinstance(value, str):
                raise ValueError("durable_updates must be text")
            return DurableUpdatePolicy(value)
        except (OSError, ValueError) as exc:
            raise ConflictError("Project durable-memory policy is invalid") from exc

    def _next_id(self, prefix: str, at: datetime | None = None) -> str:
        stamp = (at or utc_now()).strftime("%Y%m%d")
        pattern = re.compile(rf"^{re.escape(prefix)}-{stamp}-([0-9]{{4}})$")
        roots = (
            (self.records, True),
            (self.staging, False),
            (self.history, False),
            (self.reservations, True),
        )
        used: set[int] = set()
        for root, files in roots:
            if not root.is_dir():
                continue
            for path in root.iterdir():
                name = path.stem if files and path.is_file() else path.name
                match = pattern.match(name)
                if match:
                    used.add(int(match.group(1)))
        if prefix == "MEM":
            for root in (self.staging, self.history):
                if not root.is_dir():
                    continue
                for path in root.glob("MEM-PROP-*/proposal.yaml"):
                    try:
                        document = read_json_object(path)
                    except (OSError, ValueError):
                        continue
                    record = document.get("record")
                    identifier = record.get("id") if isinstance(record, dict) else None
                    match = pattern.match(identifier) if isinstance(identifier, str) else None
                    if match:
                        used.add(int(match.group(1)))
        try:
            value = next(number for number in range(1, 10_000) if number not in used)
        except StopIteration as exc:
            raise ConflictError(f"No {prefix} identifiers remain for {stamp}") from exc
        return f"{prefix}-{stamp}-{value:04d}"

    def new_record(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        source: MemoryProvenance,
        *,
        verified_commit: str | None = None,
        introduced_by_task: str | None = None,
        confidence: float = 1.0,
    ) -> DurableMemoryRecord:
        with FileLock(self.lock_path):
            identifier = self._next_id("MEM")
            self.reservations.mkdir(parents=True, exist_ok=True)
            atomic_write_json(
                self.reservations / f"{identifier}.json",
                {"schema_version": MEMORY_SCHEMA_VERSION, "id": identifier},
            )
        return DurableMemoryRecord(
            id=identifier,
            category=category,
            title=title,
            content=content,
            source=source,
            verified_commit=verified_commit,
            introduced_by_task=introduced_by_task,
            confidence=confidence,
        )

    def save(self, record: DurableMemoryRecord) -> Path:
        _ensure_secret_safe(record.title, record.content, record.model_dump_json())
        self._validate_sources(record)
        self.initialize()
        with FileLock(self.lock_path):
            self.records.mkdir(parents=True, exist_ok=True)
            path = self.records / f"{record.id}.md"
            if path.is_file():
                if _parse_record(path) != record:
                    raise ConflictError("Memory identity already exists")
                return path
            atomic_write_bytes(path, _frontmatter(record))
            return path

    def get(self, record_id: str) -> DurableMemoryRecord:
        path = self.records / f"{_require_id(record_id, _MEMORY_ID, 'memory ID')}.md"
        if not path.is_file():
            raise NotFoundError("Memory record not found")
        record = _parse_record(path)
        self._validate_sources(record)
        return record

    def list(self) -> tuple[DurableMemoryRecord, ...]:
        if not self.records.is_dir():
            return ()
        records = tuple(_parse_record(path) for path in sorted(self.records.glob("MEM-*.md")))
        for record in records:
            self._validate_sources(record)
        return records

    def search(self, query: str, limit: int = 10) -> tuple[DurableMemoryRecord, ...]:
        terms = tuple(dict.fromkeys(re.findall(r"[a-z0-9_]{2,}", query.casefold())))
        scored = []
        for record in self.list():
            text = f"{record.title} {record.category} {record.content}".casefold()
            score = sum(term in text for term in terms)
            if score or not terms:
                scored.append((score, record.title.casefold(), record))
        scored.sort(key=lambda item: (-item[0], item[1], item[2].id))
        return tuple(item[2] for item in scored[:limit])

    def status(
        self,
        record: DurableMemoryRecord,
        current_commit: str | None,
        *,
        source_root: Path | None = None,
    ) -> MemoryRecordStatus:
        self._validate_sources(record)
        inspected_root = source_root or self.layout.root
        changed: list[str] = []
        for relative in record.source.paths:
            expected = record.source.content_hashes.get(relative)
            actual = _hash(_source_path(inspected_root, relative))
            if expected is not None and actual != expected:
                changed.append(relative)
        if (
            not changed
            and record.verified_commit
            and current_commit
            and record.verified_commit != current_commit
            and not record.source.content_hashes
        ):
            changed.extend(record.source.paths or ("<repository>",))
        return MemoryRecordStatus(
            record=record,
            freshness=MemoryFreshness.STALE if changed else MemoryFreshness.FRESH,
            changed_sources=tuple(sorted(changed)),
        )

    def revalidate(
        self,
        current_commit: str,
        record_ids: tuple[str, ...] = (),
    ) -> MemoryRevalidationResult:
        """Explicitly revalidate stale records whose source files still exist.

        Revalidation changes provenance only: identity and durable content remain
        unchanged. Missing source files remain stale. Passing record IDs limits the
        operation to those records; otherwise every approved record is considered.
        """

        if not current_commit.strip():
            raise ConflictError("Memory revalidation requires the current Git commit")
        requested = tuple(
            dict.fromkeys(_require_id(value, _MEMORY_ID, "memory ID") for value in record_ids)
        )
        with FileLock(self.lock_path):
            records = (
                tuple(self.get(identifier) for identifier in requested)
                if requested
                else self.list()
            )
            statuses: list[MemoryRecordStatus] = []
            revalidated: list[str] = []
            unchanged: list[str] = []
            stale: list[str] = []
            for record in records:
                current = self.status(record, current_commit)
                if current.freshness == MemoryFreshness.FRESH:
                    statuses.append(current)
                    unchanged.append(record.id)
                    continue
                hashes: dict[str, str] = {}
                missing = False
                for relative in record.source.paths:
                    digest = _hash(_source_path(self.layout.root, relative))
                    if digest is None:
                        missing = True
                        break
                    hashes[relative] = digest
                if missing:
                    statuses.append(current)
                    stale.append(record.id)
                    continue
                updated = record.model_copy(
                    update={
                        "source": record.source.model_copy(update={"content_hashes": hashes}),
                        "verified_commit": current_commit,
                        "last_verified_at": utc_now(),
                    }
                )
                _ensure_secret_safe(updated.title, updated.content, updated.model_dump_json())
                self._validate_sources(updated)
                path = self.records / f"{updated.id}.md"
                if not path.is_file() or _parse_record(path) != record:
                    raise ConflictError("Memory changed while it was being revalidated")
                atomic_write_bytes(path, _frontmatter(updated))
                statuses.append(self.status(updated, current_commit))
                revalidated.append(updated.id)
            return MemoryRevalidationResult(
                current_commit=current_commit,
                statuses=tuple(statuses),
                revalidated_ids=tuple(revalidated),
                unchanged_ids=tuple(unchanged),
                stale_ids=tuple(stale),
            )

    def propose(
        self,
        record: DurableMemoryRecord,
        rationale: str,
        *,
        policy: DurableUpdatePolicy = DurableUpdatePolicy.REVIEW,
        evidence: tuple[str, ...] = (),
    ) -> MemoryProposal:
        _ensure_secret_safe(record.title, record.content, rationale, *evidence)
        self._validate_sources(record)
        with FileLock(self.lock_path):
            if (self.records / f"{record.id}.md").exists():
                raise ConflictError("Memory identity already exists")
            for root in (self.staging, self.history):
                for path in root.glob("MEM-PROP-*/proposal.yaml") if root.is_dir() else ():
                    existing = read_json_object(path).get("record")
                    if isinstance(existing, dict) and existing.get("id") == record.id:
                        raise ConflictError("Memory identity already has a proposal")
            proposal_id = self._next_id("MEM-PROP")
            proposal = MemoryProposal(
                id=proposal_id,
                policy=policy,
                record=record,
                rationale=rationale,
                evidence=evidence,
            )
            directory = self.staging / proposal.id
            directory.mkdir(parents=True, exist_ok=False)
            atomic_write_json(directory / "proposal.yaml", proposal.model_dump(mode="json"))
            atomic_write_bytes(directory / "proposed.md", _frontmatter(record))
            atomic_write_bytes(
                directory / "diff.md",
                (
                    f"# Proposed memory update\n\nCategory: `{record.category}`\n\n"
                    f"## Rationale\n\n{rationale.strip()}\n"
                ).encode(),
            )
            atomic_write_json(directory / "evidence.json", {"sources": list(evidence)})
        if policy == DurableUpdatePolicy.AUTO:
            return self.approve(proposal.id, "Approved by configured auto policy")
        return proposal

    def _validate_sources(self, record: DurableMemoryRecord) -> None:
        for relative in record.source.paths:
            _source_path(self.layout.root, relative)

    def proposal(self, proposal_id: str) -> MemoryProposal:
        proposal_id = _require_id(proposal_id, _PROPOSAL_ID, "memory proposal ID")
        for root in (self.staging, self.history):
            path = root / proposal_id / "proposal.yaml"
            if path.is_file():
                return MemoryProposal.model_validate(read_json_object(path))
        raise NotFoundError("Memory proposal not found")

    def proposals(self, introduced_by_task: str | None = None) -> tuple[MemoryProposal, ...]:
        """List staged and reviewed proposals, optionally for one Task Capsule."""

        values: list[MemoryProposal] = []
        for root in (self.staging, self.history):
            if not root.is_dir():
                continue
            for path in sorted(root.glob("MEM-PROP-*/proposal.yaml")):
                proposal = MemoryProposal.model_validate(read_json_object(path))
                if (
                    introduced_by_task is None
                    or proposal.record.introduced_by_task == introduced_by_task
                ):
                    values.append(proposal)
        return tuple(sorted(values, key=lambda item: (item.created_at, item.id)))

    def propose_task_outcome(
        self,
        task_id: str,
        title: str,
        content: str,
        verified_commit: str,
        evidence: tuple[str, ...],
    ) -> MemoryProposal:
        """Idempotently stage a successful Task Capsule outcome under project policy."""

        task_id = _require_id(task_id, _TASK_ID, "Task Capsule ID")
        with FileLock(self.lock_path):
            existing = next(
                (
                    proposal
                    for proposal in self.proposals(task_id)
                    if proposal.record.title == title
                ),
                None,
            )
            if existing is not None:
                return existing
            record = self.new_record(
                MemoryCategory.WORKFLOWS,
                title,
                content,
                MemoryProvenance(type="task"),
                verified_commit=verified_commit,
                introduced_by_task=task_id,
            )
            return self.propose(
                record,
                "Accepted delivery outcome proposed by the Memory Curator.",
                policy=self.configured_policy(),
                evidence=evidence,
            )

    def approve(self, proposal_id: str, reason: str) -> MemoryProposal:
        return self._review(proposal_id, True, reason)

    def reject(self, proposal_id: str, reason: str) -> MemoryProposal:
        return self._review(proposal_id, False, reason)

    def _review(self, proposal_id: str, approved: bool, reason: str) -> MemoryProposal:
        if not reason.strip():
            raise ConflictError("Memory review requires a reason")
        proposal_id = _require_id(proposal_id, _PROPOSAL_ID, "memory proposal ID")
        with FileLock(self.lock_path):
            directory = self.staging / proposal_id
            path = directory / "proposal.yaml"
            if not path.is_file():
                existing = self.proposal(proposal_id)
                expected = "APPROVED" if approved else "REJECTED"
                if existing.status == expected:
                    return existing
                raise ConflictError("Memory proposal is no longer pending")
            proposal = MemoryProposal.model_validate(read_json_object(path))
            if proposal.status != "PENDING":
                raise ConflictError("Memory proposal is no longer pending")
            if approved:
                self.save(proposal.record)
            reviewed = proposal.model_copy(
                update={
                    "status": "APPROVED" if approved else "REJECTED",
                    "reviewed_at": utc_now(),
                    "review_reason": reason,
                }
            )
            atomic_write_json(path, reviewed.model_dump(mode="json"))
            self.history.mkdir(parents=True, exist_ok=True)
            target = self.history / proposal_id
            directory.replace(target)
            return reviewed


def source_hashes(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    """Capture repository-relative hashes for later freshness validation."""

    result: dict[str, str] = {}
    for relative in paths:
        candidate = _source_path(root, relative)
        if not candidate.is_file():
            raise PolicyDeniedError("Memory provenance must reference a project file")
        value = _hash(candidate)
        assert value is not None
        result[relative] = value
    return result
