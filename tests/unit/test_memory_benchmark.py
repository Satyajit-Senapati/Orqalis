"""Calibrate read accounting; benchmark smoke supplies complete workflow witnesses."""

import importlib.util
from array import array
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest


def benchmark_module() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_memory.py"
    spec = importlib.util.spec_from_file_location("orqalis_memory_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_probe_counts_actual_utf8_and_preserves_stage_snapshots(tmp_path: Path) -> None:
    module = benchmark_module()
    content = "caf\u00e9\n"
    target = tmp_path / "sample.py"
    target.write_bytes(content.encode("utf-8"))
    memory = tmp_path / ".orqalis" / "memory" / "records" / "MEM-20000101-0001.md"
    memory.parent.mkdir(parents=True)
    memory.write_bytes(b"Reviewed decision")
    with module.ReadProbe(tmp_path, ["sample.py"]) as probe:
        assert target.read_text(encoding="utf-8") == content
        first = probe.snapshot()
        assert target.read_bytes() == content.encode("utf-8")
        assert memory.read_text(encoding="utf-8") == "Reviewed decision"
        final = probe.snapshot()
    source = final["categories"]["source"]
    assert source["unique_files"] == 1
    assert source["open_operations"] == source["read_operations"] == 2
    assert source["returned_chars"] == len(content) * 2
    assert source["returned_utf8_bytes"] == len(content.encode("utf-8")) * 2
    assert final["categories"]["memory"]["unique_files"] == 1
    assert final["graph_refresh_calls"] == 0
    assert first["categories"]["source"]["open_operations"] == 1
    assert first["categories"]["source"]["files"]["sample.py"]["open_operations"] == 1


def calibrated_fixture(module: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    case = {
        "fact": "Reviewed policy",
        "old_fact": "Obsolete policy",
        "source_witness": "return value",
        "target_path": "src/example.py",
        "symbol": "example",
        "source_files": {"src/example.py": "def example(value):\n    return value\n"},
    }
    detail_id, overview_id, old_id = "MEM-20000101-0002", "MEM-20000101-0003", "MEM-20000101-0001"
    detail: dict[str, Any] = {
        "id": detail_id,
        "content": "Introduction\nReviewed policy\nTail",
        "title": "Policy",
        "category": "decision",
        "references": [],
        "summary": "Current operating decision",
        "source": {"type": "user", "paths": [], "content_hashes": {}},
        "verified_commit": None,
        "supersedes": old_id,
    }
    overview = {
        **detail,
        "id": overview_id,
        "content": "Read the linked decision",
        "title": "Guide",
        "category": "architecture",
        "references": [detail_id],
        "summary": "Operating guide",
        "supersedes": None,
    }
    fixture = {
        "detail_id": detail_id,
        "overview_id": overview_id,
        "predecessor_id": old_id,
        "_active_records": {detail_id: detail, overview_id: overview},
        "source_files": list(case["source_files"]),
        "expected_symbol": module.fixture_symbol(case),
    }
    return case, fixture


def memory_page(
    fixture: dict[str, Any], *, offset: int = 0, end: int | None = None
) -> dict[str, Any]:
    record = fixture["_active_records"][fixture["detail_id"]]
    content = record["content"][offset:end]
    stop = offset + len(content)
    return {
        "item": {
            "id": record["id"],
            "title": record["title"],
            "category": record["category"],
            "preview": record["summary"],
            "content_chars": len(record["content"]),
            "references": [],
            "reference_count": 0,
            "freshness": "FRESH",
            "lifecycle": "ACTIVE",
            "superseded_by": None,
        },
        "source": deepcopy(record["source"]),
        "verified_commit": None,
        "content": content,
        "offset": offset,
        "next_offset": stop if stop < len(record["content"]) else None,
        "references": [],
    }


def symbol_body(case: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    expected = fixture["expected_symbol"]
    node = {
        key: value
        for key, value in expected.items()
        if key not in {"byte_start", "byte_end", "body_sha256"}
    }
    node.update(
        kind="FUNCTION",
        language="Python",
        metadata={
            "byte_start": expected["byte_start"],
            "byte_end": expected["byte_end"],
        },
    )
    data = case["source_files"][case["target_path"]].encode()
    return {
        "symbol": node,
        "source_hash": expected["source_hash"],
        "content": data[expected["byte_start"] : expected["byte_end"]].decode(),
        "source_coverage": {"extraction_truncated": False},
    }


def test_workflow_requires_typed_content_witness_and_checks_budget(tmp_path: Path) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    page = memory_page(fixture)
    flow.call(
        "get_project_memory_detail",
        lambda: page,
        budget=1800,
        record_id=fixture["detail_id"],
        offset=0,
    )
    with pytest.raises(AssertionError):
        flow.finish("complete", require_source=True)
    flow.call("get_symbol_body", lambda: symbol_body(case, fixture), budget=1800)
    result = flow.finish("complete", require_source=True)
    assert result["witness_recall"] == 1
    assert result["durable_fact_ms"] is None
    assert result["total_duration_ms"] is None
    evidence = result["stages"][0]["verified_evidence"][0]
    assert evidence["returned_content_sha256"] == module.digest(page["content"].encode())
    assert evidence["oracle_content_sha256"] == evidence["returned_content_sha256"]
    with pytest.raises(AssertionError):
        flow.call(
            "get_project_memory_detail",
            lambda: page,
            budget=4,
            record_id=fixture["detail_id"],
            offset=0,
        )


def test_untyped_payload_cannot_supply_gold_strings(tmp_path: Path) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    with pytest.raises(AssertionError, match="No typed evidence"):
        flow.call(
            "memory",
            lambda: {
                "body": case["fact"],
                "wrong_file_body": case["source_witness"],
                "old": case["old_fact"],
            },
        )
    assert flow.first_seen == {} and flow.stages == []


@pytest.mark.parametrize(
    "mutation",
    [
        "predecessor",
        "wrong_id",
        "superseded",
        "stale",
        "wrong_content",
        "wrong_offset",
        "wrong_next_offset",
        "wrong_source",
        "obsolete_metadata",
        "predecessor_metadata",
    ],
)
def test_memory_gold_text_does_not_override_identity_or_content_failure(
    tmp_path: Path, mutation: str
) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    page = memory_page(fixture)
    if mutation == "predecessor":
        page["item"]["id"] = fixture["predecessor_id"]
    elif mutation == "wrong_id":
        page["item"]["id"] = fixture["overview_id"]
    elif mutation == "superseded":
        page["item"]["lifecycle"] = "SUPERSEDED"
    elif mutation == "stale":
        page["item"]["freshness"] = "STALE"
    elif mutation == "wrong_content":
        page["content"] = page["content"].replace("Tail", "FAIL")
    elif mutation == "wrong_offset":
        page["offset"] = 1
    elif mutation == "wrong_next_offset":
        page["next_offset"] = 999
    elif mutation == "wrong_source":
        page["source"]["content_hashes"] = {case["target_path"]: "0" * 64}
    elif mutation == "obsolete_metadata":
        page["diagnostic"] = case["old_fact"]
    else:
        page["diagnostic"] = fixture["predecessor_id"]
    with pytest.raises(AssertionError):
        flow.call(
            "get_project_memory_detail", lambda: page, record_id=fixture["detail_id"], offset=0
        )
    assert flow.first_seen == {} and flow.stages == []


@pytest.mark.parametrize("mutation", ["id", "path", "name", "hash", "outer_hash", "span", "body"])
def test_source_gold_text_requires_exact_symbol_path_hash_and_span(
    tmp_path: Path, mutation: str
) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    body = symbol_body(case, fixture)
    if mutation in {"id", "name"}:
        body["symbol"][mutation] = "wrong"
    elif mutation == "path":
        body["symbol"]["file_path"] = "src/wrong.py"
    elif mutation == "hash":
        body["symbol"]["source_hash"] = "0" * 64
    elif mutation == "outer_hash":
        body["source_hash"] = "0" * 64
    elif mutation == "span":
        body["symbol"]["metadata"]["byte_end"] += 1
    else:
        body["content"] += "\n# wrong but still contains return value"
    with pytest.raises(AssertionError):
        flow.call("get_symbol_body", lambda: body)
    assert flow.first_seen == {} and flow.stages == []


def test_metadata_gold_is_not_a_content_witness_and_page_digest_is_honest(tmp_path: Path) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    page = memory_page(fixture, end=5)
    page["diagnostic"] = case["fact"]
    flow.call("get_project_memory_detail", lambda: page, record_id=fixture["detail_id"], offset=0)
    assert flow.first_seen == {}
    evidence = flow.stages[0]["verified_evidence"][0]
    assert evidence["returned_content_sha256"] != evidence["oracle_content_sha256"]
    with pytest.raises(AssertionError):
        flow.finish("direct", require_source=False)


def test_context_and_full_memory_allow_only_canonical_successor_provenance(tmp_path: Path) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    records = [
        {
            "record": deepcopy(record),
            "freshness": "FRESH",
            "lifecycle": "ACTIVE",
            "superseded_by": None,
            "changed_sources": [],
        }
        for record in fixture["_active_records"].values()
    ]
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    flow.call("all_active_memory", lambda: records)
    assert flow.finish("direct", require_source=False)["exact_answer_pass"]
    context = {"memory": records, "memory_discovery": []}
    flow.call("project_context", lambda: context)
    records[0]["record"]["content"] += "\n" + case["old_fact"]
    with pytest.raises(AssertionError):
        flow.call("all_active_memory", lambda: records)
    with pytest.raises(AssertionError):
        flow.call("project_context", lambda: context)


def test_full_memory_rejects_extra_predecessor_and_duplicate_records(tmp_path: Path) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    records = [
        {
            "record": deepcopy(record),
            "freshness": "FRESH",
            "lifecycle": "ACTIVE",
            "superseded_by": None,
            "changed_sources": [],
        }
        for record in fixture["_active_records"].values()
    ]
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), False)
    with pytest.raises(AssertionError):
        flow.call("all_active_memory", lambda: [*records, records[0]])
    predecessor = deepcopy(records[0])
    predecessor["record"]["id"] = fixture["predecessor_id"]
    with pytest.raises(AssertionError):
        flow.call("all_active_memory", lambda: [*records, predecessor])


def test_required_witness_timing_ignores_later_unrequired_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = benchmark_module()
    case, fixture = calibrated_fixture(module)
    ticks = iter(float(value) for value in range(20))
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(ticks))
    flow = module.Workflow(case, fixture, module.ReadProbe(tmp_path, []), True)
    flow.call(
        "get_project_memory_detail",
        lambda: memory_page(fixture),
        record_id=fixture["detail_id"],
        offset=0,
    )
    flow.call("get_symbol_body", lambda: symbol_body(case, fixture))
    assert flow.first_seen["source_branch"] > flow.first_seen["durable_fact"]
    result = flow.finish("direct", require_source=False)
    assert result["all_required_witnesses_ms"] == result["durable_fact_ms"]
    complete = flow.finish("full", require_source=True)
    assert complete["all_required_witnesses_ms"] == flow.first_seen["source_branch"]


