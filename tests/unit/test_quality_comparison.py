"""Adversarial report checks; these tests do not execute benchmark workloads."""

import copy
import hashlib
import json
import runpy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCH = runpy.run_path(str(ROOT / "scripts/benchmark_quality.py"))
COMPARE = runpy.run_path(str(ROOT / "scripts/compare_quality.py"))


def distribution() -> dict[str, Any]:
    return {"samples_ms": [1, 2, 3], "median_ms": 2, "p95_ms": 3}


def refresh(report: dict[str, Any]) -> None:
    for case in report["cases"]:
        for channel in ("index", "context"):
            case[channel] = BENCH["relevance"](
                case[channel]["top_paths"], case["expected_paths"], 5
            )
    report["partitions"] = BENCH["partition_summary"](report["cases"])
    for channel in ("index", "context"):
        values = [
            case[channel]["recall_at_k"]
            for case in report["cases"]
            if case[channel]["recall_at_k"] is not None
        ]
        report["summary"][f"mean_{channel}_recall_at_k"] = sum(values) / len(values)


def capture() -> dict[str, Any]:
    gold = [
        {
            "id": "positive",
            "partition": "engineering",
            "relevant_paths": ["src/example.py"],
            "scope": ["src/example.py"],
            "expected_capabilities": ["python"],
            "contract_tests": ["tests/unit/test_example.py"],
        },
        {
            "id": "negative",
            "partition": "held-out",
            "relevant_paths": [],
            "scope": ["unrelated/"],
            "expected_capabilities": [],
            "contract_tests": [],
        },
    ]
    cases = []
    for row in gold:
        cases.append(
            {
                "id": row["id"],
                "partition": row["partition"],
                "expected_paths": row["relevant_paths"],
                "index": {"top_paths": row["relevant_paths"][:]},
                "context": {"top_paths": row["relevant_paths"][:]},
                "orientation_paths": [],
                "context_chars": 100,
                "context_bytes": 100,
                "source_files_opened": 1,
                "source_read_operations": 1,
                "memory_files_opened": 1,
                "memory_read_operations": 1,
                "index_time": distribution(),
                "context_time": distribution(),
            }
        )
    dependencies = [["example", "1"]]
    env = {
        "python": "3.12",
        "platform": "fixture",
        "machine": "x64",
        "cpu_count": 2,
        "repetitions": 3,
        "isolated_python": True,
        "dependencies": dependencies,
        "dependency_sha256": hashlib.sha256(json.dumps(dependencies).encode()).hexdigest(),
        "environment_policy": "controlled",
    }
    routing = []
    for row in [
        *gold,
        {"id": "negative-prose", "expected_capabilities": []},
        {"id": "negative-missing", "expected_capabilities": []},
    ]:
        ids = ["python-edit"] if row["expected_capabilities"] else []
        routing.append(
            {
                "id": row["id"],
                "actual": row["expected_capabilities"],
                "expected": row["expected_capabilities"],
                "false_positives": [],
                "false_negatives": [],
                "expected_skills": ids,
                "selected_skills": ids[:],
                "time": distribution(),
                "selection_time": distribution(),
            }
        )
    report = {
        "schema_version": 2,
        "complete": True,
        "source_stable": True,
        "source_sha256": "a" * 64,
        "source_inventory": ["src/orqalis/__init__.py"],
        "dataset_sha256": "b" * 64,
        "corpus_sha256": "c" * 64,
        "benchmark_script_sha256": "d" * 64,
        "fixture_revision": "frozen",
        "environment": env,
        "dataset_manifest": {
            "fixture_revision": "frozen",
            "cases": gold,
            "memories": [{"title": "Known"}],
            "context_budget_chars": 1000,
            "retrieval_k": 5,
        },
        "cases": cases,
        "skills": {
            "fixture_sha256": "e" * 64,
            "routing": routing,
            "selection_contracts": [
                {
                    "id": name,
                    "expected_denial": deny,
                    "denied": deny,
                    "expected_skills": ids,
                    "selected_skills": ids[:],
                    "typed_contract_roundtrip": True,
                }
                for name, (deny, ids) in COMPARE["SELECTION_CONTRACTS"].items()
            ],
        },
        "portable_skills": {
            "supported": True,
            "portable_instructions_match_fixture": True,
            "resource_match_fixture": True,
            "selected_ids": ["python-edit"],
            "expected_selected_ids": ["python-edit"],
            "level_1_metadata_bytes": 100,
            "level_2_metadata_and_selected_body_bytes": 200,
            "level_3_metadata_body_and_one_reference_bytes": 300,
            "eager_all_bodies_and_references_bytes": 1000,
        },
        "summary": {
            "context_budget_pass": True,
            "routing_false_positives": 0,
            "routing_false_negatives": 0,
            "unchanged_parse_count": 0,
            "one_file_parse_count": 1,
            "memory_lookup_passes": 1,
            "mean_context_bytes": 100,
        },
        "memory": [{"expected_found": True, "expected_title": "Known", "titles": ["Known"]}],
        "cli_startup": distribution(),
        "mcp_startup_to_project_response": distribution(),
        "graph": {
            name: {
                "time": distribution()
                if name == "unchanged"
                else {"samples_ms": [1], "median_ms": 1, "p95_ms": 1},
                "metrics": {"processed_files": 0 if name == "unchanged" else 1},
            }
            for name in ("cold", "unchanged", "one_file_changed")
        },
        "disk": {"graph_bytes": 100, "index_bytes": 100, "project_store_bytes": 100},
        "context_python_peak_allocated_bytes": 100,
    }
    report["contract_evidence"] = {
        "schema_version": 2,
        "helper_sha256": report["benchmark_script_sha256"],
        "runner_sha256": "e" * 64,
        "helper_stable": True,
        "runner_stable": True,
        "dataset_stable": True,
        "source_sha256": report["source_sha256"],
        "dataset_sha256": report["dataset_sha256"],
        "source_stable": True,
        "tests_stable": True,
        "tests_sha256": "f" * 64,
        "environment": env.copy(),
        "exit_code": 0,
        "child_source_policy": "rewrite-known-orqalis-cli-and-python-module-v2",
        "junit": {
            "files": {
                "tests/unit/test_example.py": {"passed": 1, "failed": 0, "skipped": 0, "errors": 0}
            },
            "test_count": 1,
            "unmatched_cases": [],
            "suite_errors": 0,
            "complete": True,
            "passed": True,
        },
    }
    refresh(report)
    return report


