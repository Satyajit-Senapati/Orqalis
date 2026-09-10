import hashlib
import tomllib
from pathlib import Path

from orqalis.domain.capabilities import LoadedSkill, SkillMetadata, ToolName
from orqalis.domain.errors import ConflictError, InputError, PolicyDeniedError
from orqalis.security.redaction import safe_diagnostic


class SkillRegistry:
    """Metadata is discoverable; instruction bodies load only after capability selection.

    Roots must be explicitly trusted by application configuration, never inferred
    from a provider response or an arbitrary repository instruction.
    """

    def __init__(self, roots: tuple[Path, ...]) -> None:
        self.entries: dict[tuple[str, str], tuple[SkillMetadata, Path, str]] = {}
        for root in roots:
            if root.is_symlink():
                raise PolicyDeniedError("Skill roots cannot be symlinks")
            resolved = root.resolve(strict=True)
            for metadata_path in sorted(resolved.glob("*/skill.toml")):
                if metadata_path.is_symlink() or metadata_path.parent.is_symlink():
                    raise PolicyDeniedError("Skill files cannot be symlinks")
                raw = self._read(metadata_path)
                metadata = SkillMetadata.model_validate(tomllib.loads(raw))
                key = (metadata.id, metadata.version)
                if key in self.entries:
                    raise ConflictError("Duplicate skill ID and version")
                self.entries[key] = (
                    metadata,
                    metadata_path.parent,
                    hashlib.sha256(raw.encode()).hexdigest(),
                )

    @staticmethod
    def _read(path: Path) -> str:
        if path.is_symlink() or path.stat().st_size > 100_000:
            raise PolicyDeniedError("Unsafe or oversized skill file")
        return path.read_text(encoding="utf-8")

    def discover(self) -> tuple[SkillMetadata, ...]:
        return tuple(item[0] for _, item in sorted(self.entries.items()))

    def load(self, metadata: SkillMetadata) -> LoadedSkill:
        registered, root, expected = self.entries[(metadata.id, metadata.version)]
        raw = self._read(root / "skill.toml")
        if metadata != registered or hashlib.sha256(raw.encode()).hexdigest() != expected:
            raise ConflictError("Skill metadata changed after discovery; rediscover explicitly")
        instructions = self._read(root / "instructions.md")
        if safe_diagnostic(instructions) != instructions:
            raise PolicyDeniedError("Skill contains private or sensitive instruction content")
        return LoadedSkill(
            metadata=metadata,
            instructions=instructions,
            content_hash=hashlib.sha256((raw + "\n" + instructions).encode()).hexdigest(),
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
            and (not metadata.applicable_when or set(metadata.applicable_when) & set(tags))
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
