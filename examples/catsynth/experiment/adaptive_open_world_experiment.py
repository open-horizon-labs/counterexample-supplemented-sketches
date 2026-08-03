"""Prospective adaptive open-world comparison for CatSynth.

The Sketch-CE arm probes a pre-registered candidate pool in order and promotes
only observed failures. The exact promoted stream and evolved sketch checkpoints
are then replayed through two rebuild controls:

* replay_all: clean-room cumulative counterexamples from the initial sketch;
* reviewed_sketch: clean-room generation from the evolved Sketch-CE sketch.

Rejected coverage probes are never sent to a Developer or either control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import run_experiment as exp
except ModuleNotFoundError:  # Imported as experiment.adaptive_open_world_experiment.
    from experiment import run_experiment as exp

from catsynth.codex_app_server import (
    DEFAULT_CODEX_MODEL,
    CodexAppServerClient,
    CodexAppServerError,
)


HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "adaptive_candidate_manifest.json"
CONTROL_ARMS = ("replay_all", "reviewed_sketch")


def load_preregistered_candidates() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = HERE / manifest["source"]
    source_bytes = source.read_bytes()
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if actual_hash != manifest["source_sha256"]:
        raise exp.ExperimentError(
            "candidate source changed after pre-registration: "
            f"expected {manifest['source_sha256']}, got {actual_hash}"
        )
    cases = json.loads(source_bytes)
    by_id = {case["id"]: case for case in cases}
    ids = manifest["candidate_ids"]
    if len(ids) != len(set(ids)):
        raise exp.ExperimentError("candidate manifest contains duplicate IDs")
    missing = [case_id for case_id in ids if case_id not in by_id]
    if missing:
        raise exp.ExperimentError(f"candidate manifest IDs missing from source: {missing}")
    return manifest, [by_id[case_id] for case_id in ids]


def diff_churn(diffs: dict[str, str]) -> int:
    return sum(
        1
        for diff in diffs.values()
        for line in diff.splitlines()
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    )


def records_for_iterative(arm: dict[str, Any]) -> list[dict[str, Any]]:
    records = list(arm["initial_generation"]["attempts"])
    for cycle in arm["cycles"]:
        records.extend(cycle["attempts"])
    return records


def reset_workspace(workspace: Path, sketch: str) -> None:
    exp.baseline_workspace(workspace)
    (workspace / "SKETCH.md").write_text(sketch.rstrip() + "\n", encoding="utf-8")


def compact_repair_failures(
    cumulative: list[dict[str, Any]],
    gate: dict[str, Any],
    record: dict[str, Any],
    sketch_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep every failure while storing the shared breed catalog only once."""
    packets = exp.one_shot_failure_packets(
        cumulative, gate, record, sketch_review,
    )
    compact = []
    for packet in packets:
        item = dict(packet)
        breeds = item.pop("candidate_breeds", None)
        if breeds is not None:
            item["candidate_breed_names"] = [breed.get("name") for breed in breeds]
            item["candidate_breed_data"] = "See shared_breed_catalog."
        compact.append(item)
    breeds, _, _ = exp.fixtures()
    return {"shared_breed_catalog": breeds, "failures": compact}