def test_valid_comparison_allows_unsupported_baseline_and_explicit_orientation() -> None:
    baseline, current = capture(), capture()
    baseline["portable_skills"] = {"supported": False}
    current["cases"][1]["orientation_paths"] = ["orientation-only.py"]
    assert COMPARE["compare"](baseline, current)["status"] == "PASS"


def test_negative_paths_cannot_pass_even_when_positive_recall_is_unchanged() -> None:
    baseline, current = capture(), capture()
    current["cases"][1]["context"]["top_paths"] = ["irrelevant.py"]
    refresh(current)
    result = COMPARE["compare"](baseline, current)
    assert result["status"] == "FAIL"
    assert "unmarked irrelevant" in str(result["failed_invariants"])


def test_same_recall_with_worse_ranking_requires_review() -> None:
    baseline, current = capture(), capture()
    current["cases"][0]["index"]["top_paths"] = ["noise.py", "src/example.py"]
    refresh(current)
    result = COMPARE["compare"](baseline, current)
    assert result["status"] == "REVIEW"
    assert {row["metric"] for row in result["per_case_metric_regressions"]} == {
        "precision_at_k",
        "mrr",
        "ndcg_at_k",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-case",
        "duplicate-case",
        "missing-routing",
        "invented-score",
        "nan",
        "false-summary",
        "missing-partition",
        "missing-timing-sample",
    ],
)
def test_invalid_or_incomplete_witnesses_are_rejected(mutation: str) -> None:
    baseline, current = capture(), capture()
    if mutation == "missing-case":
        current["cases"].pop()
    elif mutation == "duplicate-case":
        current["cases"].append(copy.deepcopy(current["cases"][0]))
    elif mutation == "missing-routing":
        current["skills"]["routing"].pop()
    elif mutation == "invented-score":
        current["cases"][0]["index"]["mrr"] = 0
    elif mutation == "nan":
        current["cases"][0]["context_bytes"] = float("nan")
    elif mutation == "false-summary":
        current["summary"]["mean_index_recall_at_k"] = 0.5
    elif mutation == "missing-partition":
        current["partitions"].pop("held-out")
    else:
        current["cli_startup"]["samples_ms"].pop()
    with pytest.raises(ValueError):
        COMPARE["compare"](baseline, current)


