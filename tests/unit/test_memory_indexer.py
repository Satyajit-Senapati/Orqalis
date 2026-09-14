import pytest

from orqalis.memory.indexing import DeterministicMemoryIndexer


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.production",
        "secrets/config.json",
        "credentials.json",
        "node_modules/file.ts",
        ".orqalis/transcript.md",
        "private_key.txt",
    ],
)
def test_sensitive_paths_excluded(path: str) -> None:
    assert not DeterministicMemoryIndexer().allows(path)


def test_binary_large_invalid_and_private_contents_excluded() -> None:
    indexer = DeterministicMemoryIndexer()
    for content in [
        b"\x00binary",
        b"x" * 256001,
        b"\xff\xfe",
        b"-----BEGIN PRIVATE KEY-----",
        b"chain_of_thought: private",
    ]:
        assert indexer.index("README.md", content) is None


def test_source_scanner_does_not_store_literals_or_execute() -> None:
    result = DeterministicMemoryIndexer().index(
        "auth.py", b'password = "private"\ndef validate(): pass\n'
    )
    assert result
    assert "validate" in result.summary
    assert "private" not in result.summary


@pytest.mark.parametrize(
    ("path", "category", "role"),
    [
        ("docs/domain-rules.md", "domain", "documentation"),
        ("docs/known-issues.md", "known_issue", "documentation"),
        ("CONTRIBUTING.md", "convention", "documentation"),
        ("docs/adr/0001-storage.md", "decision", "documentation"),
        ("docs/architecture.md", "architecture", "documentation"),
        ("docs/address.md", "architecture", "documentation"),
        ("build.gradle", "repository_map", "build_manifest"),
        ("build.gradle.kts", "repository_map", "build_manifest"),
        ("go.mod", "repository_map", "build_manifest"),
        ("pom.xml", "repository_map", "build_manifest"),
    ],
)
def test_memory_categories_and_supported_build_manifests(
    path: str, category: str, role: str
) -> None:
    indexed = DeterministicMemoryIndexer().index(path, b"Source-backed project knowledge")
    assert indexed is not None
    assert indexed.memory_type == category
    assert indexed.role == role


@pytest.mark.parametrize("kind", ["EC", "DSA", "OPENSSH", "ENCRYPTED", "RSA"])
def test_private_key_variants_are_excluded_before_excerpting(kind: str) -> None:
    content = ("public context\n" * 600 + f"-----BEGIN {kind} PRIVATE KEY-----\nopaque").encode()
    assert DeterministicMemoryIndexer().index("docs/notes.md", content) is None