def test_partial_binary_utf8_reads_preserve_bytes_and_account_incrementally(tmp_path: Path) -> None:
    module = benchmark_module()
    target = tmp_path / "sample.py"
    data = "caf\u00e9\n".encode()
    target.write_bytes(data)
    with module.ReadProbe(tmp_path, ["sample.py"]) as probe:
        with target.open("rb") as stream:
            assert stream.read(4) == data[:4]
            partial = probe.snapshot()["categories"]["source"]
            assert partial["returned_chars"] == 3
            assert partial["binary_pending_bytes"] == 1
            assert stream.read(0) == b""
            assert stream.read(1) == data[4:5]
            assert stream.readlines() == [b"\n"]
        result = probe.snapshot()["categories"]["source"]
    assert result["returned_chars"] == 5
    assert result["returned_utf8_bytes"] == len(data)
    assert result["binary_pending_bytes"] == result["binary_undecodable_bytes"] == 0


def test_binary_invalid_bytes_readinto_and_seek_are_transparent(tmp_path: Path) -> None:
    module = benchmark_module()
    target = tmp_path / "sample.py"
    target.write_bytes(b"\xff\xc3\xa9\xc3")
    with module.ReadProbe(tmp_path, ["sample.py"]) as probe:
        with target.open("rb") as stream:
            buffer = bytearray(2)
            assert stream.readinto(buffer) == 2 and buffer == b"\xff\xc3"
            assert stream.read1(1) == b"\xa9"
            assert stream.readinto1(buffer) == 1 and buffer[0] == 0xC3
            assert stream.seek(1) == 1
            assert stream.read(2) == b"\xc3\xa9"
        result = probe.snapshot()["categories"]["source"]
    assert result["returned_chars"] == 2
    assert result["returned_utf8_bytes"] == 6
    assert result["binary_undecodable_bytes"] == 2
    assert result["binary_pending_bytes"] == 0


