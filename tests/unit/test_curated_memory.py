import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from orqalis.context import ProjectContextBuilder
from orqalis.domain.errors import ConflictError, PolicyDeniedError
from orqalis.memory.curated import (
    CuratedMemoryStore,
    DurableMemoryRecord,
    DurableUpdatePolicy,
    MemoryCategory,
    MemoryFreshness,
    MemoryProvenance,
    source_hashes,
)
from orqalis.persistence.filesystem.io import atomic_write_json, read_json_object
from orqalis.persistence.filesystem.layout import ProjectLayout, bootstrap_project_store
from orqalis.sdk import Orqalis
from tests.conftest import fixture_git


def _store(tmp_path: Path) -> CuratedMemoryStore:
    root = tmp_path / "repo"
    root.mkdir()
    bootstrap_project_store(root, project_name="fixture")
    return CuratedMemoryStore(ProjectLayout(root))


def test_memory_initialization_and_retrieval(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.initialize()
    assert (store.layout.memory / "architecture.md").is_file()
    record = store.new_record(
        MemoryCategory.ARCHITECTURE,
        "Local state",
        "Task history is stored inside the repository.",
        MemoryProvenance(type="user"),
    )
    path = store.save(record)
    assert path.read_text(encoding="utf-8").startswith("---\n")
    assert store.get(record.id) == record
    assert store.search("task repository") == (record,)


def test_memory_freshness_uses_source_hashes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    source = store.layout.root / "service.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    hashes = source_hashes(store.layout.root, ("service.py",))
    record = store.new_record(
        MemoryCategory.CONVENTIONS,
        "Constant policy",
        "The service declares its constant at module scope.",
        MemoryProvenance(type="repository", paths=("service.py",), content_hashes=hashes),
        verified_commit="abc",
    )
    assert store.status(record, "def").freshness == MemoryFreshness.FRESH
    source.write_text("VALUE = 2\n", encoding="utf-8")
    status = store.status(record, "def")
    assert status.freshness == MemoryFreshness.STALE
    assert status.changed_sources == ("service.py",)


def test_selective_revalidation_updates_only_provenance_and_keeps_missing_stale(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first_source = store.layout.root / "first.py"
    missing_source = store.layout.root / "missing.py"
    first_source.write_text("VALUE = 1\n", encoding="utf-8")
    missing_source.write_text("VALUE = 1\n", encoding="utf-8")
    first = store.new_record(
        MemoryCategory.ARCHITECTURE,
        "First source",
        "The first source owns the durable boundary.",
        MemoryProvenance(
            type="repository",
            paths=("first.py",),
            content_hashes=source_hashes(store.layout.root, ("first.py",)),
        ),
        verified_commit="a" * 40,
    )
    missing = store.new_record(
        MemoryCategory.PITFALLS,
        "Missing source",
        "The missing source must be restored before revalidation.",
        MemoryProvenance(
            type="repository",
            paths=("missing.py",),
            content_hashes=source_hashes(store.layout.root, ("missing.py",)),
        ),
        verified_commit="a" * 40,
    )
    store.save(first)
    store.save(missing)
    first_source.write_text("VALUE = 2\n", encoding="utf-8")
    missing_source.unlink()

    result = store.revalidate("b" * 40, (first.id, missing.id))

    refreshed = store.get(first.id)
    assert result.revalidated_ids == (first.id,)
    assert result.stale_ids == (missing.id,)
    assert refreshed.id == first.id
    assert refreshed.title == first.title
    assert refreshed.content == first.content
    assert refreshed.verified_commit == "b" * 40
    assert refreshed.source.content_hashes == source_hashes(store.layout.root, ("first.py",))
    assert store.status(refreshed, "b" * 40).freshness == MemoryFreshness.FRESH
    replay = store.revalidate("b" * 40, (first.id,))
    assert replay.revalidated_ids == ()
    assert replay.unchanged_ids == (first.id,)


def test_memory_proposal_approval_and_rejection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.new_record(
        MemoryCategory.PITFALLS,
        "Retry durability",
        "Retry state must survive a process restart.",
        MemoryProvenance(type="task"),
    )
    proposed = store.propose(first, "Observed during acceptance", evidence=("AC-restart",))
    assert proposed.policy == DurableUpdatePolicy.REVIEW
    approved = store.approve(proposed.id, "Evidence is durable")
    assert approved.status == "APPROVED"
    assert store.get(first.id) == first
    assert (store.history / proposed.id / "proposal.yaml").is_file()

    second = store.new_record(
        MemoryCategory.DOMAIN,
        "Temporary guess",
        "This has not been verified.",
        MemoryProvenance(type="task"),
    )
    rejected = store.reject(
        store.propose(second, "Candidate inference").id, "Insufficient source evidence"
    )
    assert rejected.status == "REJECTED"
    assert second not in store.list()


def test_pending_and_concurrent_memory_records_have_unique_ids(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def create(number: int) -> DurableMemoryRecord:
        return store.new_record(
            MemoryCategory.ARCHITECTURE,
            f"Decision {number}",
            f"Durable decision {number}.",
            MemoryProvenance(type="user"),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = tuple(pool.map(create, range(4)))
    assert len({record.id for record in records}) == 4
    proposals = tuple(store.propose(record, "Reviewable evidence") for record in records)
    assert len({proposal.record.id for proposal in proposals}) == 4


def test_successful_task_outcome_is_staged_idempotently_under_review_policy(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    task_id = "ORQ-20260916-0001"

    first = store.propose_task_outcome(
        task_id,
        f"Accepted task {task_id}",
        "The accepted delivery established a durable project workflow.",
        "a" * 40,
        ("commit:" + "a" * 40,),
    )
    replay = store.propose_task_outcome(
        task_id,
        f"Accepted task {task_id}",
        "The accepted delivery established a durable project workflow.",
        "a" * 40,
        ("commit:" + "a" * 40,),
    )

    assert first == replay
    assert first.status == "PENDING"
    assert first.record.introduced_by_task == task_id
    assert store.proposals(task_id) == (first,)


def test_reviewed_task_memory_enters_context_only_after_approval_and_revalidation(
    git_repo: Path,
) -> None:
    layout = bootstrap_project_store(git_repo, project_name="fixture")
    store = CuratedMemoryStore(layout)
    head = fixture_git(git_repo, "rev-parse", "HEAD")
    task_id = "ORQ-20260916-0001"
    proposal = store.propose_task_outcome(
        task_id,
        f"Accepted task {task_id}",
        "The accepted task established a durable retry workflow.",
        head,
        (f"commit:{head}",),
    )

    pending = ProjectContextBuilder(git_repo).build("durable retry workflow")
    assert proposal.status == "PENDING"
    assert proposal.record.id not in {item.record.id for item in pending.memory}

    store.approve(proposal.id, "Acceptance evidence verifies the durable workflow")
    approved = ProjectContextBuilder(git_repo).build("durable retry workflow")
    approved_item = next(item for item in approved.memory if item.record.id == proposal.record.id)
    assert approved_item.freshness == MemoryFreshness.FRESH

    (git_repo / "main.py").write_text("answer = 43\n", encoding="utf-8")
    fixture_git(git_repo, "add", "main.py")
    fixture_git(git_repo, "commit", "-m", "test: advance branch")
    stale = ProjectContextBuilder(git_repo).build("durable retry workflow")
    assert (
        next(item for item in stale.memory if item.record.id == proposal.record.id).freshness
        == MemoryFreshness.STALE
    )

    sdk = Orqalis(root=git_repo)
    try:
        result = sdk.revalidate_project_memory((proposal.record.id,))
    finally:
        sdk.close()
    assert result.revalidated_ids == (proposal.record.id,)
    revalidated = ProjectContextBuilder(git_repo).build("durable retry workflow")
    assert (
        next(item for item in revalidated.memory if item.record.id == proposal.record.id).freshness
        == MemoryFreshness.FRESH
    )


def test_sdk_searches_curated_memory_with_freshness(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = store.new_record(
        MemoryCategory.DOMAIN,
        "Retry vocabulary",
        "A retry window is the bounded period for offline attempts.",
        MemoryProvenance(type="user"),
    )
    store.save(record)

    sdk = Orqalis(root=store.layout.root)
    try:
        matches = sdk.search_project_memory("retry")
    finally:
        sdk.close()

    assert tuple(item.record for item in matches) == (record,)
    assert matches[0].freshness == MemoryFreshness.FRESH


@pytest.mark.parametrize("path", ("../outside.py", r"..\outside.py", "C:/outside.py"))
def test_memory_provenance_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        MemoryProvenance(type="repository", paths=(path,))


@pytest.mark.parametrize(
    "content",
    (
        "api_key=sk-private12345678",
        "postgresql://user:private-password@example.invalid/db",
        "-----BEGIN PRIVATE KEY-----\nprivate",
    ),
)
def test_memory_rejects_secrets(tmp_path: Path, content: str) -> None:
    store = _store(tmp_path)
    record = store.new_record(
        MemoryCategory.TECHNOLOGY,
        "Credentials",
        content,
        MemoryProvenance(type="user"),
    )
    with pytest.raises(PolicyDeniedError):
        store.save(record)


def test_source_hash_helper_is_sha256(tmp_path: Path) -> None:
    store = _store(tmp_path)
    source = store.layout.root / "README.md"
    source.write_bytes(b"hello")
    assert (
        source_hashes(store.layout.root, ("README.md",))["README.md"]
        == hashlib.sha256(b"hello").hexdigest()
    )


def test_memory_identifiers_cannot_escape_the_project_store(tmp_path: Path) -> None:
    store = _store(tmp_path)
    outside = store.layout.root / "outside.md"
    outside.write_text("must not be read", encoding="utf-8")

    with pytest.raises(PolicyDeniedError, match="memory ID"):
        store.get("../outside")
    with pytest.raises(PolicyDeniedError, match="proposal ID"):
        store.proposal("../../outside")
    with pytest.raises(PolicyDeniedError, match="proposal ID"):
        store.approve("../../outside", "unsafe")


def test_durable_update_policy_is_project_configured(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.configured_policy() == DurableUpdatePolicy.REVIEW
    config = read_json_object(store.layout.config)
    config["memory"] = {"durable_updates": "auto"}
    atomic_write_json(store.layout.config, config)
    assert store.configured_policy() == DurableUpdatePolicy.AUTO

    record = store.new_record(
        MemoryCategory.CONVENTIONS,
        "Stable command",
        "Use the repository-local test command.",
        MemoryProvenance(type="user"),
    )
    proposal = store.propose(
        record,
        "Confirmed by project policy",
        policy=store.configured_policy(),
    )
    assert proposal.status == "APPROVED"
    assert store.get(record.id) == record

    config["memory"] = {"durable_updates": "invalid"}
    atomic_write_json(store.layout.config, config)
    with pytest.raises(ConflictError, match="policy"):
        store.configured_policy()