def run_rebuild_epoch(
    arm: str,
    root: Path,
    workspace: Path,
    epoch: int,
    cumulative: list[dict[str, Any]],
    authoritative_sketch: str,
    client: exp.ChatClient,
    ledger: exp.Ledger,
    max_repairs: int,
    sketch_approver: exp.SketchApprover,
    review_adjudicator: exp.SketchReviewAdjudicator,
) -> dict[str, Any]:
    reset_workspace(workspace, authoritative_sketch)
    failures = None
    attempts = []
    gate: dict[str, Any] = {}
    sketch_review: dict[str, Any] = {}
    validation_passed = False
    first_gate = None
    first_sketch_review = None
    authoritative_corpus = (
        exp.complete_case_packets(cumulative)
        if arm == "replay_all" and epoch > 0
        else None
    )
    for attempt in range(max_repairs + 1):
        if attempt == 0 and epoch == 0:
            phase = "initial"
        elif attempt == 0 and arm == "replay_all":
            phase = "one_shot"
        elif attempt == 0:
            phase = "initial"
        else:
            phase = "one_shot_repair"
        parsed, record = exp.call_developer_with_approval(
            workspace,
            cumulative,
            failures,
            arm,
            phase,
            f"epoch-{epoch:02d}-attempt-{attempt + 1:02d}",
            client,
            ledger,
            sketch_approver,
            complete_corpus=authoritative_corpus,
        )
        if parsed:
            try:
                validation = exp.run_validation(
                    workspace,
                    cumulative,
                    client,
                    ledger,
                    f"{arm}-epoch-{epoch}-attempt-{attempt + 1}",
                    review_adjudicator,
                )
                gate = validation["gate"]
                sketch_review = validation["sketch_review"]
                validation_passed = validation["passed"]
            except Exception as exc:
                gate = {
                    "passed": False,
                    "passed_count": 0,
                    "total": len(cumulative) + 1,
                    "cases": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
                sketch_review = exp.failed_sketch_review(
                    f"{type(exc).__name__}: {exc}", len(cumulative) + 1,
                )
                validation_passed = False
        else:
            gate = {
                "passed": False,
                "passed_count": 0,
                "total": len(cumulative) + 1,
                "cases": [],
                "error": record.get("error"),
            }
            sketch_review = exp.failed_sketch_review(
                record.get("error"), len(cumulative) + 1,
            )
            validation_passed = False
        if first_gate is None:
            first_gate = json.loads(json.dumps(gate))
            first_sketch_review = json.loads(json.dumps(sketch_review))
        record["gate"] = gate
        record["sketch_review"] = sketch_review
        record["validation_passed"] = validation_passed
        record["visible_failures_supplied"] = failures or []
        attempt_root = root / f"epoch-{epoch:02d}" / f"attempt-{attempt + 1:02d}"
        exp.write_json(attempt_root / "record.json", record)
        exp.snapshot_generation(
            attempt_root / "generation",
            workspace,
            cumulative,
            gate,
            record,
            failures,
            sketch_review,
        )
        attempts.append(record)
        if validation_passed:
            break
        failures = compact_repair_failures(
            cumulative, gate, record, sketch_review,
        )
    if not validation_passed:
        raise exp.ExperimentError(
            f"{arm} did not close both checks in epoch {epoch} after {max_repairs} repairs"
        )
    current_id = cumulative[-1]["id"] if cumulative else None
    prior_regressions = [
        item["id"]
        for item in (first_gate or {}).get("cases", [])
        if not item.get("passed") and item["id"] != current_id
    ]
    prior_review_failures = [
        item["id"]
        for item in (first_sketch_review or {}).get("cases", [])
        if not item.get("passed") and item["id"] != current_id
    ]
    return {
        "epoch": epoch,
        "attempts": attempts,
        "repair_attempts": len(attempts) - 1,
        "first_gate": first_gate,
        "first_sketch_review": first_sketch_review,
        "final_gate": gate,
        "final_sketch_review": sketch_review,
        "final_validation_passed": validation_passed,
        "prior_regressions_on_first_attempt": prior_regressions,
        "prior_sketch_review_failures_on_first_attempt": prior_review_failures,
        "artifact_churn_lines": sum(diff_churn(item.get("diffs", {})) for item in attempts),
    }


def run_rebuild_arm(
    arm: str,
    root: Path,
    promoted: list[dict[str, Any]],
    sketch_checkpoints: list[str],
    client: exp.ChatClient,
    max_repairs: int,
    sketch_approver: exp.SketchApprover,
    review_adjudicator: exp.SketchReviewAdjudicator,
) -> tuple[dict[str, Any], exp.Ledger]:
    workspace = root / "workspace"
    ledger = exp.Ledger()
    epochs = [
        run_rebuild_epoch(
            arm,
            root,
            workspace,
            0,
            [],
            exp.INITIAL_SKETCH_PATH.read_text(encoding="utf-8"),
            client,
            ledger,
            max_repairs,
            sketch_approver,
            review_adjudicator,
        )
    ]
    for index, case in enumerate(promoted, 1):
        sketch = (
            exp.INITIAL_SKETCH_PATH.read_text(encoding="utf-8")
            if arm == "replay_all"
            else sketch_checkpoints[index - 1]
        )
        epochs.append(
            run_rebuild_epoch(
                arm,
                root,
                workspace,
                index,
                promoted[:index],
                sketch,
                client,
                ledger,
                max_repairs,
                sketch_approver,
                review_adjudicator,
            )
        )
    final_epoch = epochs[-1]
    return {
        "workspace": str(workspace),
        "epochs": epochs,
        "final_gate": final_epoch["final_gate"],
        "final_sketch_review": final_epoch["final_sketch_review"],
        "final_validation_passed": final_epoch["final_validation_passed"],
    }, ledger


def finish_arm(
    name: str,
    arm: dict[str, Any],
    promoted: list[dict[str, Any]],
    client: exp.ChatClient,
    ledger: exp.Ledger,
) -> None:
    if not arm.get("final_validation_passed"):
        raise exp.ExperimentError(
            f"{name} failed its final deterministic gate or sketch review"
        )
    workspace = Path(arm["workspace"])
    arm["evaluation"] = exp.final_evaluation(workspace, promoted, client, ledger, name)
    arm["quality"] = exp.quality_metrics(workspace)
    arm["tokens"] = ledger.totals()
    if name == "sketch_ce":
        records = records_for_iterative(arm)
        arm["metrics"] = {
            "rebuilds": 1,
            "repair_attempts": len(records) - 1 - len(arm["promoted"]),
            "prior_regressions_on_first_attempt": sum(
                1
                for cycle in arm["cycles"]
                if cycle["status"] == "promoted"
                for attempt in cycle["attempts"][:1]
                for item in attempt["gate"].get("cases", [])
                if not item.get("passed") and item["id"] != cycle["case"]
            ),
            "prior_sketch_review_failures_on_first_attempt": sum(
                1
                for cycle in arm["cycles"]
                if cycle["status"] == "promoted"
                for attempt in cycle["attempts"][:1]
                for item in attempt["sketch_review"].get("cases", [])
                if not item.get("passed") and item["id"] != cycle["case"]
            ),
            "artifact_churn_lines": sum(
                diff_churn(record.get("diffs", {})) for record in records
            ),
        }
    else:
        epochs = arm["epochs"]
        arm["metrics"] = {
            "rebuilds": len(epochs),
            "repair_attempts": sum(epoch["repair_attempts"] for epoch in epochs),
            "prior_regressions_on_first_attempt": sum(
                len(epoch["prior_regressions_on_first_attempt"]) for epoch in epochs
            ),
            "prior_sketch_review_failures_on_first_attempt": sum(
                len(epoch["prior_sketch_review_failures_on_first_attempt"])
                for epoch in epochs
            ),
            "artifact_churn_lines": sum(
                epoch["artifact_churn_lines"] for epoch in epochs
            ),
        }


def developer_bucket(arm: dict[str, Any], name: str) -> dict[str, Any]:
    category = "developer_iterative" if name == "sketch_ce" else f"developer_{name}"
    return arm["tokens"]["by_category"].get(category, {})


def markdown_report(report: dict[str, Any]) -> str:
    names = ("replay_all", "reviewed_sketch", "sketch_ce")
    arms = [report["arms"][name] for name in names]
    post_acceptance_tokens = [
        sum(
            call["total_tokens"]
            for call in arm["tokens"]["calls"]
            if ":reference:" in call["label"] or ":hidden:" in call["label"]
        )
        for arm in arms
    ]
    runtime_acceptance_tokens = [
        arm["tokens"]["by_category"].get("runtime_oracle", {}).get("total_tokens", 0)
        - post
        for arm, post in zip(arms, post_acceptance_tokens)
    ]
    specification_tokens = [
        arm["tokens"]["by_category"].get("spec_oracle", {}).get("total_tokens", 0)
        for arm in arms
    ]
    sketch_review_tokens = [
        arm["tokens"]["by_category"].get("sketch_reviewer", {}).get("total_tokens", 0)
        for arm in arms
    ]
    acceptance_tokens = [
        developer_bucket(arm, name).get("total_tokens", 0)
        + runtime + specification + sketch_review
        for arm, name, runtime, specification, sketch_review in zip(
            arms, names, runtime_acceptance_tokens, specification_tokens,
            sketch_review_tokens,
        )
    ]
    lines = [
        "# Prospective adaptive open-world comparison",
        "",
        f"Model: `{report['model']}` at `{report['inference']['effort']}` effort",
        "",
        f"Pre-registered candidates: {report['candidate_pool']['count']}  ",
        f"Accepted counterexamples: {report['discovery']['promoted_count']}  ",
        f"Passing coverage probes: {report['discovery']['coverage_count']}",
        "",
        "| Measure | Replay all | Evolved-sketch rebuild | Sketch-CE |",
        "|---|---:|---:|---:|",
    ]
    rows = [
        ("Tokens through visible acceptance", acceptance_tokens),
        ("Developer calls", [developer_bucket(arm, name).get("calls", 0) for arm, name in zip(arms, names)]),
        ("Developer tokens", [developer_bucket(arm, name).get("total_tokens", 0) for arm, name in zip(arms, names)]),
        ("Runtime Oracle tokens through acceptance", runtime_acceptance_tokens),
        ("Specification Oracle tokens", specification_tokens),
        ("Sketch Reviewer tokens", sketch_review_tokens),
        ("Post-acceptance evaluation tokens", post_acceptance_tokens),
        ("Total recorded tokens, including evaluation", [arm["tokens"]["overall"]["total_tokens"] for arm in arms]),
        ("Repair attempts", [arm["metrics"]["repair_attempts"] for arm in arms]),
        ("Rebuilds", [arm["metrics"]["rebuilds"] for arm in arms]),
        ("First-attempt prior regressions", [arm["metrics"]["prior_regressions_on_first_attempt"] for arm in arms]),
        ("First-attempt prior sketch-review failures", [
            arm["metrics"]["prior_sketch_review_failures_on_first_attempt"]
            for arm in arms
        ]),
        ("Artifact churn lines", [arm["metrics"]["artifact_churn_lines"] for arm in arms]),
        ("Final strategy LOC", [arm["quality"]["strategy_loc"] for arm in arms]),
        ("Final decision nodes", [arm["quality"]["decision_nodes"] for arm in arms]),
        ("Final changed lines from baseline", [arm["quality"]["changed_lines_from_baseline"] for arm in arms]),
        ("Visible accepted CEs", [
            f"{arm['evaluation']['visible_passed']}/{arm['evaluation']['visible_total']}"
            for arm in arms
        ]),
        ("Withheld cases", [
            f"{arm['evaluation']['hidden_passed']}/{arm['evaluation']['hidden_total']}"
            for arm in arms
        ]),
    ]
    for label, values in rows:
        lines.append(f"| {label} | {values[0]} | {values[1]} | {values[2]} |")
    lines.extend(["", "## Candidate disposition", "", "| Candidate | Result |", "|---|---|"])
    for item in report["discovery"]["candidates"]:
        disposition = "accepted CE" if item["status"] == "promoted" else "coverage, not accepted"
        lines.append(f"| `{item['id']}` | {disposition} |")
    lines.extend([
        "",
        "The candidate cases and authoritative expected outputs were frozen before the run and",
        "treated as a simulated operator-approved stream. This stands in for the live method's",
        "approval boundary; the model cannot approve policy.",
        "Only failures were accepted or sent to Developer, and every accepted CE changed the",
        "Sketch-CE sketch. CatSynth uses every accepted CE as a regression (R = A). Replay-all",
        "received the initial sketch plus the cumulative accepted archive. Evolved-sketch rebuild",
        "received only the current evolved sketch checkpoint. Withheld cases were evaluated",
        "after visible acceptance and were never repair input.",
        "Each repair advanced only after the deterministic gate and separate model-backed",
        "review against the current sketch both passed for the active case and R.",
        "Tokens through acceptance include Developer edits, Runtime Oracle checks,",
        "Specification Oracle rule proposals, and Sketch Reviewer calls. Post-acceptance",
        "evaluation is separate.",
        "Sketch-CE pays to evaluate the external candidates and propose rules for failures.",
        "The controls inherit the resulting promotion schedule, so their totals have a narrower",
        "boundary and are not end-to-end price alternatives.",
        "Lower cumulative churn measures less rework, not final maintainability. The final",
        "Sketch-CE strategy is larger and has more decision nodes than either rebuild. The",
        "evolved-sketch control tests whether reviewed synthesis can carry policy without",
        "replaying the CE archive as generation context.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    parser.add_argument("--max-repairs", type=int, default=12)
    args = parser.parse_args()

    manifest, candidates = load_preregistered_candidates()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (HERE / "artifacts" / f"adaptive-open-world-{run_id}")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(MANIFEST_PATH, output / MANIFEST_PATH.name)
    client = CodexAppServerClient(model=args.model, cwd=HERE, timeout=600)
    sketch_approver = exp.ManualSketchApprover(output)
    review_adjudicator = exp.ManualSketchReviewAdjudicator(output)
    try:
        models = client.list_models()
        if args.model not in models:
            raise SystemExit(f"model {args.model!r} unavailable; available: {models}")

        iterative_ledger = exp.Ledger()
        sketch_ce = exp.run_iterative(
            output / "sketch-ce", candidates, client, iterative_ledger,
            args.max_repairs, sketch_approver, review_adjudicator,
        )
        promoted = sketch_ce["promoted"]
        promoted_cycles = [
            cycle for cycle in sketch_ce["cycles"] if cycle["status"] == "promoted"
        ]
        sketch_checkpoints = [cycle["sketch_after"] for cycle in promoted_cycles]
        if [case["id"] for case in promoted] != [cycle["case"] for cycle in promoted_cycles]:
            raise exp.ExperimentError("promoted stream and sketch checkpoints diverged")

        replay_all, replay_ledger = run_rebuild_arm(
            "replay_all",
            output / "replay-all",
            promoted,
            sketch_checkpoints,
            client,
            args.max_repairs,
            sketch_approver,
            review_adjudicator,
        )
        reviewed_sketch, reviewed_ledger = run_rebuild_arm(
            "reviewed_sketch",
            output / "reviewed-sketch",
            promoted,
            sketch_checkpoints,
            client,
            args.max_repairs,
            sketch_approver,
            review_adjudicator,
        )

        arms = {
            "replay_all": replay_all,
            "reviewed_sketch": reviewed_sketch,
            "sketch_ce": sketch_ce,
        }
        ledgers = {
            "replay_all": replay_ledger,
            "reviewed_sketch": reviewed_ledger,
            "sketch_ce": iterative_ledger,
        }
        for name, arm in arms.items():
            finish_arm(name, arm, promoted, client, ledgers[name])
            exp.write_json(output / name.replace("_", "-") / "summary.json", arm)

        candidate_disposition = [
            {"id": cycle["case"], "status": cycle["status"]}
            for cycle in sketch_ce["cycles"]
        ]
        report = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "prospective_adaptive_open_world",
            "provider": client.provider,
            "model": args.model,
            "inference": {
                "effort": client.effort,
                "summary": client.summary,
                "personality": client.personality,
                "tools": False,
                "environment_access": False,
                "model_fallback": False,
            },
            "max_repairs_per_epoch": args.max_repairs,
            "candidate_pool": {
                "count": len(candidates),
                "manifest": manifest,
            },
            "discovery": {
                "promoted_count": len(promoted),
                "coverage_count": len(candidates) - len(promoted),
                "promoted_ids": [case["id"] for case in promoted],
                "candidates": candidate_disposition,
                "publication_gate_met": len(promoted) >= 5,
            },
            "arms": arms,
        }
        exp.write_json(output / "report.json", report)
        (output / "REPORT.md").write_text(markdown_report(report), encoding="utf-8")
        print(output)
    except CodexAppServerError as exc:
        exp.write_json(output / "provider-error.json", {
            "error": str(exc),
            "transcript": exc.transcript,
        })
        raise
    finally:
        client.close()


if __name__ == "__main__":
    main()