def test_binary_readinto_counts_bytes_for_nonbyte_buffers(tmp_path: Path) -> None:
    module = benchmark_module()
    target = tmp_path / "sample.py"
    target.write_bytes(b"abcdefgh")
    with module.ReadProbe(tmp_path, ["sample.py"]) as probe:
        with target.open("rb") as stream:
            buffer = array("I", [0])
            assert buffer.itemsize == 4
            assert stream.readinto(buffer) == 4
            assert memoryview(buffer).cast("B").tobytes() == b"abcd"
            assert stream.readinto1(buffer) == 4
            assert memoryview(buffer).cast("B").tobytes() == b"efgh"
        result = probe.snapshot()["categories"]["source"]
    assert result["returned_utf8_bytes"] == result["returned_chars"] == 8


def test_read_probe_counts_canonical_snapshot_reads_once(tmp_path: Path) -> None:
    from orqalis.persistence.filesystem import io

    module = benchmark_module()
    source = tmp_path / "sample.py"
    memory = tmp_path / ".orqalis/memory/records/MEM-20000101-0001.md"
    metadata = tmp_path / ".orqalis/state.yaml"
    memory.parent.mkdir(parents=True)
    data = "café\n".encode()
    for path in (source, memory, metadata):
        path.write_bytes(data)
    assert "open" not in vars(io)
    with module.ReadProbe(tmp_path, ["sample.py"]) as probe:
        assert source.read_bytes() == data
        assert io.read_bytes(source) == data
        assert io.read_text(memory) == "café\n"
        assert io.read_bytes(metadata) == data
        result = probe.snapshot()
    assert "open" not in vars(io)
    for kind, expected in (("source", 2), ("memory", 1), ("metadata", 1)):
        row = result["categories"][kind]
        assert row["open_operations"] == row["read_operations"] == expected
        assert row["returned_utf8_bytes"] == len(data) * expected
        assert row["returned_chars"] == len("café\n") * expected
    assert result["graph_refresh_calls"] == 0


@pytest.mark.parametrize("content", [b"", b"plain bytes", b"caf\xc3\xa9\n", b"\xff\xc3"])
def test_owned_verification_matches_path_read_accounting(tmp_path: Path, content: bytes) -> None:
    from orqalis.persistence.filesystem import io

    module = benchmark_module()
    legacy = tmp_path / "legacy.tmp"
    legacy.write_bytes(content)
    with module.ReadProbe(tmp_path, []) as probe:
        assert io.read_bytes(legacy) == content
        before = probe.snapshot()["categories"]["metadata"]
    with module.ReadProbe(tmp_path, []) as probe:
        io.atomic_write_bytes(tmp_path / "owned.bin", content)
        after = probe.snapshot()["categories"]["metadata"]
    for key in (
        "unique_files",
        "open_operations",
        "read_operations",
        "returned_chars",
        "returned_utf8_bytes",
        "binary_undecodable_bytes",
        "binary_pending_bytes",
    ):
        assert after[key] == before[key]
    assert (tmp_path / "owned.bin").read_bytes() == content
