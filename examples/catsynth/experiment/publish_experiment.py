"""Project a raw experiment artifact into a compact, reviewable repository record.

Raw App Server transcripts remain local. The published record keeps every
generated sketch, strategy, prompt, diff, failure, gate outcome, and usage total.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


FILES = ("SKETCH.md", "strategy.py", "oracle_prompt.txt")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact_case(case: dict[str, Any]) -> dict[str, Any]:
    fields = case.get("fields", {})
    mismatches = {
        name: value for name, value in fields.items()
        if value.get("checked", True) and not value.get("match", False)
    }
    return {
        key: case[key]
        for key in ("id", "scenario_id", "passed", "checked_fields", "expected", "actual", "error")
        if key in case
    } | ({"mismatches": mismatches} if mismatches else {})


def compact_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: gate[key]
        for key in ("passed", "passed_count", "total", "scope", "error")
        if key in gate
    } | {"cases": [compact_case(case) for case in gate.get("cases", [])]}


def compact_sketch_review(review: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "verdict", "applicable_clauses", "required_behavior",
            "difference", "failure_class", "passed", "model_verdict",
            "adjudication")
    return {
        key: review[key]
        for key in ("passed", "passed_count", "total", "error")
        if key in review
    } | {
        "cases": [
            {key: item[key] for key in keep if key in item}
            for item in review.get("cases", [])
        ]
    }


def compact_failure(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "failures" in value:
        return {"failures": [compact_failure(item) for item in value["failures"]]}
    keep = (
        "id", "scenario_id", "reviewer_policy", "counterexample_clause",
        "profile", "relevant_rule_rows", "relevant_oracle_tag_rules",
        "checked_fields", "expected", "actual", "mismatches", "failure_kind",
        "sketch_review",
    )
    return {key: value[key] for key in keep if key in value}


def developer_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "usage": record.get("usage", {}),
        "error": record.get("error"),
        "parsed_keys": record.get("parsed_keys", []),
        "diffs": record.get("diffs", {}),
    }
    if "sketch_approval" in record:
        metadata["sketch_approval"] = record["sketch_approval"]
    if record.get("workspace_restored"):
        metadata["workspace_restored"] = True
    return metadata


def publish_generation(source: Path, destination: Path, record_path: Path,
                       arm: str) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for filename in FILES:
        shutil.copy2(source / filename, destination / filename)
    record = read_json(record_path)
    corpus = read_json(source / "corpus.json") if (source / "corpus.json").exists() else []
    active = None
    if (source / "active_failure.json").exists():
        active = compact_failure(read_json(source / "active_failure.json"))
    elif record.get("visible_failures_supplied"):
        active = compact_failure(record["visible_failures_supplied"])
    metadata = {
        "arm": arm,
        "source_generation": source.name,
        "corpus_ids": [case["id"] for case in corpus],
        "active_failure": active,
        "gate": compact_gate(record.get("gate", read_json(source / "gate.json"))),
        "developer": developer_metadata(record),
    }
    review = record.get("sketch_review")
    if review is None and (source / "sketch-review.json").exists():
        review = read_json(source / "sketch-review.json")
    if review is not None:
        metadata["sketch_review"] = compact_sketch_review(review)
        metadata["validation_passed"] = record.get(
            "validation_passed",
            metadata["gate"].get("passed") and review.get("passed"),
        )
    write_json(destination / "metadata.json", metadata)


def compact_evaluation(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "visible_passed": value["visible_passed"],
        "visible_total": value["visible_total"],
        "visible_reference": [compact_case(case) for case in value["visible_reference"]],
        "hidden_passed": value["hidden_passed"],
        "hidden_total": value["hidden_total"],
        "hidden": [compact_case(case) for case in value["hidden"]],
    }


def publish_spec_first(raw: Path, destination: Path, report: dict[str, Any]) -> None:
    destination.mkdir(parents=True)
    shutil.copy2(raw.parent.parent / "complete_spec.md", destination / "complete_spec.md")
    arm = report["arms"]["spec_first_repair"]
    arm_result = {
        "repair_attempts": arm["repair_attempts"],
        "visible_failure_feedback_events": arm["visible_failure_feedback_events"],
        "developer": arm["tokens"]["by_category"]["developer_spec_first_repair"],
        "tokens": arm["tokens"],
        "quality": arm["quality"],
        "final_gate": compact_gate(arm["final_gate"]),
        "evaluation": compact_evaluation(arm["evaluation"]),
    }
    if "final_sketch_review" in arm:
        arm_result["final_sketch_review"] = compact_sketch_review(
            arm["final_sketch_review"]
        )
        arm_result["final_validation_passed"] = arm["final_validation_passed"]
    write_json(destination / "results.json", {
        key: report[key]
        for key in (
            "run_id", "created_at", "mode", "provider", "model", "inference",
            "max_repairs", "visible_case_count",
        )
    } | {"arm": arm_result})
    for index, source in enumerate(sorted((raw / "spec-first-repair" / "generations").iterdir()), 1):
        publish_generation(
            source,
            destination / "generations" / source.name,
            raw / "spec-first-repair" / f"attempt-{index:02d}" / "record.json",
            "spec-first",
        )
    final = destination / "final"
    final.mkdir()
    for filename in FILES:
        shutil.copy2(raw / "spec-first-repair" / "workspace" / filename, final / filename)


def publish_adaptive(raw: Path, destination: Path, report: dict[str, Any]) -> None:
    destination.mkdir(parents=True)
    shutil.copy2(raw / "adaptive_candidate_manifest.json", destination / "protocol.json")

    cases_by_id = {
        case["id"]: case
        for case in json.loads((raw.parent.parent / "cases.json").read_text(encoding="utf-8"))
    }
    promoted_ids = report["discovery"]["promoted_ids"]
    write_json(destination / "promoted-corpus.json", [cases_by_id[item] for item in promoted_ids])

    results = {
        key: report[key]
        for key in (
            "run_id", "created_at", "mode", "provider", "model", "inference",
            "max_repairs_per_epoch", "candidate_pool", "discovery",
        )
    }
    results["arms"] = {}
    for name, arm in report["arms"].items():
        developer_category = "developer_iterative" if name == "sketch_ce" else f"developer_{name}"
        arm_result = {
            "metrics": arm["metrics"],
            "quality": arm["quality"],
            "tokens": arm["tokens"],
            "developer": arm["tokens"]["by_category"].get(developer_category, {}),
            "final_gate": compact_gate(arm["final_gate"]),
            "evaluation": compact_evaluation(arm["evaluation"]),
        }
        if "final_sketch_review" in arm:
            arm_result["final_sketch_review"] = compact_sketch_review(
                arm["final_sketch_review"]
            )
            arm_result["final_validation_passed"] = arm["final_validation_passed"]
        results["arms"][name] = arm_result
    write_json(destination / "results.json", results)

    for cycle in sorted((raw / "sketch-ce").glob("cycle-*/introduced-counterexample.json")):
        value = read_json(cycle)
        case = value["counterexample"]
        status = next(
            item["status"] for item in report["discovery"]["candidates"]
            if item["id"] == case["id"]
        )
        write_json(destination / "discovery" / f"{case['id']}.json", {
            "status": status,
            "counterexample": case,
            "evaluation_before_promotion": compact_case(value["evaluation"]),
            **({
                "sketch_review_before_promotion": compact_sketch_review(
                    read_json(cycle.parent / "introduced-sketch-review.json")
                )
            } if (cycle.parent / "introduced-sketch-review.json").exists() else {}),
        })

    sketch_generations = sorted((raw / "sketch-ce" / "generations").iterdir())
    for source in sketch_generations:
        publish_generation(
            source,
            destination / "arms" / "sketch-ce" / "generations" / source.name,
            source / "developer.json",
            "sketch-ce",
        )

    for raw_name, published_name in (
        ("replay-all", "replay-all"),
        ("reviewed-sketch", "evolved-sketch-rebuild"),
    ):
        for attempt in sorted((raw / raw_name).glob("epoch-*/attempt-*")):
            source = attempt / "generation"
            generation_name = f"{attempt.parent.name}-{attempt.name}"
            publish_generation(
                source,
                destination / "arms" / published_name / "generations" / generation_name,
                attempt / "record.json",
                published_name,
            )

    for raw_name, published_name in (
        ("sketch-ce", "sketch-ce"),
        ("replay-all", "replay-all"),
        ("reviewed-sketch", "evolved-sketch-rebuild"),
    ):
        final = destination / "arms" / published_name / "final"
        final.mkdir(parents=True)
        for filename in FILES:
            shutil.copy2(raw / raw_name / "workspace" / filename, final / filename)


def publish(raw: Path, destination: Path) -> None:
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")
    report = read_json(raw / "report.json")
    if report.get("mode") == "spec_first_repair_only":
        publish_spec_first(raw, destination, report)
    else:
        publish_adaptive(raw, destination, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    publish(args.raw.resolve(), args.destination.resolve())


if __name__ == "__main__":
    main()