@pytest.mark.parametrize("field", ["python", "platform", "repetitions", "dependencies"])
def test_different_environments_cannot_be_compared(field: str) -> None:
    baseline, current = capture(), capture()
    if field == "repetitions":
        current["environment"][field] = 1
    elif field == "dependencies":
        current["environment"][field] = [["example", "2"]]
        current["environment"]["dependency_sha256"] = hashlib.sha256(
            json.dumps(current["environment"][field]).encode()
        ).hexdigest()
    else:
        current["environment"][field] = "other"
    with pytest.raises(ValueError):
        COMPARE["compare"](baseline, current)


@pytest.mark.parametrize(
    "failure",
    [
        "empty-selection",
        "role-grant",
        "wrong-pin",
        "roundtrip",
        "unsupported",
        "changed-body",
        "changed-resource",
        "changed-portable-selection",
        "not-progressive",
    ],
)
def test_skill_and_portability_regressions_cannot_pass(failure: str) -> None:
    baseline, current = capture(), capture()
    if failure == "empty-selection":
        current["skills"]["routing"][0]["selected_skills"] = []
    elif failure == "role-grant":
        current["skills"]["selection_contracts"][0]["denied"] = False
    elif failure == "wrong-pin":
        current["skills"]["selection_contracts"][2]["denied"] = False
    elif failure == "roundtrip":
        current["skills"]["selection_contracts"][1]["typed_contract_roundtrip"] = False
    elif failure == "unsupported":
        current["portable_skills"] = {"supported": False}
    elif failure == "changed-body":
        current["portable_skills"]["portable_instructions_match_fixture"] = False
    elif failure == "changed-resource":
        current["portable_skills"]["resource_match_fixture"] = False
    elif failure == "changed-portable-selection":
        current["portable_skills"]["selected_ids"] = []
    else:
        current["portable_skills"]["eager_all_bodies_and_references_bytes"] = 250
    assert COMPARE["compare"](baseline, current)["status"] == "FAIL"


def test_contract_skips_missing_evidence_and_lying_flags_cannot_pass() -> None:
    baseline, current = capture(), capture()
    current["contract_evidence"] = None
    assert COMPARE["compare"](baseline, current)["status"] == "REVIEW"
    current = capture()
    row = current["contract_evidence"]["junit"]["files"]["tests/unit/test_example.py"]
    row.update(passed=0, skipped=1)
    with pytest.raises(ValueError, match="pass flags"):
        COMPARE["compare"](baseline, current)
    current["contract_evidence"]["junit"]["passed"] = False
    assert COMPARE["compare"](baseline, current)["status"] == "FAIL"


def test_added_source_files_and_non_python_resources_change_fingerprint(tmp_path: Path) -> None:
    package = tmp_path / "src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    before = BENCH["source_fingerprint"](tmp_path)
    (package / "new-resource.txt").write_text("Runtime input")
    after = BENCH["source_fingerprint"](tmp_path)
    assert before != after and "src/orqalis/new-resource.txt" in after["files"]
    (package / "__pycache__").mkdir()
    (package / "__pycache__/fixture.pyc").write_bytes(b"cache")
    assert after == BENCH["source_fingerprint"](tmp_path)


