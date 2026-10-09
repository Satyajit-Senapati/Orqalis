import hashlib
from pathlib import Path
from typing import Any, BinaryIO, Self, cast
from uuid import uuid4

import pytest

from orqalis.delivery.guardian import ChangeGuardian
from orqalis.domain.delivery import DeliveryPolicy, ReviewedTestChange
from orqalis.domain.errors import PolicyDeniedError
from orqalis.execution.review import workspace_digest
from orqalis.git.service import LocalGitService
from tests.unit.test_guardian import workspace


@pytest.mark.parametrize(
    "body",
    [
        "def test_answer():\n    pass\n",
        "import pytest\npytestmark = pytest.mark.skip\ndef test_answer():\n    assert 42 == 42\n",
        "def check():\n    assert 42 == 42\ndef test_answer():\n    check()\n",
        "import pytest\n@pytest.mark.skip\ndef test_answer():\n    assert 42 == 42\n",
        'import pytest\ndef test_answer():\n    pytest.xfail("temporary")\n    assert 42 == 42\n',
    ],
)
def test_guardian_blocks_weakened_test_and_requires_exact_review(
    git_repo: Path,
    body: str,
) -> None:
    path = "tests/test_main.py"
    target = git_repo / path
    binding = workspace(git_repo, ("tests/*",))
    target.write_text(body)
    guardian = ChangeGuardian(LocalGitService())
    report = guardian.inspect(binding, DeliveryPolicy(), uuid4(), "implementation")
    assert not report.passed and any(f.category == "test_reduction" for f in report.findings)
    approved = DeliveryPolicy(
        reviewed_test_changes=(
            ReviewedTestChange(
                path=path,
                old_hash=report.changes[0].old_hash or "",
                new_hash=hashlib.sha256(target.read_bytes()).hexdigest(),
            ),
        )
    )
    assert guardian.inspect(binding, approved, uuid4(), "implementation").passed
    target.write_text(body + "# new unreviewed content\n")
    assert not guardian.inspect(binding, approved, uuid4(), "implementation").passed


def test_assertions_can_be_added_without_test_exception(git_repo: Path) -> None:
    binding = workspace(git_repo, ("tests/*",))
    target = git_repo / "tests/test_main.py"
    target.write_text(target.read_text() + "    assert 43 != 42\n")
    assert (
        ChangeGuardian(LocalGitService())
        .inspect(binding, DeliveryPolicy(), uuid4(), "implementation")
        .passed
    )


def test_oversized_change_is_rejected_before_content_allocation(
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = workspace(git_repo, ("*",))
    target = git_repo / "huge.bin"
    with target.open("wb") as stream:
        stream.truncate(10_000_001)
    original = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        assert self != target, "Oversize file must not be opened to read contents"
        return original(self, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(Path, "open", guarded_open)
    report = ChangeGuardian(LocalGitService()).inspect(binding, DeliveryPolicy(), uuid4(), "final")
    assert not report.passed and report.tree_hash == "unverified"
    assert any(f.category == "unsafe_path" for f in report.findings)


def test_default_delivery_policy_keeps_legacy_fingerprints() -> None:
    assert "reviewed_test_changes" not in DeliveryPolicy().model_dump(mode="json")
    assert "reviewed_test_changes" not in DeliveryPolicy().model_dump_json()


def test_integrity_handles_unittest_and_changed_skip_conditions() -> None:
    from orqalis.delivery.test_integrity import test_weakening

    assert test_weakening(
        "class Check:\n def testValue(self): self.assertEqual(1, 1)\n",
        "class Check:\n def testValue(self): pass\n",
    )
    assert test_weakening(
        "@pytest.mark.skipif(False, reason='check')\ndef test_value(): assert True\n",
        "@pytest.mark.skipif(True, reason='check')\ndef test_value(): assert True\n",
    )


@pytest.mark.parametrize("terms", [500, 5000])
def test_uninspectable_ast_complexity_fails_closed(terms: int) -> None:
    from orqalis.delivery.test_integrity import test_weakening

    before = "def test_value(): assert True\n"
    after = (
        "@pytest.mark.skipif(" + "+".join(["value"] * terms) + ")\ndef test_value(): assert True\n"
    )
    assert test_weakening(before, after)
    assert not test_weakening(after, before)


def test_syntax_disabled_tests_require_review_but_baseline_repairs_do_not() -> None:
    from orqalis.delivery.test_integrity import test_weakening

    valid = "def test_value(): assert True\n"
    invalid = "def test_value(): assert (\n"
    assert test_weakening(valid, invalid)
    assert not test_weakening(invalid, valid)


def test_module_skip_collections_and_scope_changes_require_review() -> None:
    from orqalis.delivery.test_integrity import test_weakening

    test = "def test_value(): assert True\n"
    assert test_weakening(test, "pytestmark = [pytest.mark.skip]\n" + test)
    assert test_weakening("@pytest.mark.skip\n" + test, "pytestmark = pytest.mark.skip\n" + test)
    assert not test_weakening(test, "pytestmark = pytest.mark.asyncio\n" + test)


@pytest.mark.parametrize(
    "check",
    [
        "with pytest.raises(ValueError):\n        parse('invalid')",
        "with pytest.warns(UserWarning):\n        warn()",
        "pytest.fail('required failure')",
        "with raises(ValueError):\n        parse('invalid')",
    ],
)
def test_assertion_helper_removal_requires_review(check: str) -> None:
    from orqalis.delivery.test_integrity import test_weakening

    before = "def test_value():\n    " + check + "\n"
    assert test_weakening(before, "def test_value():\n    pass\n")
    assert not test_weakening(before, before + "    assert True\n")


@pytest.mark.parametrize("consumer", ["guardian", "workspace_digest"])
def test_growing_changed_file_is_bounded_after_size_check(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    limit = 10_000_000
    binding = workspace(git_repo, ("*",))
    target = git_repo / "growing.py"
    initial = b"value = 1\n"
    target.write_bytes(initial)
    original_open = Path.open
    opened_sizes: list[int] = []
    requested_sizes: list[int] = []
    returned_sizes: list[int] = []

    class CountedRead:
        def __init__(self, stream: BinaryIO) -> None:
            self.stream = stream

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: Any) -> None:
            self.stream.close()

        def read(self, size: int = -1) -> bytes:
            requested_sizes.append(size)
            assert size == limit + 1, "Review must never request an unbounded growing-file read"
            value = self.stream.read(size)
            returned_sizes.append(len(value))
            return value

    def grow_before_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        mode = args[0] if args else kwargs.get("mode", "r")
        if path != target or mode != "rb":
            return original_open(path, *args, **kwargs)
        # The consumer has just accepted stat().st_size. Grow at this exact
        # barrier; a deadline or independently scheduled writer is unnecessary.
        opened_sizes.append(path.stat().st_size)
        assert opened_sizes == [len(initial)]
        with original_open(path, "r+b") as growing:
            growing.truncate(limit + 1)
        return CountedRead(cast(BinaryIO, original_open(path, *args, **kwargs)))

    monkeypatch.setattr(Path, "open", grow_before_open)
    if consumer == "guardian":
        report = ChangeGuardian(LocalGitService()).inspect(
            binding, DeliveryPolicy(), uuid4(), "final"
        )
        assert not report.passed and report.tree_hash == "unverified"
        assert any(f.category == "unsafe_path" for f in report.findings)
    else:
        with pytest.raises(PolicyDeniedError, match="exceeds review limits"):
            workspace_digest(binding, LocalGitService())
    assert opened_sizes == [len(initial)]
    assert requested_sizes == returned_sizes == [limit + 1]
