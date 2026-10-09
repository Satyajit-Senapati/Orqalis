"""Progressive memory reads must reduce context without hiding relevant long records."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from orqalis.context import ProjectContextBuilder
from orqalis.domain.errors import InputError, NotFoundError
from orqalis.memory.curated import (
    CuratedMemoryStore,
    MemoryCategory,
    MemoryProvenance,
    _frontmatter,
)
from orqalis.memory.navigation import MemoryNavigationService
from orqalis.persistence.filesystem.layout import ProjectLayout, bootstrap_project_store


def _store(root: Path) -> CuratedMemoryStore:
    root.mkdir(exist_ok=True)
    bootstrap_project_store(root, project_name="navigation")
    return CuratedMemoryStore(ProjectLayout(root))


def test_discovery_has_small_explainable_metadata_and_get_pages_exact_body(tmp_path: Path) -> None:
    store = _store(tmp_path / "repo")
    body = ('Durability \U0001f9e0 "quoted" detail.\n' * 2000).strip()
    record = store.new_record(
        MemoryCategory.DECISION,
        "Durability policy",
        body,
        MemoryProvenance(type="user"),
        summary="Atomic snapshots preserve task state.",
    )
    store.save(record)
    service = MemoryNavigationService(store)
    found = service.discover("durability", max_chars=1000)
    assert [item.id for item in found.items] == [record.id]
    assert found.items[0].matched_on == ("title", "body")
    assert found.size_chars == len(found.model_dump_json()) <= 1000
    assert found.size_chars < len(body) / 20
    assert found.items[0].preview == record.summary
    assert not service.discover("quantum cooking airport").items
    chunks = []
    offset = 0
    while True:
        page = service.read(record.id, offset=offset, max_chars=4000)
        assert page.size_chars == len(page.model_dump_json()) <= 4000
        chunks.append(page.content)
        if page.next_offset is None:
            break
        assert page.next_offset > offset
        offset = page.next_offset
    assert "".join(chunks) == body
    with pytest.raises(InputError):
        service.read(record.id, offset=len(body) + 1)


def test_explicit_references_validate_and_integrity_reports_manual_corruption(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "repo")
    detail = store.new_record(
        MemoryCategory.MODULE, "Sync detail", "Bounded retries.", MemoryProvenance(type="user")
    )
    store.save(detail)
    overview = store.new_record(
        MemoryCategory.ARCHITECTURE,
        "Sync overview",
        "Read the referenced module.",
        MemoryProvenance(type="user"),
        references=(detail.id,),
    )
    store.save(overview)
    service = MemoryNavigationService(store)
    assert service.check().ok
    assert service.read(overview.id).references == (detail.id,)
    missing = store.new_record(
        MemoryCategory.MODULE,
        "Missing",
        "No target.",
        MemoryProvenance(type="user"),
        references=("MEM-20000101-0001",),
    )
    with pytest.raises(NotFoundError):
        store.save(missing)
    with pytest.raises(ValidationError):
        type(detail).model_validate({**detail.model_dump(), "references": (detail.id,)})
    # Human edits remain possible; checking them must report cycles/broken targets.
    detail_path = store.records / f"{detail.id}.md"
    detail_path.write_bytes(
        _frontmatter(detail.model_copy(update={"references": (overview.id, "MEM-20000101-0001")}))
    )
    report = service.check()
    assert not report.ok
    assert {issue.kind for issue in report.issues} == {"reference_cycle", "missing_reference"}
    limited = service.check(max_issues=1)
    assert limited.truncated and len(limited.issues) == 1


@pytest.mark.parametrize("budget", [1000, 4000, 12000])
def test_long_relevant_memory_is_discoverable_inside_automatic_context(
    git_repo: Path, budget: int
) -> None:
    store = _store(git_repo)
    record = store.new_record(
        MemoryCategory.DECISION,
        "Zephyr durability",
        "zephyr durability details. " * 3000,
        MemoryProvenance(type="user"),
        summary="Atomic checkpoints govern Zephyr durability.",
    )
    store.save(record)
    pack = ProjectContextBuilder(git_repo).build("zephyr durability", budget)
    assert len(pack.model_dump_json()) <= budget
    assert pack.size_chars == len(pack.model_dump_json())
    assert not pack.memory
    assert [item.id for item in pack.memory_discovery] == [record.id]
    assert pack.truncated


def test_irrelevant_graph_fallback_is_explicit_orientation(git_repo: Path) -> None:
    _store(git_repo)
    pack = ProjectContextBuilder(git_repo).build("quantum chocolate airport", 12000)
    assert pack.graph
    assert all(item.orientation_only for item in pack.graph)
    assert all(item.match_reasons == ("centrality",) for item in pack.graph)


@pytest.mark.parametrize("metadata", ["[]", "null", '"text"', "12"])
def test_integrity_reports_non_object_frontmatter(tmp_path: Path, metadata: str) -> None:
    store = _store(tmp_path / "repo")
    store.records.mkdir(parents=True, exist_ok=True)
    (store.records / "MEM-20000101-0001.md").write_text(
        f"---\n{metadata}\n---\n\n# malformed\n", encoding="utf-8"
    )
    result = MemoryNavigationService(store).check()
    assert not result.ok
    assert "invalid_record" in {issue.kind for issue in result.issues}
