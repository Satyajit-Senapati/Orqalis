"""Observe durable-memory workflow reads without claiming autonomous task success.

This compares current-version workflows, not release performance. --smoke verifies
correctness/read accounting and omits timings; use --repeat only in a quiet capture window.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import codecs
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import ExitStack
from functools import partial
from pathlib import Path
from typing import IO, Any
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def environment() -> dict[str, str]:
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("ORQALIS_", "PYTHON", "PYTEST", "GIT_"))
    }
    result.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_NO_REPLACE_OBJECTS="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    return result


def git(root: Path, *arguments: str) -> str:
    configured = {
        **environment(),
        "GIT_AUTHOR_NAME": "Memory Workflow Fixture",
        "GIT_AUTHOR_EMAIL": "memory@example.invalid",
        "GIT_COMMITTER_NAME": "Memory Workflow Fixture",
        "GIT_COMMITTER_EMAIL": "memory@example.invalid",
    }
    return subprocess.run(
        [
            "git",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(root),
            *arguments,
        ],
        env=configured,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def source_fingerprint(root: Path) -> dict[str, Any]:
    paths = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "src/orqalis").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    paths += [name for name in ("pyproject.toml", "uv.lock") if (root / name).is_file()]
    hasher = hashlib.sha256()
    for name in sorted(paths):
        hasher.update(name.encode() + b"\0" + (root / name).read_bytes() + b"\0")
    return {"sha256": hasher.hexdigest(), "files": sorted(paths)}


class CountedReader:
    """Count returned data without changing binary read behavior.

    Binary bytes are decoded incrementally only for character accounting. Invalid
    bytes and incomplete UTF-8 sequences are explicit counters, never read errors.
    """

    def __init__(self, stream: IO[Any], stats: dict[str, int]) -> None:
        self.stream: Any = stream
        self.stats = stats
        self.decoder = codecs.getincrementaldecoder("utf-8")("surrogateescape")
        self.pending_bytes = 0
        for key in ("binary_undecodable_bytes", "binary_pending_bytes"):
            self.stats.setdefault(key, 0)

    def _binary_chars(self, value: bytes, *, final: bool = False) -> None:
        text = self.decoder.decode(value, final=final)
        invalid = sum(0xDC80 <= ord(char) <= 0xDCFF for char in text)
        self.stats["returned_chars"] += len(text) - invalid
        self.stats["binary_undecodable_bytes"] += invalid
        pending = len(self.decoder.getstate()[0])
        self.stats["binary_pending_bytes"] += pending - self.pending_bytes
        self.pending_bytes = pending

    def _record(self, value: str | bytes) -> str | bytes:
        self.stats["read_operations"] += 1
        if isinstance(value, bytes):
            self.stats["returned_utf8_bytes"] += len(value)
            self._binary_chars(value)
        else:
            self.stats["returned_chars"] += len(value)
            self.stats["returned_utf8_bytes"] += len(value.encode("utf-8", "surrogatepass"))
        return value

    def read(self, *args: Any, **kwargs: Any) -> Any:
        return self._record(self.stream.read(*args, **kwargs))

    def readline(self, *args: Any, **kwargs: Any) -> Any:
        return self._record(self.stream.readline(*args, **kwargs))

    def read1(self, *args: Any, **kwargs: Any) -> Any:
        return self._record(self.stream.read1(*args, **kwargs))

    def readinto(self, buffer: Any) -> Any:
        count = self.stream.readinto(buffer)
        if count is not None:
            self._record(bytes(memoryview(buffer).cast("B")[:count]))
        return count

    def readinto1(self, buffer: Any) -> Any:
        count = self.stream.readinto1(buffer)
        if count is not None:
            self._record(bytes(memoryview(buffer).cast("B")[:count]))
        return count

    def readlines(self, *args: Any, **kwargs: Any) -> Any:
        values = self.stream.readlines(*args, **kwargs)
        self._record(
            b"".join(values) if values and isinstance(values[0], bytes) else "".join(values)
        )
        return values

    def seek(self, *args: Any, **kwargs: Any) -> Any:
        position = self.stream.seek(*args, **kwargs)
        self._binary_chars(b"", final=True)
        self.decoder.reset()
        return position

    def close(self) -> None:
        self._binary_chars(b"", final=True)
        self.stream.close()

    def __iter__(self) -> CountedReader:
        return self

    def __next__(self) -> Any:
        value = self.readline()
        if not value:
            raise StopIteration
        return value

    def __enter__(self) -> CountedReader:
        return self

    def __exit__(self, *args: Any) -> Any:
        self._binary_chars(b"", final=True)
        return self.stream.__exit__(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


class ReadProbe:
    def __init__(self, root: Path, source_paths: list[str]) -> None:
        self.root = root.resolve()
        self.source_paths = set(source_paths)
        self.rows: dict[str, dict[str, Any]] = {}
        self.graph_refreshes = 0
        self.parsed_files = 0
        self.cache_hits = 0
        self.stack = ExitStack()

    def __enter__(self) -> ReadProbe:
        from orqalis.graph.engine import ProjectGraphEngine
        from orqalis.persistence.filesystem import io as filesystem_io

        original_open = Path.open
        original_refresh = ProjectGraphEngine.refresh
        original_verify = getattr(filesystem_io, "_verify_temporary", None)

        def counted(stream: IO[Any], path: Path, mode: str) -> Any:
            if "r" not in mode and "+" not in mode:
                return stream
            try:
                relative = path.absolute().relative_to(self.root).as_posix()
            except ValueError:
                return stream
            kind = (
                "source"
                if relative in self.source_paths
                else "memory"
                if relative.startswith(".orqalis/memory/records/")
                else "metadata"
            )
            row = self.rows.setdefault(
                relative,
                {
                    "kind": kind,
                    "open_operations": 0,
                    "read_operations": 0,
                    "returned_chars": 0,
                    "returned_utf8_bytes": 0,
                },
            )
            row["open_operations"] += 1
            return CountedReader(stream, row)

        def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
            stream = original_open(path, *args, **kwargs)
            return counted(stream, path, args[0] if args else kwargs.get("mode", "r"))

        def canonical_open(path: Any, *args: Any, **kwargs: Any) -> Any:
            # Caller owns the returned reader and closes it through CountedReader.
            stream = builtins.open(path, *args, **kwargs)  # noqa: SIM115
            return counted(stream, Path(path), args[0] if args else kwargs.get("mode", "r"))

        def verified(path: Path, stream: IO[Any], content: bytes) -> Any:
            # Observe the same logical validation read through its owned descriptor.
            # Readable-stream counts are not native file opens or physical disk I/O.
            assert original_verify is not None
            reader = counted(stream, path, "w+b")
            try:
                return original_verify(path, reader, content)
            finally:
                if isinstance(reader, CountedReader):
                    reader._binary_chars(b"", final=True)

        def refreshed(engine: Any) -> Any:
            self.graph_refreshes += 1
            result = original_refresh(engine)
            self.parsed_files += result.metrics.processed_files
            self.cache_hits += result.metrics.cache_hits
            return result

        self.stack.enter_context(patch.object(Path, "open", opened))
        self.stack.enter_context(patch.object(filesystem_io, "open", canonical_open, create=True))
        if original_verify is not None:
            self.stack.enter_context(patch.object(filesystem_io, "_verify_temporary", verified))
        self.stack.enter_context(patch.object(ProjectGraphEngine, "refresh", refreshed))
        return self

    def __exit__(self, *args: Any) -> None:
        self.stack.close()

    def snapshot(self) -> dict[str, Any]:
        categories = {}
        for kind in ("source", "memory", "metadata"):
            rows = {
                name: dict(value)
                for name, value in sorted(self.rows.items())
                if value["kind"] == kind
            }
            categories[kind] = {
                key: sum(row[key] for row in rows.values())
                for key in (
                    "open_operations",
                    "read_operations",
                    "returned_chars",
                    "returned_utf8_bytes",
                    "binary_undecodable_bytes",
                    "binary_pending_bytes",
                )
            }
            categories[kind].update(unique_files=len(rows), paths=list(rows), files=rows)
        return {
            "categories": categories,
            "graph_refresh_calls": self.graph_refreshes,
            "graph_processed_files": self.parsed_files,
            "graph_cache_hits": self.cache_hits,
        }


def fixture_symbol(case: dict[str, Any]) -> dict[str, Any]:
    """Independent Python AST oracle over fixed input, never source execution."""
    path, name = case["target_path"], case["symbol"]
    data = case["source_files"][path].encode("utf-8")
    functions = [
        node
        for node in ast.parse(data).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    assert len(functions) == 1
    node = functions[0]
    assert node.end_lineno is not None and node.end_col_offset is not None
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[: node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[: node.end_lineno - 1])) + node.end_col_offset
    return {
        "id": "symbol:" + digest("\x1f".join(("symbol", path, name, "FUNCTION")).encode())[:24],
        "name": name,
        "file_path": path,
        "source_hash": digest(data),
        "byte_start": start,
        "byte_end": end,
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "body_sha256": digest(data[start:end]),
    }


class WitnessOracle:
    """Stage-specific identity/content checks against frozen fixture inputs.

    Navigation pages expose no full-record digest. We verify each returned slice
    against the canonical fixture and label its digest separately from the oracle's
    full-record digest; a partial response is never claimed to contain a full body.
    """

    def __init__(self, case: dict[str, Any], fixture: dict[str, Any]) -> None:
        self.case, self.fixture = case, fixture
        self.records = fixture["_active_records"]
        self.symbol = fixture["expected_symbol"]

    def _preview(self, item: dict[str, Any]) -> None:
        expected = self.records[item["id"]]
        assert item["lifecycle"] == "ACTIVE" and item["freshness"] == "FRESH"
        assert item["superseded_by"] is None
        for key in ("title", "category"):
            assert item[key] == expected[key]
        assert item["content_chars"] == len(expected["content"])
        assert item["references"] == expected["references"][:4]
        assert item["reference_count"] == len(expected["references"])
        assert (
            item["preview"] == " ".join((expected["summary"] or expected["content"]).split())[:160]
        )

    def _memory_evidence(
        self, identifier: str, content: str, offset: int, kind: str
    ) -> dict[str, Any]:
        expected = self.records[identifier]["content"]
        assert content == expected[offset : offset + len(content)]
        return {
            "kind": kind,
            "record_id": identifier,
            "lifecycle": "ACTIVE",
            "oracle_content_sha256": digest(expected.encode("utf-8")),
            "returned_content_sha256": digest(content.encode("utf-8")),
            "offset": offset,
            "content_chars": len(content),
            "witnesses": ["durable_fact"]
            if identifier == self.fixture["detail_id"] and self.case["fact"] in content
            else [],
        }

    def _record(self, item: dict[str, Any], *, context: bool = False) -> dict[str, Any]:
        record = item["record"]
        assert record == self.records[record["id"]]
        assert item["freshness"] == "FRESH"
        if not context:
            assert item["lifecycle"] == "ACTIVE" and item["superseded_by"] is None
            assert item["changed_sources"] == []
        return self._memory_evidence(record["id"], record["content"], 0, "active_memory_body")

    def _symbol(self, value: dict[str, Any]) -> None:
        for key in ("id", "name", "file_path", "source_hash", "line_start", "line_end"):
            assert value[key] == self.symbol[key], (key, value[key], self.symbol[key])
        assert value["kind"] == "FUNCTION" and value["language"] == "Python"
        for key in ("byte_start", "byte_end"):
            assert type(value["metadata"][key]) is int
            assert value["metadata"][key] == self.symbol[key]

    def _exclude_history(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                # The exact canonical successor may identify its predecessor as
                # provenance. This does not return the predecessor as active text.
                if key == "supersedes" and value == self.records[self.fixture["detail_id"]]:
                    assert child == self.fixture["predecessor_id"]
                    continue
                self._exclude_history(key)
                self._exclude_history(child)
        elif isinstance(value, list):
            for child in value:
                self._exclude_history(child)
        elif isinstance(value, str):
            assert self.case["old_fact"] not in value, "Obsolete fact in active response"
            assert self.fixture["predecessor_id"] not in value, "Predecessor in active response"

    def verify(
        self,
        name: str,
        value: Any,
        *,
        record_id: str | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        if name == "project_context":
            evidence.extend(self._record(item, context=True) for item in value["memory"])
            for item in value["memory_discovery"]:
                self._preview(item)
        elif name == "all_active_memory":
            identifiers = [item["record"]["id"] for item in value]
            assert len(identifiers) == len(set(identifiers))
            assert set(identifiers) == set(self.records)
            evidence.extend(self._record(item) for item in value)
        elif name == "discover_project_memory":
            assert len(value["items"]) == 1
            assert value["items"][0]["id"] == self.fixture["overview_id"]
            self._preview(value["items"][0])
        elif name in {"get_project_memory_overview", "get_project_memory_detail"}:
            assert record_id is not None and offset is not None
            assert value["item"]["id"] == record_id and value["offset"] == offset
            self._preview(value["item"])
            expected = self.records[record_id]
            assert value["source"] == expected["source"]
            assert value["verified_commit"] == expected["verified_commit"]
            assert value["references"] == expected["references"]
            content = value["content"]
            assert 0 <= offset <= len(expected["content"])
            end = offset + len(content)
            assert end <= len(expected["content"])
            assert value["next_offset"] == (end if end < len(expected["content"]) else None)
            evidence.append(self._memory_evidence(record_id, content, offset, "active_memory_page"))
        elif name == "read_all_source":
            assert value == self.case["source_files"], "Source contents/path inventory differ"
            path = self.case["target_path"]
            assert digest(value[path].encode("utf-8")) == self.symbol["source_hash"]
            assert self.case["source_witness"] in value[path]
            evidence.append(
                {
                    "kind": "source_file",
                    "path": path,
                    "source_hash": self.symbol["source_hash"],
                    "witnesses": ["source_branch"],
                }
            )
        elif name == "find_project_symbols":
            assert len(value["symbols"]) == 1 and not value["truncated"]
            assert not value["source_coverage"]["extraction_truncated"]
            self._symbol(value["symbols"][0])
        elif name == "get_symbol_body":
            self._symbol(value["symbol"])
            assert value["source_hash"] == self.symbol["source_hash"]
            assert not value["source_coverage"]["extraction_truncated"]
            data = self.case["source_files"][self.symbol["file_path"]].encode("utf-8")
            expected_body = data[self.symbol["byte_start"] : self.symbol["byte_end"]]
            assert value["content"] == expected_body.decode("utf-8")
            assert digest(value["content"].encode("utf-8")) == self.symbol["body_sha256"]
            assert self.case["source_witness"] in value["content"]
            evidence.append(
                {
                    "kind": "source_symbol_body",
                    **self.symbol,
                    "witnesses": ["source_branch"],
                }
            )
        else:
            raise AssertionError(f"No typed evidence contract for stage {name!r}")
        self._exclude_history(value)
        return evidence


class Workflow:
    def __init__(
        self, case: dict[str, Any], fixture: dict[str, Any], probe: ReadProbe, timings: bool
    ) -> None:
        self.probe, self.timings = probe, timings
        self.oracle = WitnessOracle(case, fixture)
        self.started = time.perf_counter()
        self.witnesses = {"durable_fact": case["fact"], "source_branch": case["source_witness"]}
        self.first_seen: dict[str, float | None] = {}
        self.stages: list[dict[str, Any]] = []

    def call(
        self,
        name: str,
        action: Callable[[], Any],
        *,
        budget: int | None = None,
        returned_ids: Callable[[Any], list[str]] | None = None,
        record_id: str | None = None,
        offset: int | None = None,
    ) -> Any:
        started = time.perf_counter()
        value = action()
        payload = (
            value.model_dump_json()
            if hasattr(value, "model_dump_json")
            else json.dumps(value, ensure_ascii=False)
        )
        assert budget is None or len(payload) <= budget, (name, len(payload), budget)
        evidence = self.oracle.verify(name, json.loads(payload), record_id=record_id, offset=offset)
        elapsed = (time.perf_counter() - self.started) * 1000
        matches = sorted({witness for item in evidence for witness in item["witnesses"]})
        for key in matches:
            self.first_seen.setdefault(key, elapsed if self.timings else None)
        self.stages.append(
            {
                "operation": name,
                "response_chars": len(payload),
                "response_utf8_bytes": len(payload.encode("utf-8")),
                "response_sha256": digest(payload.encode("utf-8")),
                "budget_chars": budget,
                "budget_pass": budget is None or len(payload) <= budget,
                "matched_witnesses": matches,
                "verified_evidence": evidence,
                "active_history_exclusion_pass": True,
                "returned_ids": returned_ids(value) if returned_ids else [],
                "duration_ms": (time.perf_counter() - started) * 1000 if self.timings else None,
                "elapsed_ms": elapsed if self.timings else None,
                "cumulative_reads": self.probe.snapshot(),
            }
        )
        return value

    def finish(self, name: str, *, require_source: bool) -> dict[str, Any]:
        required = set(self.witnesses) if require_source else {"durable_fact"}
        assert required <= self.first_seen.keys(), (name, required, self.first_seen)
        observed_times = [value for value in self.first_seen.values() if value is not None]
        required_times = [
            value for key, value in self.first_seen.items() if key in required and value is not None
        ]
        return {
            "workflow": name,
            "fresh_sdk": True,
            "stages": self.stages,
            "reads": self.probe.snapshot(),
            "matched_witnesses": sorted(self.first_seen),
            "witness_recall": len(required & self.first_seen.keys()) / len(required),
            "required_witnesses": sorted(required),
            "exact_answer_pass": True,
            "response_chars": sum(stage["response_chars"] for stage in self.stages),
            "response_utf8_bytes": sum(stage["response_utf8_bytes"] for stage in self.stages),
            "first_witness_ms": min(observed_times) if observed_times else None,
            "durable_fact_ms": self.first_seen.get("durable_fact"),
            "all_required_witnesses_ms": max(required_times) if required_times else None,
            "total_duration_ms": (time.perf_counter() - self.started) * 1000
            if self.timings
            else None,
        }


def install_fixture(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    from orqalis.memory.curated import CuratedMemoryStore, MemoryCategory, MemoryProvenance
    from orqalis.persistence.filesystem import ProjectLayout
    from orqalis.sdk import Orqalis

    root.mkdir()
    for relative, content in case["source_files"].items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    git(root, "init", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixed memory workflow fixture")
    sdk = Orqalis(root=root)
    project = sdk.initialize(root)
    store = CuratedMemoryStore(ProjectLayout(root))
    provenance = MemoryProvenance(type="user")
    if case["source_provenance"]:
        path = case["target_path"]
        provenance = MemoryProvenance(
            type="repository",
            paths=(path,),
            content_hashes={path: digest((root / path).read_bytes())},
        )
    old = store.new_record(
        MemoryCategory.DECISION, case["detail_title"], case["old_fact"], provenance
    )
    old_proposal = store.propose(old, "Record original reviewed convention")
    store.approve(old_proposal.id, "Accepted original fixture convention")
    sections = list(case["notes"])
    sections.insert(2, case["fact"])
    body = "\n\n".join(f"### Note {index + 1}\n{text}" for index, text in enumerate(sections))
    detail = store.new_record(
        MemoryCategory.DECISION,
        case["detail_title"],
        body,
        provenance,
        summary=case["detail_summary"],
    )
    proposal = store.propose(detail, "Record accepted replacement", supersedes=old.id)
    approved = store.approve(proposal.id, "Reviewed the current source and operating decision")
    overview = store.new_record(
        MemoryCategory.ARCHITECTURE,
        case["overview_title"],
        case["overview_body"],
        MemoryProvenance(type="user"),
        summary=case["overview_summary"],
        references=(detail.id,),
    )
    store.approve(
        store.propose(overview, "Connect orientation to reviewed detail").id, "Reviewed links"
    )
    for title, content in (
        (
            "Release packaging",
            (
                "Build artifacts contain the license notice and a versioned manifest. Verify "
                "their contents before publishing a release."
            ),
        ),
        (
            "Accessibility review",
            (
                "Keyboard focus must remain visible in the administration interface. Capture "
                "a reproducible keyboard-navigation witness for a changed interaction."
            ),
        ),
    ):
        other = store.new_record(
            MemoryCategory.CONVENTIONS, title, content, MemoryProvenance(type="user")
        )
        store.approve(store.propose(other, "Record separate operating convention").id, "Accepted")
    assert case["fact"] not in "\n".join(case["source_files"].values())
    assert store.get(old.id).content == case["old_fact"]
    assert detail.id in {item.id for item in store.list()} and old.id not in {
        item.id for item in store.list()
    }
    active_records = {record.id: record.model_dump(mode="json") for record in store.list()}
    assert active_records[detail.id]["content"] == body
    assert active_records[overview.id]["content"] == case["overview_body"]
    sdk.close()
    return {
        "_active_records": active_records,
        "active_content_sha256": {
            key: digest(record["content"].encode("utf-8")) for key, record in active_records.items()
        },
        "expected_symbol": fixture_symbol(case),
        "project_id": str(project.id),
        "overview_id": overview.id,
        "detail_id": detail.id,
        "predecessor_id": old.id,
        "detail_content_chars": len(approved.record.content),
        "detail_content_utf8_bytes": len(approved.record.content.encode("utf-8")),
        "source_files": sorted(case["source_files"]),
        "source_provenance": case["source_provenance"],
    }


def read_pages(sdk: Any, flow: Workflow, record_id: str, budget: int, page_limit: int) -> None:
    offset = 0
    for _ in range(page_limit):
        page = flow.call(
            "get_project_memory_detail",
            partial(sdk.get_project_memory, record_id, offset, budget),
            budget=budget,
            returned_ids=lambda value: [value.item.id],
            record_id=record_id,
            offset=offset,
        )
        assert page.item.id == record_id and page.item.lifecycle == "ACTIVE"
        if page.next_offset is None:
            break
        assert page.next_offset > offset
        offset = page.next_offset


def all_memory(sdk: Any) -> list[dict[str, Any]]:
    return [value.model_dump(mode="json") for value in sdk.search_project_memory("", 100)]


def compare_workflows(
    root: Path,
    case: dict[str, Any],
    fixture: dict[str, Any],
    dataset: dict[str, Any],
    *,
    timings: bool,
    reverse_order: bool,
) -> list[dict[str, Any]]:
    from orqalis.sdk import Orqalis

    results = []
    budget = dataset["response_budget_chars"]
    order = ["full_rediscovery", "progressive_memory_then_symbol"]
    if reverse_order:
        order.reverse()
    remembered_id = fixture["detail_id"]
    for name in order:
        with ReadProbe(root, fixture["source_files"]) as probe:
            flow = Workflow(case, fixture, probe, timings)
            sdk = Orqalis(root=root)
            try:
                if name == "full_rediscovery":
                    flow.call(
                        "project_context",
                        partial(sdk.project_context, case["task"], dataset["context_budget_chars"]),
                        budget=dataset["context_budget_chars"],
                        returned_ids=lambda value: [
                            *(item.record.id for item in value.memory),
                            *(item.id for item in value.memory_discovery),
                        ],
                    )
                    flow.call(
                        "read_all_source",
                        lambda: {
                            path: (root / path).read_text(encoding="utf-8")
                            for path in fixture["source_files"]
                        },
                        returned_ids=lambda values: list(values),
                    )
                    flow.call(
                        "all_active_memory",
                        partial(all_memory, sdk),
                        returned_ids=lambda values: [value["record"]["id"] for value in values],
                    )
                else:
                    found = flow.call(
                        "discover_project_memory",
                        partial(sdk.discover_project_memory, case["discovery_query"], 1, budget),
                        budget=budget,
                        returned_ids=lambda value: [item.id for item in value.items],
                    )
                    assert len(found.items) == 1 and found.items[0].id == fixture["overview_id"]
                    overview = flow.call(
                        "get_project_memory_overview",
                        partial(sdk.get_project_memory, found.items[0].id, 0, budget),
                        budget=budget,
                        returned_ids=lambda value: [value.item.id],
                        record_id=fixture["overview_id"],
                        offset=0,
                    )
                    assert overview.references == (fixture["detail_id"],)
                    remembered_id = overview.references[0]
                    read_pages(sdk, flow, remembered_id, budget, dataset["detail_page_limit"])
                    memory_only = probe.snapshot()
                    assert memory_only["graph_refresh_calls"] == 0
                    found_symbols = flow.call(
                        "find_project_symbols",
                        partial(
                            sdk.find_project_symbols,
                            case["symbol"],
                            case["target_path"],
                            10,
                            dataset["symbol_budget_chars"],
                        ),
                        budget=dataset["symbol_budget_chars"],
                        returned_ids=lambda value: [node.id for node in value.symbols],
                    )
                    assert len(found_symbols.symbols) == 1
                    symbol = found_symbols.symbols[0]
                    assert symbol.source_hash
                    flow.call(
                        "get_symbol_body",
                        partial(
                            sdk.project_symbol_body,
                            symbol.id,
                            symbol.source_hash,
                            dataset["symbol_budget_chars"],
                        ),
                        budget=dataset["symbol_budget_chars"],
                        returned_ids=lambda value: [value.symbol.id, value.symbol.file_path],
                    )
            finally:
                sdk.close()
            result = flow.finish(name, require_source=True)
            result["retrieval"] = relevance(result, fixture, case["target_path"])
            assert result["retrieval"]["memory_recall"] == 1
            assert result["retrieval"]["source_recall"] == 1
            if name == "progressive_memory_then_symbol":
                result["memory_only_reads"] = memory_only
            results.append(result)
    # A new SDK receives only the explicit stable ID from the earlier reference read.
    with ReadProbe(root, fixture["source_files"]) as probe:
        flow = Workflow(case, fixture, probe, timings)
        sdk = Orqalis(root=root)
        try:
            read_pages(sdk, flow, remembered_id, budget, dataset["detail_page_limit"])
        finally:
            sdk.close()
        direct = flow.finish("restart_direct_memory", require_source=False)
        direct["retrieval"] = relevance(direct, fixture, None)
        assert direct["retrieval"]["memory_recall"] == 1
        assert direct["reads"]["graph_refresh_calls"] == 0
        results.append(direct)
    # History is checked independently; its body is not injected into active task context.
    restarted = Orqalis(root=root)
    try:
        historical = restarted.get_project_memory(fixture["predecessor_id"], 0, 4000)
        assert historical.item.lifecycle == "SUPERSEDED"
        assert historical.item.superseded_by == fixture["detail_id"]
        assert historical.content == case["old_fact"]
        assert restarted.get_project_memory(remembered_id, 0, 4000).item.lifecycle == "ACTIVE"
    finally:
        restarted.close()
    return results


def relevance(
    workflow: dict[str, Any], fixture: dict[str, Any], target_path: str | None
) -> dict[str, Any]:
    returned = {identifier for stage in workflow["stages"] for identifier in stage["returned_ids"]}
    memory = sorted(identifier for identifier in returned if identifier.startswith("MEM-"))
    sources = sorted(identifier for identifier in returned if identifier in fixture["source_files"])
    gold_memory = {fixture["detail_id"]}
    if target_path is not None:
        gold_memory.add(fixture["overview_id"])
    return {
        "definition": (
            "unique explicitly returned record IDs and source bodies; "
            "gold is fixed fixture task scope"
        ),
        "returned_memory_ids": memory,
        "returned_source_paths": sources,
        "gold_memory_ids": sorted(gold_memory),
        "gold_source_paths": [target_path] if target_path else [],
        "memory_recall": len(set(memory) & gold_memory) / len(gold_memory),
        "memory_precision": len(set(memory) & gold_memory) / len(memory) if memory else 0,
        "source_recall": float(target_path in sources) if target_path else None,
        "source_precision": (1 / len(sources) if target_path in sources else 0)
        if sources
        else None,
    }


def distribution(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "samples_ms": values,
        "median_ms": statistics.median(values),
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1],
    }


def worker(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source_root.resolve()
    sys.path.insert(0, str(source / "src"))
    import orqalis
    from orqalis.sdk import Orqalis

    assert Path(orqalis.__file__).resolve().is_relative_to(source / "src")
    if not hasattr(Orqalis, "discover_project_memory"):
        raise ValueError(
            "This current-version workflow comparison requires progressive memory APIs; "
            "it is not a release baseline benchmark"
        )
    initial_source = source_fingerprint(source)
    script_hash = digest(Path(__file__).read_bytes())
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    assert dataset["schema_version"] == 1 and dataset["cases"]
    assert len({case["id"] for case in dataset["cases"]}) == len(dataset["cases"])
    assert 1000 <= dataset["response_budget_chars"] <= 200000
    report: dict[str, Any] = {
        "schema_version": 1,
        "comparison_kind": "current_version_workflows",
        "label": args.label,
        "timings_enabled": not args.smoke,
        "release_baseline_measured": False,
        "less_selective_baseline": (
            "same current SDK: bounded context, every fixture source file, then all "
            "active curated records"
        ),
        "baseline_reference": "b8506f7d9c471516fe4b21c9caa735a7a7909af6 (not executed here)",
        "source": initial_source,
        "script_sha256": script_hash,
        "dataset_sha256": digest(dataset_bytes),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "isolated_python": bool(sys.flags.isolated),
            "repetitions": args.repeat,
            "dependencies": sorted(
                (dist.metadata.get("Name", ""), dist.version)
                for dist in importlib.metadata.distributions()
            ),
        },
        "measurement_policy": [
            (
                "Fixed illustrative engineering fixtures, typed active-memory identity/content "
                "and source-symbol path/hash/span witnesses; no model calls or autonomous "
                "engineering task-success claim. Partial page digests are distinct from full "
                "canonical fixture digests."
            ),
            (
                "Fresh SDK objects on every workflow and repetition, closed initializer, "
                "initialized warm graph/parser files; OS/interpreter caches may be warm."
            ),
            (
                "Two complete-answer workflows alternate order by repetition; restarted "
                "direct-ID memory reuse has a narrower declared witness target."
            ),
            (
                "Detail reads use a fixed page limit, never a stopping choice based on gold "
                "answer text. References are discovered from the returned overview."
            ),
            (
                "Source and memory metrics count actual Python Path.open and canonical "
                "filesystem open/read results under "
                "the fixture. Git/subprocess/kernel reads are excluded. Binary bytes are counted "
                "as returned and text as UTF-8 re-encoded bytes, not physical disk bytes. Binary "
                "characters are incrementally decoded; undecodable and pending bytes are explicit."
            ),
            (
                "Discovery scans canonical record bodies locally. Its smaller response is "
                "not a claim of fewer memory-file reads."
            ),
            (
                "Memory provenance freshness can hash named source files. Explicit symbol "
                "SDK calls each refresh the graph and can re-read the source inventory."
            ),
            (
                "Response caps apply individually to serialized bounded API responses; full "
                "rediscovery returns uncapped file/full-memory payloads by definition."
            ),
            (
                "Latency includes read instrumentation, witness verification and local SDK work. "
                "Required-witness latency uses only that workflow scope. Tokens, model "
                "costs and live task success are unavailable, not estimated from characters."
            ),
        ],
        "cases": [],
        "tokens": None,
        "provider_cost": None,
        "live_task_success": None,
    }
    with tempfile.TemporaryDirectory(prefix="orqalis-memory-workflows-") as directory:
        for case in dataset["cases"]:
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["id"]) is None:
                raise ValueError("Unsafe fixture identity")
            for name in case["source_files"]:
                if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
                    raise ValueError("Unsafe fixture source path")
            root = Path(directory) / case["id"]
            fixture = install_fixture(root, case)
            assert fixture["detail_content_chars"] > dataset["response_budget_chars"]
            samples = [
                compare_workflows(
                    root,
                    case,
                    fixture,
                    dataset,
                    timings=not args.smoke,
                    reverse_order=bool(index % 2),
                )
                for index in range(args.repeat)
            ]
            timings = {}
            if not args.smoke:
                for name in (
                    "full_rediscovery",
                    "progressive_memory_then_symbol",
                    "restart_direct_memory",
                ):
                    values = [
                        next(row for row in sample if row["workflow"] == name)["durable_fact_ms"]
                        for sample in samples
                    ]
                    timings[name] = {"time_to_durable_fact": distribution(values)}
            report["cases"].append(
                {
                    "id": case["id"],
                    "task": case["task"],
                    "fixture": {
                        key: value for key, value in fixture.items() if not key.startswith("_")
                    },
                    "gold_witnesses": {
                        "durable_fact": case["fact"],
                        "source_branch": case["source_witness"],
                    },
                    "history_retained": True,
                    "samples": samples,
                    "timing_summary": timings,
                }
            )
    all_rows = [row for case in report["cases"] for sample in case["samples"] for row in sample]
    report["summary"] = {
        "cases": len(report["cases"]),
        "workflow_samples": len(all_rows),
        "all_exact_answer_witnesses_pass": all(row["exact_answer_pass"] for row in all_rows),
        "all_response_caps_pass": all(
            stage["budget_pass"] for row in all_rows for stage in row["stages"]
        ),
        "all_history_retained": all(case["history_retained"] for case in report["cases"]),
        "direct_reuse_graph_refreshes": sum(
            row["reads"]["graph_refresh_calls"]
            for row in all_rows
            if row["workflow"] == "restart_direct_memory"
        ),
    }
    if initial_source != source_fingerprint(source):
        raise RuntimeError("Source changed during capture; discard this measurement")
    if script_hash != digest(Path(__file__).read_bytes()) or digest(dataset_bytes) != digest(
        args.dataset.read_bytes()
    ):
        raise RuntimeError("Script or fixture changed during capture; discard this measurement")
    dependencies = sorted(
        (dist.metadata.get("Name", ""), dist.version) for dist in importlib.metadata.distributions()
    )
    if dependencies != report["environment"]["dependencies"]:
        raise RuntimeError("Dependency environment changed during capture")
    report["source_stable"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=REPO)
    parser.add_argument("--dataset", type=Path, default=REPO / "benchmarks/memory_workflows.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="current-memory-workflows")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 20:
        parser.error("--repeat must be 1..20")
    if args.smoke:
        args.repeat = 1
    for name in ("source_root", "dataset", "output"):
        setattr(args, name, getattr(args, name).resolve())
    if not args.worker:
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--worker",
                "--source-root",
                str(args.source_root),
                "--dataset",
                str(args.dataset),
                "--output",
                str(args.output),
                "--label",
                args.label,
                "--repeat",
                str(args.repeat),
                *(["--smoke"] if args.smoke else []),
            ],
            env=environment(),
            check=True,
        )
        return
    report = worker(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
