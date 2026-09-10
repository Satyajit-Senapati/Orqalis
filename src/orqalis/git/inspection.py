from pathlib import PurePosixPath

from orqalis.domain.project import RepositoryProfile

_LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".java": "Java",
    ".rs": "Rust",
    ".go": "Go",
    ".cs": "C#",
}
_MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
}
_INSTRUCTIONS = {"AGENTS.md", "CLAUDE.md", "copilot-instructions.md"}


def inspect_paths(paths: tuple[str, ...]) -> RepositoryProfile:
    return RepositoryProfile(
        languages=tuple(
            sorted(
                {
                    _LANGUAGES[PurePosixPath(path).suffix]
                    for path in paths
                    if PurePosixPath(path).suffix in _LANGUAGES
                }
            )
        ),
        build_manifests=tuple(path for path in paths if PurePosixPath(path).name in _MANIFESTS),
        test_paths=tuple(
            path
            for path in paths
            if "tests" in PurePosixPath(path).parts
            or PurePosixPath(path).name.startswith("test_")
            or ".test." in PurePosixPath(path).name
        ),
        instruction_paths=tuple(
            path for path in paths if PurePosixPath(path).name in _INSTRUCTIONS
        ),
    )
