"""Reviewed supersession must preserve history across crashes and concurrent reviews."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import orqalis.memory.curated as curated
from orqalis.domain.base import utc_now
from orqalis.domain.errors import ConflictError, NotFoundError, PolicyDeniedError
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryFreshness,
    MemoryLifecycle,
    MemoryLifecycleDocument,
    MemoryProvenance,
    MemorySupersession,
)
from orqalis.persistence.filesystem.io import atomic_write_json
from orqalis.persistence.filesystem.layout import ProjectLayout, bootstrap_project_store


def _store(root: Path) -> CuratedMemoryStore:
    root.mkdir(exist_ok=True)
    bootstrap_project_store(root, project_name="lifecycle")
    return CuratedMemoryStore(ProjectLayout(root))


def _record(
    store: CuratedMemoryStore, content: str = "Use the local filesystem."
) -> curated.DurableMemoryRecord:
    return store.new_record(
        MemoryCategory.DECISION, "Persistence decision", content, MemoryProvenance(type="user")
    )


def test_only_approved_successor_is_active_and_history_remains_readable(tmp_path: Path) -> None:
    store = _store(tmp_path / "repo")
    old = _record(store)
    store.save(old)
    new = _record(store, "Use atomic local snapshots.")
    proposal = store.propose(
        new, "Replace the older decision.", supersedes=old.id, evidence=("accepted task evidence",)
    )
    assert store.search("persistence") == (old,)
    reviewed = store.approve(proposal.id, "Reviewed source evidence")
    assert reviewed.record.supersedes == old.id
    assert store.list() == (reviewed.record,)
    assert {r.id for r in store.list(include_inactive=True)} == {old.id, new.id}
    status = store.status(store.get(old.id), None)
    assert status.lifecycle == MemoryLifecycle.SUPERSEDED
    assert status.superseded_by == new.id
    assert store.get(old.id).content == old.content
    assert store.approve(proposal.id, "retry") == reviewed
    with pytest.raises(ConflictError):
        store.reject(proposal.id, "cannot undo approved history")
    with pytest.raises(ConflictError):
        store.revalidate("newcommit", (old.id,))
    other = _store(tmp_path / "other")
    _record(other)  # Reserve the colliding local ID; neither store shares records.
    with pytest.raises(NotFoundError):
        other.propose(_record(other), "Cross-project ID", supersedes=old.id)


def test_rejected_and_conflicting_proposals_do_not_hide_predecessor(tmp_path: Path) -> None:
    store = _store(tmp_path / "repo")
    old = _record(store)
    old_path = store.save(old)
    rejected = store.propose(_record(store, "candidate one"), "reason", supersedes=old.id)
    store.reject(rejected.id, "not accepted")
    assert store.list() == (old,)
    pending = store.propose(_record(store, "candidate two"), "reason", supersedes=old.id)
    changed = old.model_copy(update={"content": "Human edited the decision during review."})
    old_path.write_bytes(curated._frontmatter(changed))
    with pytest.raises(ConflictError, match="changed after proposal"):
        store.approve(pending.id, "outdated review")
    assert store.list() == (changed,)
    assert store.proposal(pending.id).status == "PENDING"


@pytest.mark.parametrize("boundary", ["before_transition", "after_transition", "after_review"])
def test_crash_boundaries_have_one_active_record_and_retry_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    store = _store(tmp_path / "repo")
    old = _record(store)
    store.save(old)
    new = _record(store, "Use reviewed atomic supersession.")
    proposal = store.propose(new, "replace decision", supersedes=old.id)
    original = atomic_write_json

    def fail_at_boundary(path: Path, value: Any) -> None:
        is_transition = path == store.lifecycle_path
        is_review = path.name == "proposal.yaml" and value.get("status") == "APPROVED"
        if is_transition and boundary == "before_transition":
            raise OSError("simulated stop before transition")
        original(path, value)
        if (is_transition and boundary == "after_transition") or (
            is_review and boundary == "after_review"
        ):
            raise OSError("simulated stop after atomic write")

    monkeypatch.setattr(curated, "atomic_write_json", fail_at_boundary)
    with pytest.raises(OSError, match="simulated stop"):
        store.approve(proposal.id, "reviewed")
    fresh = CuratedMemoryStore(store.layout)
    expected = old.id if boundary == "before_transition" else new.id
    assert [record.id for record in fresh.list()] == [expected]
    monkeypatch.setattr(curated, "atomic_write_json", original)
    approved = fresh.approve(proposal.id, "reviewed retry")
    assert approved.status == "APPROVED"
    assert [record.id for record in fresh.list()] == [new.id]
    assert len(fresh._lifecycle_document().supersessions) == 1
    assert fresh.approve(proposal.id, "another retry") == approved


def test_concurrent_reviews_cannot_publish_competing_successors(tmp_path: Path) -> None:
    store = _store(tmp_path / "repo")
    old = _record(store)
    store.save(old)
    proposals = tuple(
        store.propose(_record(store, f"candidate {i}"), "reason", supersedes=old.id)
        for i in range(2)
    )

    def approve(identifier: str) -> str:
        try:
            return store.approve(identifier, "reviewed").record.id
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(approve, (proposal.id for proposal in proposals)))
    assert results.count("conflict") == 1
    assert [record.id for record in store.list()] == [
        item for item in results if item != "conflict"
    ]


def test_lifecycle_cycles_and_missing_records_fail_closed(tmp_path: Path) -> None:
    now = utc_now()
    ids = ("MEM-20260926-0001", "MEM-20260926-0002")
    first = MemorySupersession(
        predecessor=ids[0],
        successor=ids[1],
        predecessor_digest="a" * 64,
        proposal_id="MEM-PROP-20260926-0001",
        reviewed_at=now,
        reason="reviewed",
    )
    second = first.model_copy(update={"predecessor": ids[1], "successor": ids[0]})
    with pytest.raises(ValidationError, match="cycle"):
        MemoryLifecycleDocument(supersessions=(first, second))
    store = _store(tmp_path / "repo")
    atomic_write_json(
        store.lifecycle_path,
        MemoryLifecycleDocument(supersessions=(first,)).model_dump(mode="json"),
    )
    with pytest.raises(ConflictError, match="missing record"):
        store.list()


def test_self_supersession_and_secret_review_reason_are_denied(tmp_path: Path) -> None:
    store = _store(tmp_path / "repo")
    record = _record(store)
    with pytest.raises(ConflictError, match="itself"):
        store.propose(record, "self", supersedes=record.id)
    proposal = store.propose(record, "reason")
    with pytest.raises(PolicyDeniedError):
        store.approve(proposal.id, "password=verysecret123")
    assert not store.list()


def test_status_batch_shares_lifecycle_and_source_reads_without_hiding_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path / "repo")
    source = store.layout.root / "policy.md"
    source.write_text("Use atomic snapshots.\n", encoding="utf-8")
    expected_hash = sha256(source.read_bytes()).hexdigest()
    provenance = MemoryProvenance(
        type="repository",
        paths=("policy.md",),
        content_hashes={"policy.md": expected_hash},
    )
    old = store.new_record(MemoryCategory.DECISION, "Old rule", "First rule.", provenance)
    store.save(old)
    peer = store.new_record(MemoryCategory.DECISION, "Peer rule", "Second rule.", provenance)
    store.save(peer)
    successor = store.new_record(
        MemoryCategory.DECISION, "New rule", "Reviewed replacement.", provenance
    )
    proposal = store.propose(successor, "Replace old rule", supersedes=old.id)
    approved = store.approve(proposal.id, "Reviewed source")
    records = store.list(include_inactive=True)
    calls = {"lifecycle": 0, "source": 0}
    original_lifecycle = store._lifecycle_document
    original_hash = curated._hash

    def lifecycle() -> MemoryLifecycleDocument:
        calls["lifecycle"] += 1
        return original_lifecycle()

    def hash_source(path: Path) -> str | None:
        calls["source"] += 1
        return original_hash(path)

    monkeypatch.setattr(store, "_lifecycle_document", lifecycle)
    monkeypatch.setattr(curated, "_hash", hash_source)
    statuses = store.statuses(records, None)
    by_id = {status.record.id: status for status in statuses}
    assert len(statuses) == 3
    assert by_id[old.id].lifecycle == MemoryLifecycle.SUPERSEDED
    assert by_id[old.id].superseded_by == approved.record.id
    assert by_id[peer.id].lifecycle == by_id[approved.record.id].lifecycle == MemoryLifecycle.ACTIVE
    assert all(status.freshness == MemoryFreshness.FRESH for status in statuses)
    assert calls == {"lifecycle": 1, "source": 1}

    source.write_text("Use reviewed event logs.\n", encoding="utf-8")
    changed = store.statuses(records, None)
    assert all(status.freshness == MemoryFreshness.STALE for status in changed)
    assert all(status.changed_sources == ("policy.md",) for status in changed)
    assert calls == {"lifecycle": 2, "source": 2}

    other = tmp_path / "other"
    other.mkdir()
    (other / "policy.md").write_text("Use atomic snapshots.\n", encoding="utf-8")
    alternate = store.statuses(records, None, source_root=other)
    assert all(status.freshness == MemoryFreshness.FRESH for status in alternate)
    assert calls == {"lifecycle": 3, "source": 3}
