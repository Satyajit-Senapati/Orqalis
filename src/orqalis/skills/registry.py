import hashlib
import tomllib
from pathlib import Path, PurePosixPath

from orqalis.domain.capabilities import LoadedSkill, SkillMetadata, SkillResource, ToolName
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.git.service import validate_relative_path
from orqalis.persistence.filesystem.io import ensure_no_filesystem_links
from orqalis.security.redaction import safe_diagnostic
from orqalis.skills.markdown import parse_skill_markdown


class SkillRegistry:
    """Metadata is discoverable; instruction bodies load only after capability selection.

    Roots must be explicitly trusted by application configuration, never inferred
    from a provider response or an arbitrary repository instruction.
    """

    def __init__(self, roots: tuple[Path, ...]) -> None:
        self.entries: dict[tuple[str, str], tuple[SkillMetadata, Path, str]] = {}
        self._manifests: dict[tuple[str, str], Path] = {}
        self._resource_hashes: dict[tuple[str, str, str], str] = {}
        self._instruction_hashes: dict[tuple[str, str], str] = {}
        for root in roots:
            resolved = ensure_no_filesystem_links(root).resolve(strict=True)
            paths = sorted((*resolved.glob("*/skill.toml"), *resolved.glob("*/SKILL.md")))
            for metadata_path in paths:
                raw = self._read(metadata_path)
                if metadata_path.name == "SKILL.md":
                    if (metadata_path.parent / "skill.toml").exists():
                        raise ConflictError("Skill directory must use one manifest format")
                    metadata, _ = parse_skill_markdown(raw, metadata_path.parent)
                else:
                    metadata = SkillMetadata.model_validate(tomllib.loads(raw))
                if safe_diagnostic(metadata.model_dump_json()) != metadata.model_dump_json():
                    raise PolicyDeniedError("Skill contains private or sensitive metadata")
                key = (metadata.id, metadata.version)
                if key in self.entries:
                    raise ConflictError("Duplicate skill ID and version")
                self.entries[key] = (metadata, metadata_path.parent, self._hash(raw))
                self._manifests[key] = metadata_path

    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _read(path: Path) -> str:
        path = ensure_no_filesystem_links(path)
        if not path.is_file() or path.stat().st_size > 100_000:
            raise PolicyDeniedError("Unsafe or oversized skill file")
        with path.open(encoding="utf-8") as handle:
            raw = handle.read(100_001)
        if len(raw.encode("utf-8")) > 100_000:
            raise PolicyDeniedError("Unsafe or oversized skill file")
        return raw

    def discover(self) -> tuple[SkillMetadata, ...]:
        return tuple(item[0] for _, item in sorted(self.entries.items()))

    def load(self, metadata: SkillMetadata) -> LoadedSkill:
        key = (metadata.id, metadata.version)
        if key not in self.entries:
            raise InputError("Skill was not discovered in a trusted root")
        registered, root, expected = self.entries[key]
        manifest = self._manifests[key]
        raw = self._read(manifest)
        if metadata != registered or self._hash(raw) != expected:
            raise ConflictError("Skill metadata changed after discovery; rediscover explicitly")
        if manifest.name == "SKILL.md":
            _, instructions = parse_skill_markdown(raw, root)
        else:
            instructions = self._read(root / "instructions.md")
        if safe_diagnostic(instructions) != instructions:
            raise PolicyDeniedError("Skill contains private or sensitive instruction content")
        digest = self._hash(raw + "\n" + instructions)
        previous = self._instruction_hashes.setdefault(key, digest)
        if previous != digest:
            raise ConflictError(
                "Skill instructions changed after activation; rediscover explicitly"
            )
        return LoadedSkill(metadata=metadata, instructions=instructions, content_hash=digest)

    def read_resource(self, metadata: SkillMetadata, relative_path: str) -> SkillResource:
        """Read a bounded text resource on demand, never execute scripts or traverse links."""
        self.load(metadata)
        validate_relative_path(relative_path)
        root = self.entries[(metadata.id, metadata.version)][1]
        target = ensure_no_filesystem_links(root.joinpath(*PurePosixPath(relative_path).parts))
        if not target.resolve().is_relative_to(root.resolve()):
            raise PolicyDeniedError("Skill resource must remain inside the trusted skill")
        try:
            content = self._read(target)
        except (OSError, UnicodeError):
            raise InputError("Skill resource must be an existing UTF-8 text file") from None
        if safe_diagnostic(content) != content:
            raise PolicyDeniedError("Skill resource contains private or sensitive content")
        digest = self._hash(content)
        key = (metadata.id, metadata.version, relative_path)
        if self._resource_hashes.setdefault(key, digest) != digest:
            raise ConflictError("Skill resource changed after activation; rediscover explicitly")
        return SkillResource(
            skill_id=metadata.id,
            version=metadata.version,
            path=relative_path,
            content=content,
            content_hash=digest,
        )

    def select(
        self,
        required: tuple[str, ...],
        tools: tuple[ToolName, ...],
        tags: tuple[str, ...] = (),
        built_in: tuple[str, ...] = (),
        pins: dict[str, str] | None = None,
    ) -> tuple[LoadedSkill, ...]:
        uncovered = set(required) - set(built_in)
        available = [
            metadata
            for metadata in self.discover()
            if set(metadata.required_tools) <= set(tools)
            and (
                not metadata.applicable_when
                or {tag.casefold() for tag in metadata.applicable_when}
                & {tag.casefold() for tag in tags}
            )
            and (not pins or metadata.id not in pins or pins[metadata.id] == metadata.version)
        ]
        selected = []
        while uncovered:
            candidates = [item for item in available if uncovered & set(item.capabilities)]
            if not candidates:
                raise InputError("No permitted skill set covers the required capabilities")
            chosen = sorted(
                candidates,
                key=lambda item: (
                    -len(uncovered & set(item.capabilities)),
                    len(item.required_tools),
                    item.id,
                    tuple(-int(part) for part in item.version.split(".")),
                ),
            )[0]
            selected.append(self.load(chosen))
            uncovered -= set(chosen.capabilities)
            available = [item for item in available if item.id != chosen.id]
        return tuple(selected)
