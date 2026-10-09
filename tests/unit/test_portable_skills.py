from pathlib import Path

import pytest

from orqalis.domain.capabilities import ToolName
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.skills.registry import SkillRegistry


def skill(root: Path, header: str = "", body: str = "Inspect references/guide.md.") -> Path:
    directory = root / "code-review"
    directory.mkdir()
    (directory / "SKILL.md").write_text(
        "---\nname: code-review\ndescription: Review code with evidence.\n"
        + header
        + "---\n"
        + body,
        encoding="utf-8",
    )
    return directory


def test_standard_skill_selection_and_resources_preserve_policy(tmp_path: Path) -> None:
    directory = skill(
        tmp_path,
        'allowed-tools: Read\nmetadata:\n  orqalis-version: "1.2.0"\n'
        '  orqalis-capabilities: "review, evidence"\n',
    )
    (directory / "references").mkdir()
    (directory / "references/guide.md").write_text("Verify every claim.", encoding="utf-8")
    registry = SkillRegistry((tmp_path,))
    (metadata,) = registry.discover()
    assert metadata.required_tools == (ToolName.FILE_READ,)
    assert metadata.version == "1.2.0"
    with pytest.raises(InputError):
        registry.select(("review",), ())
    (loaded,) = registry.select(("review", "evidence"), (ToolName.FILE_READ,))
    assert loaded.instructions == "Inspect references/guide.md."
    resource = registry.read_resource(metadata, "references/guide.md")
    assert resource.content == "Verify every claim."
    assert len(resource.content_hash) == 64
    (directory / "references/guide.md").write_text("Changed guide.", encoding="utf-8")
    with pytest.raises(ConflictError):
        registry.read_resource(metadata, "references/guide.md")


def test_skill_body_is_not_exposed_during_discovery_and_changes_are_detected(
    tmp_path: Path,
) -> None:
    directory = skill(tmp_path)
    registry = SkillRegistry((tmp_path,))
    (metadata,) = registry.discover()
    assert metadata.version == "0.0.0"
    assert "Inspect references" not in metadata.model_dump_json()
    (directory / "SKILL.md").write_text(
        (directory / "SKILL.md").read_text() + "\nChanged instructions.", encoding="utf-8"
    )
    with pytest.raises(ConflictError):
        registry.load(metadata)


@pytest.mark.parametrize(
    "header",
    [
        "name: other\n",
        "unknown-field: value\n",
        "allowed-tools: Bash(git:*)\n",
        "allowed-tools: unknown.tool\n",
        "metadata: {version: 1.0}\n",
        "metadata: {a: one, a: two}\n",
        "metadata: {a: &anchor value, b: *anchor}\n",
        "metadata: {a: {b: {c: value}}}\n",
        "license: !!python/object/apply:os.system []\n",
        "metadata:\n  orqalis-version: invalid\n",
        "metadata:\n  orqalis-capabilities: ' , '\n",
    ],
)
def test_unsupported_ambiguous_and_executable_metadata_are_rejected(
    tmp_path: Path, header: str
) -> None:
    skill(tmp_path, header)
    with pytest.raises(InputError):
        SkillRegistry((tmp_path,))


@pytest.mark.parametrize(
    "path", ["../outside.md", "/outside.md", "C:/outside.md", "references/../SKILL.md"]
)
def test_skill_resources_cannot_escape_root(tmp_path: Path, path: str) -> None:
    skill(tmp_path)
    registry = SkillRegistry((tmp_path,))
    with pytest.raises(PolicyDeniedError):
        registry.read_resource(registry.discover()[0], path)


def test_skill_symlink_parent_is_rejected(tmp_path: Path) -> None:
    directory = skill(tmp_path)
    link = tmp_path / "linked"
    try:
        link.symlink_to(directory, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires local OS permissions")
    with pytest.raises(PolicyDeniedError):
        SkillRegistry((tmp_path,))


def test_native_and_legacy_formats_cannot_silently_override_each_other(tmp_path: Path) -> None:
    directory = skill(tmp_path)
    (directory / "skill.toml").write_text(
        'id="code-review"\nversion="1.0.0"\ndescription="Review"\ncapabilities=["review"]\n'
    )
    with pytest.raises(ConflictError):
        SkillRegistry((tmp_path,))


def test_legacy_instruction_changes_require_rediscovery(tmp_path: Path) -> None:
    directory = tmp_path / "legacy"
    directory.mkdir()
    (directory / "skill.toml").write_text(
        'id="legacy"\nversion="1.0.0"\ndescription="Review"\ncapabilities=["review"]\n'
    )
    body = directory / "instructions.md"
    body.write_text("Original instructions.")
    registry = SkillRegistry((tmp_path,))
    (metadata,) = registry.discover()
    registry.load(metadata)
    body.write_text("Changed instructions.")
    with pytest.raises(ConflictError):
        registry.load(metadata)


def test_frontmatter_without_body_or_final_newline_is_valid(tmp_path: Path) -> None:
    directory = skill(tmp_path)
    (directory / "SKILL.md").write_text("---\nname: code-review\ndescription: Review changes.\n---")
    registry = SkillRegistry((tmp_path,))
    assert registry.load(registry.discover()[0]).instructions == ""


def test_missing_binary_and_oversized_resources_are_rejected(tmp_path: Path) -> None:
    directory = skill(tmp_path)
    (directory / "binary.bin").write_bytes(b"\xff\xfe")
    (directory / "large.md").write_text("x" * 100001)
    registry = SkillRegistry((tmp_path,))
    metadata = registry.discover()[0]
    for name in ("missing.md", "binary.bin"):
        with pytest.raises((InputError, PolicyDeniedError)):
            registry.read_resource(metadata, name)
    with pytest.raises(PolicyDeniedError):
        registry.read_resource(metadata, "large.md")
