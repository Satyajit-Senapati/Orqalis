from pathlib import Path

from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
from orqalis.persistence.filesystem import ProjectLayout
from orqalis.sdk import Orqalis


def test_project_brain_projects_authoritative_context_not_legacy_cache(git_repo: Path) -> None:
    sdk = Orqalis(root=git_repo)
    try:
        project = sdk.initialize(git_repo)
        store = CuratedMemoryStore(ProjectLayout(git_repo))
        record = store.new_record(
            MemoryCategory.DOMAIN,
            "Repository authority",
            "Durable project knowledge is owned by the curated filesystem store.",
            MemoryProvenance(type="user"),
        )
        proposal = store.propose(record, "Keep the persistence authority explicit")
        assert store.approve(proposal.id, "Verified by the repository maintainer").status == (
            "APPROVED"
        )

        source_records = tuple(
            (git_repo / ".orqalis" / "cache" / "search" / "source-records").glob("SRC-*.md")
        )
        assert source_records

        brain = sdk.brain.get(project.id)

        assert brain.query == ""
        assert any(match.item.title == record.title for match in brain.matches)
        assert not {
            "AGENTS.md",
            "main.py",
            "Project overview",
            "pyproject.toml",
            "tests/test_main.py",
        }.intersection(match.item.title for match in brain.matches)
        assert brain.freshness.active_items == len(brain.matches)
        assert brain.entities
    finally:
        sdk.close()