def test_junit_counts_real_outcomes_and_rejects_missing_or_duplicate_cases(tmp_path: Path) -> None:
    path = tmp_path / "contracts.xml"
    path.write_text(
        '<testsuites><testsuite errors="0">'
        '<testcase classname="tests.unit.test_example" name="works"/>'
        '<testcase classname="tests.unit.test_example" name="skips">'
        "<skipped/></testcase></testsuite></testsuites>"
    )
    report = BENCH["contract_junit"](path, ["tests/unit/test_example.py"])
    assert report["complete"] and not report["passed"]
    assert report["files"]["tests/unit/test_example.py"]["skipped"] == 1
    assert not BENCH["contract_junit"](
        path, ["tests/unit/test_example.py", "tests/unit/test_missing.py"]
    )["complete"]
    path.write_text(
        '<testsuite><testcase classname="x" name="same"/>'
        '<testcase classname="x" name="same"/></testsuite>'
    )
    with pytest.raises(ValueError, match="Duplicate"):
        BENCH["contract_junit"](path, ["tests/unit/test_example.py"])


def test_benchmark_environment_drops_application_credentials_and_git_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORQALIS_OPENAI_API_KEY", "not-for-benchmark")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.autocrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "untrusted")
    monkeypatch.setenv("PYTHONPATH", "untrusted")
    env = BENCH["controlled_environment"]()
    assert (
        "ORQALIS_OPENAI_API_KEY" not in env
        and "GIT_CONFIG_KEY_1" not in env
        and "GIT_CONFIG_VALUE_1" not in env
        and "PYTHONPATH" not in env
    )
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "core.autocrlf"
    assert env["GIT_CONFIG_VALUE_0"] == "input"


def test_controlled_git_commits_crlf_fixture_as_lf_without_local_config(tmp_path: Path) -> None:
    import subprocess

    # Explicit bytes make the Windows Path.write_text failure reproducible on every OS.
    (tmp_path / "main.py").write_bytes(b"answer = 42\r\n")
    BENCH["git"](tmp_path, "init", "-b", "main")
    BENCH["git"](tmp_path, "add", "main.py")
    BENCH["git"](tmp_path, "commit", "-m", "Controlled fixture")
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "show", "HEAD:main.py"],
        env=BENCH["controlled_environment"](),
        capture_output=True,
        check=True,
    )
    assert result.stdout == b"answer = 42\n"
    assert (tmp_path / "main.py").read_bytes() == b"answer = 42\r\n"
    assert "autocrlf" not in (tmp_path / ".git/config").read_text(encoding="utf-8")


def test_timed_preserves_results_and_rejects_empty_measurements() -> None:
    values = iter(["first", "second"])
    result, timing = BENCH["timed"](lambda: next(values), 2)
    assert result == "second" and len(timing["samples_ms"]) == 2
    assert BENCH["timed"](lambda: None, 1)[0] is None
    with pytest.raises(ValueError, match="at least one"):
        BENCH["timed"](lambda: None, 0)


def test_contract_child_cli_is_bound_to_selected_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import subprocess
    import sys

    package = tmp_path / "selected/src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "__main__.py").write_text("print('selected-fixture-source')")
    source = tmp_path / "selected"
    audit = tmp_path / "children.jsonl"
    # monkeypatch records the original class so the harness override is test-scoped.
    monkeypatch.setattr(subprocess, "Popen", subprocess.Popen)
    monkeypatch.setattr(
        asyncio.BaseEventLoop, "subprocess_exec", asyncio.BaseEventLoop.subprocess_exec
    )
    runner = runpy.run_path(str(ROOT / "scripts/run_quality_contracts.py"))
    runner["install_child_source_guard"](source, audit)
    for command in (
        [str(tmp_path / "installed/orqalis.exe"), "--version"],
        [sys.executable, "-m", "orqalis", "--version"],
    ):
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        assert result.stdout.strip() == "selected-fixture-source"
    records = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(records) == 2 and all(row["selected_source"] == str(source) for row in records)


