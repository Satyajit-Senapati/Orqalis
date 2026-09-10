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
