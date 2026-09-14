import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_installed import UIProcessIdentity, stream_snapshot, verified_ui_owner


def test_ui_cleanup_owns_the_exact_runtime_listener(tmp_path: Path) -> None:
    python = tmp_path / "managed runtime" / "python.exe"
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{python}" -I -m orqalis ui',
        "ParentProcessId": 10,
    }
    assert verified_ui_owner(record, python, 10) == 20


def test_ui_cleanup_owns_windows_venv_redirector_parent(tmp_path: Path) -> None:
    python = tmp_path / "managed runtime" / "Scripts" / "python.exe"
    base = tmp_path / "base Python" / "python.exe"
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{base}" -I -m orqalis ui',
        "ParentProcessId": 10,
        "ParentCommandLine": f'"{python}" -I -m orqalis ui',
        "GrandparentProcessId": 5,
    }
    assert verified_ui_owner(record, python, 5) == 10


@pytest.mark.parametrize("parent_id", [None, 9])
def test_ui_cleanup_rejects_runtime_listener_outside_foreground_cli(
    tmp_path: Path, parent_id: int | None
) -> None:
    python = tmp_path / "managed" / "python.exe"
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{python}" -I -m orqalis ui',
    }
    if parent_id is not None:
        record["ParentProcessId"] = parent_id
    with pytest.raises(AssertionError, match="not owned by the CLI"):
        verified_ui_owner(record, python, 10)


@pytest.mark.parametrize("grandparent_id", [None, 9])
def test_ui_cleanup_rejects_redirector_outside_foreground_cli(
    tmp_path: Path, grandparent_id: int | None
) -> None:
    python = tmp_path / "managed" / "Scripts" / "python.exe"
    base = tmp_path / "base" / "python.exe"
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{base}" -I -m orqalis ui',
        "ParentProcessId": 10,
        "ParentCommandLine": f'"{python}" -I -m orqalis ui',
    }
    if grandparent_id is not None:
        record["GrandparentProcessId"] = grandparent_id
    with pytest.raises(AssertionError, match="not owned by the CLI"):
        verified_ui_owner(record, python, 5)


@pytest.mark.parametrize("parent", ["base", "different-runtime", "missing-isolation", "absent"])
def test_ui_cleanup_rejects_unowned_base_interpreter(tmp_path: Path, parent: str) -> None:
    python = tmp_path / "managed" / "python.exe"
    base = tmp_path / "base" / "python.exe"
    parent_command = {
        "base": f'"{base}" -I -m orqalis ui',
        "different-runtime": f'"{tmp_path / "other" / "python.exe"}" -I -m orqalis ui',
        "missing-isolation": f'"{python}" -m orqalis serve',
        "absent": None,
    }[parent]
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{base}" -I -m orqalis ui',
        "ParentProcessId": 10,
        "ParentCommandLine": parent_command,
        "GrandparentProcessId": 5,
    }
    with pytest.raises(AssertionError, match="another runtime"):
        verified_ui_owner(record, python, 5)


def test_ui_cleanup_rejects_nonisolated_listener_even_with_managed_parent(tmp_path: Path) -> None:
    python = tmp_path / "managed" / "python.exe"
    record: UIProcessIdentity = {
        "ProcessId": 20,
        "CommandLine": f'"{tmp_path / "base" / "python.exe"}" -m orqalis serve',
        "ParentProcessId": 10,
        "ParentCommandLine": f'"{python}" -I -m orqalis ui',
        "GrandparentProcessId": 5,
    }
    with pytest.raises(AssertionError, match="not the isolated"):
        verified_ui_owner(record, python, 5)


class ReplayStream:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = iter(messages)

    async def recv(self) -> str:
        return json.dumps(next(self.messages))


def test_installed_stream_accepts_replay_before_snapshot() -> None:
    stream = ReplayStream(
        [
            {"type": "events", "events": [{"sequence": 1}, {"sequence": 2}]},
            {"type": "events", "events": [{"sequence": 3}]},
            {"type": "snapshot", "snapshot": {"run": {"id": "run"}, "last_event_sequence": 3}},
        ]
    )
    _, cursor = asyncio.run(stream_snapshot(stream, "run", 0))
    assert cursor == 3


def test_installed_stream_accepts_reconnect_without_replay() -> None:
    stream = ReplayStream(
        [{"type": "snapshot", "snapshot": {"run": {"id": "run"}, "last_event_sequence": 3}}]
    )
    _, cursor = asyncio.run(stream_snapshot(stream, "run", 3))
    assert cursor == 3


@pytest.mark.parametrize("sequences", [[2, 1], [2, 2], [1]])
def test_installed_stream_rejects_out_of_order_or_duplicate_events(
    sequences: list[int],
) -> None:
    stream = ReplayStream(
        [{"type": "events", "events": [{"sequence": sequence} for sequence in sequences]}]
    )
    with pytest.raises(AssertionError):
        asyncio.run(stream_snapshot(stream, "run", 1))


def test_installed_stream_rejects_snapshot_ahead_of_replayed_events() -> None:
    stream = ReplayStream(
        [{"type": "snapshot", "snapshot": {"run": {"id": "run"}, "last_event_sequence": 3}}]
    )
    with pytest.raises(AssertionError, match="Snapshot disagrees"):
        asyncio.run(stream_snapshot(stream, "run", 2))
