"""Compare structurally complete, reproducible quality evidence; PASS is not model quality."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

METRICS = ("recall_at_k", "precision_at_k", "mrr", "ndcg_at_k")
ENV_KEYS = (
    "python",
    "platform",
    "machine",
    "cpu_count",
    "repetitions",
    "dependency_sha256",
    "environment_policy",
)
SKILL_GOLD = {
    cap: f"{cap}-edit"
    for cap in ("python", "javascript", "typescript", "react", "documentation", "database")
}
SELECTION_CONTRACTS = {
    "read-only-role": (True, []),
    "exact-pin": (False, ["python-edit"]),
    "wrong-pin": (True, []),
    "no-capabilities": (False, []),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: Any, name: str, minimum: float = 0) -> float:
    require(
        type(value) in (int, float) and math.isfinite(value) and value >= minimum,
        f"Invalid numeric witness: {name}",
    )
    return float(value)


def unique_rows(rows: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    require(isinstance(rows, list) and bool(rows), f"Missing {name} witnesses")
    ids = [row["id"] for row in rows]
    require(len(ids) == len(set(ids)), f"Duplicate {name} IDs")
    return {row["id"]: row for row in rows}


def same_number(actual: Any, expected: Any, name: str) -> None:
    if expected is None:
        require(actual is None, f"Invalid null witness: {name}")
    else:
        require(abs(number(actual, name) - expected) < 1e-9, f"Inconsistent witness: {name}")


def check_distribution(data: dict[str, Any], repetitions: int, name: str) -> None:
    samples = data["samples_ms"]
    require(len(samples) == repetitions, f"Unexpected timing sample count: {name}")
    for sample in samples:
        number(sample, name)
    same_number(data["median_ms"], statistics.median(samples), name + "/median")
    same_number(data["p95_ms"], sorted(samples)[math.ceil(len(samples) * 0.95) - 1], name + "/p95")


def validate_report(report: dict[str, Any]) -> None:
    require(report.get("schema_version") == 2, "Quality report schema must be version 2")
    require(
        report.get("complete") is True and report.get("source_stable") is True,
        "Comparison requires complete captures from stable sources",
    )
    require(
        report.get("environment", {}).get("isolated_python") is True,
        "Comparison requires isolated source imports",
    )
    for key in ("dataset_sha256", "corpus_sha256", "source_sha256", "benchmark_script_sha256"):
        require(
            isinstance(report.get(key), str) and len(report[key]) == 64,
            f"Missing fingerprint: {key}",
        )
    inventory = report["source_inventory"]
    require(
        bool(inventory) and inventory == sorted(set(inventory)),
        "Missing or duplicate source inventory",
    )
    environment = report["environment"]
    require(all(key in environment for key in ENV_KEYS), "Incomplete environment witness")
    require(
        environment["dependency_sha256"]
        == hashlib.sha256(json.dumps(environment["dependencies"]).encode()).hexdigest(),
        "Dependency fingerprint does not match inventory",
    )
    repetitions = environment["repetitions"]
    require(type(repetitions) is int and 1 <= repetitions <= 20, "Invalid repetition count")
    dataset = report["dataset_manifest"]
    require(
        dataset["fixture_revision"] == report["fixture_revision"],
        "Fixture revision differs from dataset",
    )
    gold = unique_rows(dataset["cases"], "dataset")
    rows = unique_rows(report["cases"], "retrieval")
    require(rows.keys() == gold.keys(), "Missing/extra retrieval cases")
    k = dataset["retrieval_k"]
    for case_id, case in rows.items():
        expected = gold[case_id]["relevant_paths"]
        require(
            case["expected_paths"] == expected and case["partition"] == gold[case_id]["partition"],
            f"Case labels changed: {case_id}",
        )
        for channel in ("index", "context"):
            measurement = case[channel]
            paths = measurement["top_paths"]
            require(
                isinstance(paths, list) and len(paths) <= k and len(paths) == len(set(paths)),
                f"Invalid top paths: {case_id}/{channel}",
            )
            hits = len(set(paths) & set(expected))
            gains = [int(path in expected) for path in paths]
            ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(expected))))
            values = {
                "recall_at_k": hits / len(expected) if expected else None,
                "precision_at_k": hits / len(paths) if paths else 0,
                "mrr": next((1 / (rank + 1) for rank, hit in enumerate(gains) if hit), 0),
                "ndcg_at_k": sum(hit / math.log2(rank + 2) for rank, hit in enumerate(gains))
                / ideal
                if ideal
                else None,
                "negative_returned_paths": len(paths) if not expected else None,
            }
            for metric, value in values.items():
                same_number(measurement[metric], value, f"{case_id}/{channel}/{metric}")
        for key in (
            "context_chars",
            "context_bytes",
            "source_files_opened",
            "source_read_operations",
            "memory_files_opened",
            "memory_read_operations",
        ):
            number(case[key], f"{case_id}/{key}")
        require(isinstance(case["orientation_paths"], list), "Missing orientation witness")
        check_distribution(case["index_time"], repetitions, case_id + "/index")
        check_distribution(case["context_time"], repetitions, case_id + "/context")
    routing = unique_rows(report["skills"]["routing"], "routing")
    route_gold = {
        **gold,
        "negative-prose": {"expected_capabilities": []},
        "negative-missing": {"expected_capabilities": []},
    }
    require(routing.keys() == route_gold.keys(), "Missing/extra routing cases")
    for case_id, case in routing.items():
        expected = route_gold[case_id]["expected_capabilities"]
        require(case["expected"] == expected, f"Routing labels changed: {case_id}")
        require(
            case["false_positives"] == sorted(set(case["actual"]) - set(expected)),
            "Invalid routing false positives",
        )
        require(
            case["false_negatives"] == sorted(set(expected) - set(case["actual"])),
            "Invalid routing false negatives",
        )
        require(
            case["expected_skills"] == sorted(SKILL_GOLD[cap] for cap in expected),
            "Skill labels changed",
        )
        require(
            len(case["selected_skills"]) == len(set(case["selected_skills"])),
            "Duplicate selected skills",
        )
        check_distribution(case["time"], repetitions, case_id + "/routing")
        check_distribution(case["selection_time"], repetitions, case_id + "/selection")
    contracts = unique_rows(report["skills"]["selection_contracts"], "skill selection contracts")
    require(contracts.keys() == SELECTION_CONTRACTS.keys(), "Missing selection contracts")
    for case_id, (denial, ids) in SELECTION_CONTRACTS.items():
        require(
            contracts[case_id]["expected_denial"] is denial
            and contracts[case_id]["expected_skills"] == ids,
            "Skill contract expectations changed",
        )
    summary = report["summary"]
    for channel in ("index", "context"):
        expected = statistics.mean(
            row[channel]["recall_at_k"]
            for row in rows.values()
            if row[channel]["recall_at_k"] is not None
        )
        same_number(summary[f"mean_{channel}_recall_at_k"], expected, "summary recall")
    same_number(
        summary["mean_context_bytes"],
        statistics.mean(row["context_bytes"] for row in rows.values()),
        "summary bytes",
    )
    require(
        summary["context_budget_pass"]
        is all(row["context_chars"] <= dataset["context_budget_chars"] for row in rows.values()),
        "Context budget summary contradicts cases",
    )
    for key in ("false_positives", "false_negatives"):
        same_number(
            summary["routing_" + key],
            sum(len(row[key]) for row in routing.values()),
            "routing summary",
        )
    require(
        summary["memory_lookup_passes"] == sum(row["expected_found"] for row in report["memory"]),
        "Memory summary contradicts cases",
    )
    partitions = report["partitions"]
    require(
        set(partitions) == {row["partition"] for row in rows.values()}, "Missing partition summary"
    )
    for partition, measured in partitions.items():
        selected = [row for row in rows.values() if row["partition"] == partition]
        require(measured["case_count"] == len(selected), "Partition count differs")
        same_number(
            measured["mean_context_bytes"],
            statistics.mean(row["context_bytes"] for row in selected),
            "partition bytes",
        )
        for channel in ("index", "context"):
            positives = [
                row[channel] for row in selected if row[channel]["recall_at_k"] is not None
            ]
            negatives = [row[channel] for row in selected if row[channel]["recall_at_k"] is None]
            require(
                measured[channel]["positive_cases"] == len(positives)
                and measured[channel]["negative_cases"] == len(negatives),
                "Partition polarity counts differ",
            )
            for metric in METRICS:
                same_number(
                    measured[channel][metric],
                    statistics.mean(row[metric] for row in positives) if positives else None,
                    "partition " + metric,
                )
            same_number(
                measured[channel]["negative_returned_paths"],
                sum(row["negative_returned_paths"] for row in negatives),
                "partition negative count",
            )
    for key in ("cli_startup", "mcp_startup_to_project_response"):
        check_distribution(report[key], repetitions, key)
    for name in ("cold", "unchanged", "one_file_changed"):
        check_distribution(
            report["graph"][name]["time"],
            repetitions if name == "unchanged" else 1,
            "graph/" + name,
        )
    for key, name in (
        ("unchanged_parse_count", "unchanged"),
        ("one_file_parse_count", "one_file_changed"),
    ):
        same_number(summary[key], report["graph"][name]["metrics"]["processed_files"], key)
    require(len(report["memory"]) == len(dataset["memories"]), "Missing memory cases")
    for memory in report["memory"]:
        require(
            memory["expected_found"] is (memory["expected_title"] in memory["titles"]),
            "Memory witness mismatch",
        )
    for value in report["disk"].values():
        number(value, "disk")
    number(report["context_python_peak_allocated_bytes"], "allocation")
    portable = report["portable_skills"]
    require(type(portable["supported"]) is bool, "Missing portable support state")
    if portable["supported"]:
        for key in (
            "level_1_metadata_bytes",
            "level_2_metadata_and_selected_body_bytes",
            "level_3_metadata_body_and_one_reference_bytes",
            "eager_all_bodies_and_references_bytes",
        ):
            number(portable[key], key, 1)
        require(
            portable["expected_selected_ids"] == ["python-edit"], "Portable skill labels changed"
        )


def validate_contract(evidence: dict[str, Any], report: dict[str, Any]) -> None:
    require(evidence.get("schema_version") == 2, "Contract evidence requires helper-bound schema 2")
    require(
        evidence.get("child_source_policy") == "rewrite-known-orqalis-cli-and-python-module-v2",
        "Contract child source isolation is not qualified",
    )
    require(
        evidence["source_sha256"] == report["source_sha256"]
        and evidence["dataset_sha256"] == report["dataset_sha256"],
        "Contract source/dataset mismatch",
    )
    require(
        evidence["source_stable"] is True and evidence["tests_stable"] is True,
        "Contract inputs changed during execution",
    )
    require(
        all(
            evidence.get(key) is True
            for key in ("helper_stable", "runner_stable", "dataset_stable")
        ),
        "Contract helper, runner or dataset changed during execution",
    )
    for key in ("helper_sha256", "runner_sha256"):
        value = evidence.get(key)
        require(
            isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef"),
            f"Missing contract fingerprint: {key}",
        )
    require(
        evidence["helper_sha256"] == report["benchmark_script_sha256"],
        "Contract helper differs from the measured quality script",
    )
    for key in ENV_KEYS:
        if key != "repetitions":
            require(
                evidence["environment"][key] == report["environment"][key],
                f"Contract environment mismatch: {key}",
            )
    required = {
        path for case in report["dataset_manifest"]["cases"] for path in case["contract_tests"]
    }
    junit = evidence["junit"]
    require(set(junit["files"]) == required, "Contract file coverage differs from dataset")
    counts = junit["files"].values()
    for row in counts:
        require(
            set(row) == {"passed", "failed", "skipped", "errors"}, "Invalid JUnit outcome inventory"
        )
        for count in row.values():
            require(type(count) is int and count >= 0, "Invalid JUnit outcome count")
    counted = sum(sum(row.values()) for row in counts)
    require(
        junit["test_count"] == counted + len(junit["unmatched_cases"]),
        "JUnit total contradicts cases",
    )
    complete = (
        bool(counted)
        and not junit["unmatched_cases"]
        and not junit["suite_errors"]
        and all(sum(row.values()) for row in counts)
    )
    passed = (
        bool(counted)
        and not junit["unmatched_cases"]
        and not junit["suite_errors"]
        and all(
            row["passed"] and not (row["failed"] or row["skipped"] or row["errors"])
            for row in counts
        )
    )
    require(
        junit["complete"] is bool(complete) and junit["passed"] is bool(passed),
        "JUnit pass flags contradict outcomes",
    )


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    for report in (baseline, current):
        try:
            validate_report(report)
        except (KeyError, TypeError, IndexError, ZeroDivisionError) as exc:
            raise ValueError("Incomplete or invalid quality report structure") from exc
    for key in (
        "dataset_sha256",
        "corpus_sha256",
        "fixture_revision",
        "benchmark_script_sha256",
        "dataset_manifest",
    ):
        require(baseline[key] == current[key], f"Comparison input mismatch: {key}")
    for key in ENV_KEYS:
        require(
            baseline["environment"][key] == current["environment"][key],
            f"Environment mismatch: {key}",
        )
    failures: list[str] = []
    review: list[str] = []
    summary = current["summary"]
    for key, expected in {
        "context_budget_pass": True,
        "routing_false_positives": 0,
        "routing_false_negatives": 0,
        "unchanged_parse_count": 0,
        "one_file_parse_count": 1,
        "memory_lookup_passes": len(current["dataset_manifest"]["memories"]),
    }.items():
        if summary[key] != expected:
            failures.append(f"{key}: observed {summary[key]!r}, required {expected!r}")
    changes: dict[str, Any] = {}
    for key in ("mean_index_recall_at_k", "mean_context_recall_at_k", "mean_context_bytes"):
        old, new = baseline["summary"][key], summary[key]
        changes[key] = {"baseline": old, "current": new, "delta": new - old}
    old_cases = {case["id"]: case for case in baseline["cases"]}
    regressions = []
    for case in current["cases"]:
        for channel in ("index", "context"):
            before, after = old_cases[case["id"]][channel], case[channel]
            if not case["expected_paths"] and after["negative_returned_paths"]:
                failures.append(f"{case['id']}/{channel} returns unmarked irrelevant paths")
            for metric in METRICS:
                if before[metric] is not None and after[metric] < before[metric] - 1e-9:
                    regressions.append(
                        {
                            "case": case["id"],
                            "partition": case["partition"],
                            "channel": channel,
                            "metric": metric,
                            "baseline": before[metric],
                            "current": after[metric],
                            "baseline_paths": before["top_paths"],
                            "current_paths": after["top_paths"],
                        }
                    )
    if regressions:
        review.append("Per-case recall/ranking regressions need explicit analysis")
    for case in current["skills"]["routing"]:
        if sorted(case["selected_skills"]) != case["expected_skills"]:
            failures.append(f"Skill selection differs from independent labels: {case['id']}")
    for case in current["skills"]["selection_contracts"]:
        if (
            case["denied"] != case["expected_denial"]
            or case["selected_skills"] != case["expected_skills"]
            or not case["typed_contract_roundtrip"]
        ):
            failures.append(f"Skill selection contract failed: {case['id']}")
    if baseline["skills"]["fixture_sha256"] != current["skills"]["fixture_sha256"]:
        review.append(
            "Bundled skill fixture changed; byte differences do not isolate disclosure changes"
        )
    portable = current["portable_skills"]
    if not portable["supported"]:
        failures.append("Current source lacks accepted portable skill support")
    else:
        if (
            not portable["portable_instructions_match_fixture"]
            or not portable["resource_match_fixture"]
        ):
            failures.append("Portable instructions/resource differ from the fixture")
        if portable["selected_ids"] != portable["expected_selected_ids"]:
            failures.append("Portable selection differs from independent labels")
        levels = [
            portable[key]
            for key in (
                "level_1_metadata_bytes",
                "level_2_metadata_and_selected_body_bytes",
                "level_3_metadata_body_and_one_reference_bytes",
                "eager_all_bodies_and_references_bytes",
            )
        ]
        if not all(a < b for a, b in zip(levels, levels[1:], strict=False)):
            failures.append(
                "Portable disclosure stages do not establish lower context bytes than eager loading"
            )
    for key in ("cli_startup", "mcp_startup_to_project_response"):
        old, new = baseline[key]["median_ms"], current[key]["median_ms"]
        changes[key] = {"baseline_ms": old, "current_ms": new, "ratio": new / old if old else None}
        if new > old * 2 + 250:
            review.append(f"{key} exceeds 2x baseline plus 250 ms noise allowance")
    for metric in ("cold", "unchanged", "one_file_changed"):
        old, new = (
            baseline["graph"][metric]["time"]["median_ms"],
            current["graph"][metric]["time"]["median_ms"],
        )
        changes[f"graph_{metric}"] = {
            "baseline_ms": old,
            "current_ms": new,
            "ratio": new / old if old else None,
        }
        if new > old * 2 + 250:
            review.append(f"graph/{metric} exceeds the timing investigation budget")
    for key in ("graph_bytes", "index_bytes", "project_store_bytes"):
        old, new = baseline["disk"][key], current["disk"][key]
        changes[key] = {"baseline": old, "current": new, "ratio": new / old if old else None}
    old, new = (
        baseline["context_python_peak_allocated_bytes"],
        current["context_python_peak_allocated_bytes"],
    )
    changes["python_peak_allocated_bytes"] = {
        "baseline": old,
        "current": new,
        "ratio": new / old if old else None,
    }
    if new > old * 2 + 10_000_000:
        review.append("Context Python allocation exceeds 2x baseline plus 10 MB")
    contract_evidence: dict[str, dict[str, Any] | None] = {}
    for label, report in (("baseline", baseline), ("current", current)):
        evidence = report.get("contract_evidence")
        contract_evidence[label] = evidence
        if evidence is None:
            review.append(f"{label} deterministic contract evidence is absent")
            continue
        validate_contract(evidence, report)
        if (
            not evidence["junit"]["complete"]
            or not evidence["junit"]["passed"]
            or evidence["exit_code"] != 0
        ):
            (failures if label == "current" else review).append(
                f"{label} deterministic contracts failed, skipped, or incomplete"
            )
    baseline_contract = contract_evidence["baseline"]
    current_contract = contract_evidence["current"]
    if (
        baseline_contract is not None
        and current_contract is not None
        and baseline_contract["tests_sha256"] != current_contract["tests_sha256"]
    ):
        review.append(
            "Contract test sources differ; use the same frozen test checkout "
            "for differential evidence"
        )
    if baseline_contract is not None and current_contract is not None:
        require(
            baseline_contract["runner_sha256"] == current_contract["runner_sha256"],
            "Contract runner fingerprints differ",
        )
    return {
        "schema_version": 2,
        "baseline_source": baseline["source_sha256"],
        "current_source": current["source_sha256"],
        "dataset_sha256": current["dataset_sha256"],
        "changes": changes,
        "partitions": {"baseline": baseline["partitions"], "current": current["partitions"]},
        "per_case_metric_regressions": regressions,
        "failed_invariants": failures,
        "requires_review": review,
        "status": "FAIL" if failures else "REVIEW" if review else "PASS",
        "limits": (
            "PASS means these deterministic comparison gates passed; it does not establish "
            "live model engineering task success, token savings, Docker isolation, "
            "or cross-machine performance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.current.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