@pytest.mark.parametrize("mutate_helper", [False, True])
def test_contract_runner_consumes_actual_junit_under_source_isolation(
    tmp_path: Path, mutate_helper: bool
) -> None:
    import subprocess
    import sys

    runner_path = ROOT / "scripts/run_quality_contracts.py"
    helper_path = ROOT / "scripts/benchmark_quality.py"
    if mutate_helper:
        copied = tmp_path / "scripts"
        copied.mkdir()
        (copied / runner_path.name).write_bytes(runner_path.read_bytes())
        (copied / helper_path.name).write_bytes(helper_path.read_bytes())
        runner_path, helper_path = copied / runner_path.name, copied / helper_path.name
    mutation = (
        (
            f"    from pathlib import Path\n    helper = Path({str(helper_path)!r})\n"
            "    helper.write_bytes(helper.read_bytes() + b'\\n# changed during test\\n')\n"
        )
        if mutate_helper
        else ""
    )
    source = tmp_path / "source"
    package = source / "src/orqalis"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("MARKER = 'selected-source'")
    (package / "__main__.py").write_text("print('selected-source')")
    tests = tmp_path / "frozen"
    test_dir = tests / "tests/unit"
    test_dir.mkdir(parents=True)
    (tests / "tests/__init__.py").write_text("")
    (test_dir / "__init__.py").write_text("")
    (test_dir / "test_example.py").write_text(
        "import subprocess\nimport orqalis\n"
        "def test_bound_source():\n"
        "    assert orqalis.MARKER == 'selected-source'\n"
        "    child = subprocess.run(['orqalis', '--version'], "
        "capture_output=True, text=True, check=True)\n"
        "    assert child.stdout.strip() == 'selected-source'\n" + mutation
    )
    dataset = capture()["dataset_manifest"]
    dataset["fixture_paths"] = ["src/example.py"]
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset))
    output = tmp_path / "contracts.json"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(runner_path),
            "--source-root",
            str(source),
            "--tests-root",
            str(tests),
            "--dataset",
            str(dataset_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (1 if mutate_helper else 0), result.stdout + result.stderr
    report = json.loads(output.read_text())
    assert report["junit"]["passed"] and report["junit"]["test_count"] == 1
    assert report["source_stable"] and report["tests_stable"]
    assert report["schema_version"] == 2
    assert report["helper_stable"] is (not mutate_helper)
    assert report["runner_stable"] and report["dataset_stable"]
    assert (
        report["helper_sha256"]
        == hashlib.sha256((ROOT / "scripts/benchmark_quality.py").read_bytes()).hexdigest()
    )
    assert report["environment"]["isolated_python"]
    assert report["child_launches"][0]["selected_source"] == str(source)


@pytest.mark.parametrize(
    "mutation",
    [
        "old_schema",
        "missing_helper",
        "changed_helper",
        "unstable_helper",
        "unstable_runner",
        "unstable_dataset",
        "different_runner",
    ],
)
def test_helperless_or_changed_contracts_cannot_be_compared(mutation: str) -> None:
    baseline, current = capture(), capture()
    evidence = current["contract_evidence"]
    if mutation == "old_schema":
        evidence["schema_version"] = 1
    elif mutation == "missing_helper":
        del evidence["helper_sha256"]
    elif mutation == "changed_helper":
        evidence["helper_sha256"] = "9" * 64
    elif mutation == "different_runner":
        evidence["runner_sha256"] = "8" * 64
    else:
        evidence[mutation.removeprefix("unstable_") + "_stable"] = False
    with pytest.raises(ValueError, match="[Cc]ontract"):
        COMPARE["compare"](baseline, current)
