"""Three-arm open-world spike for Sketch-CE double-loop learning.

The world reveals the same reviewed discovery schedule to every arm:

* replay_all rebuilds from the initial sketch plus all raw discoveries;
* reviewed_sketch rebuilds from the current reviewer-approved sketch;
* sketch_ce retains code and prompt while receiving the approved sketch and
  only the active discovery.

No arm receives future discoveries or hidden sibling cases.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import run_experiment as exp
except ModuleNotFoundError:  # Imported as experiment.open_world_spike in tests.
    from experiment import run_experiment as exp
from catsynth.codex_app_server import DEFAULT_CODEX_MODEL, CodexAppServerClient


HERE = Path(__file__).resolve().parent
SCHEDULE_PATH = HERE / "open_world_schedule.json"
ARM_NAMES = ("replay_all", "reviewed_sketch", "sketch_ce")
SPIKE_HIDDEN_IDS = {
    "hidden-allergy-medium",
    "hidden-soft-single-candidate",
    "hidden-soft-compose",
    "hidden-travel-synonym",
    "hidden-negated-travel",
    "hidden-hard-narrative-conflict",
    "hidden-duplicate-soft-synonym",
    "hidden-post-soft-tiebreak",
}


def load_schedule() -> list[dict[str, Any]]:
    return json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))


def case_map() -> dict[str, dict[str, Any]]:
    cases = json.loads(exp.CASES_PATH.read_text(encoding="utf-8"))
    return {case["id"]: case for case in cases}


def approved_sketch(events: list[dict[str, Any]]) -> str:
    initial_text = exp.INITIAL_SKETCH_PATH.read_text(encoding="utf-8")
    if not events:
        return initial_text
    initial = initial_text.rstrip()
    additions = [
        "",
        "## Reviewer-approved world discoveries",
        "",
        "Clauses are chronological. A later approved revision narrows or overrides earlier wording.",
    ]
    for event in events:
        clause = event.get("approved_clause")
        if clause:
            additions.extend([
                "",
                f"### Epoch {event['epoch']}: {event['feedback_destination']}",
                "",
                clause,
            ])
    return initial + "\n" + "\n".join(additions).rstrip() + "\n"


def discovery_packet(event: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    packet = exp.complete_case_packets([case])[0]
    return {
        "epoch": event["epoch"],
        "loop_type": event["loop_type"],
        "feedback_destination": event["feedback_destination"],
        "reviewer_decision": event["decision"],
        "approved_clause": event.get("approved_clause"),
        "reviewed_discovery": packet,
    }


def world_messages(arm: str, workspace: Path, epoch: int,
                   current_approved_sketch: str,
                   accumulated_discoveries: list[dict[str, Any]],
                   active_discovery: Any,
                   failures: Any) -> list[dict[str, str]]:
    strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    prompt = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    repair = failures is not None
    if arm == "replay_all":
        policy_context = {
            "initial_sketch": exp.INITIAL_SKETCH_PATH.read_text(encoding="utf-8"),
            "accumulated_reviewed_discoveries": accumulated_discoveries,
        }
        description = (
            "Rebuild the complete implementation from the initial sketch and every reviewed "
            "world discovery so far. Do not assume prior generated files survive between epochs."
        )
    elif arm == "reviewed_sketch":
        policy_context = {"current_reviewer_approved_sketch": current_approved_sketch}
        description = (
            "Rebuild the complete implementation from the current reviewer-approved sketch. "
            "Do not rely on raw discovery history or a prior implementation."
        )
    elif arm == "sketch_ce":
        policy_context = {
            "current_reviewer_approved_sketch": current_approved_sketch,
            "active_reviewed_discovery": active_discovery,
        }
        description = (
            "Revise the retained implementation for the active reviewed discovery under the "
            "current reviewer-approved sketch while preserving prior gated behavior."
        )
    else:
        raise ValueError(f"unknown arm {arm!r}")
    payload = {
        "arm": arm,
        "epoch": epoch,
        "phase": "repair" if repair else "epoch_generation",
        "task": (
            description + " Return compact JSON with exactly two complete-file string keys: "
            "strategy_py and oracle_prompt. Do not return a diff or markdown."
        ),
        "known_code_contract": exp.known_code_contract(),
        "policy_context": policy_context,
        "current_strategy_py": strategy,
        "current_oracle_prompt": prompt,
        "visible_gate_failures": failures,
        "constraints": [
            "Reviewer decisions and approved sketch clauses are authoritative.",
            "Do not revise governing policy or invent future discoveries.",
            "Do not inspect or branch on concrete scenario IDs, case IDs, or named fixture outputs.",
            "Do not import modules or access files, tools, environment state, or the network.",
        ],
    }
    system = (
        "You are the Developer in an open-world repository experiment. Implement only the "
        "reviewed policy known at this epoch. JSON only."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, indent=2)},
    ]


def call_world_developer(arm: str, workspace: Path, epoch: int,
                         current_approved_sketch: str,
                         accumulated_discoveries: list[dict[str, Any]],
                         active_discovery: Any, failures: Any,
                         label: str, client: exp.ChatClient,
                         ledger: exp.Ledger) -> tuple[dict, dict]:
    messages = world_messages(
        arm, workspace, epoch, current_approved_sketch,
        accumulated_discoveries, active_discovery, failures,
    )
    result = client.chat(
        messages, max_tokens=8000, temperature=0,
        extra={"output_schema": exp.SPEC_DEVELOPER_OUTPUT_SCHEMA},
    )
    ledger.add(f"developer_{arm}", label, result)
    record = exp.result_record(result)
    record["input_chars"] = sum(len(message["content"]) for message in messages)
    try:
        parsed = exp.extract_json(result.content)
        diffs = exp.apply_spec_developer(workspace, parsed)
    except Exception as exc:
        record.update({"error": f"{type(exc).__name__}: {exc}",
                       "parsed_keys": [], "diffs": {}})
        return {}, record
    record.update({"error": None, "parsed_keys": sorted(parsed), "diffs": diffs})
    return parsed, record


def reset_implementation(workspace: Path) -> None:
    shutil.copy2(exp.BASELINE / "strategy.py", workspace / "strategy.py")
    shutil.copy2(exp.BASELINE / "oracle_prompt.txt", workspace / "oracle_prompt.txt")


def token_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = exp.Ledger.TOKEN_KEYS
    return {
        "calls": after["overall"]["calls"] - before["overall"]["calls"],
        **{
            key: after["overall"][key] - before["overall"][key]
            for key in keys
        },
    }


def changed_lines(before: str, after: str) -> int:
    return sum(
        1 for line in difflib.ndiff(before.splitlines(), after.splitlines())
        if line.startswith(("+ ", "- "))
    )


def introduced_case_failed(gate: dict[str, Any], case_id: str) -> bool:
    introduced = [item for item in gate["cases"] if item["id"] == case_id]
    if len(introduced) != 1:
        raise exp.ExperimentError(
            f"pre-discovery gate did not return exactly one {case_id} result"
        )
    return not introduced[0]["passed"]


def run_epoch(arm: str, output: Path, workspace: Path, epoch: int,
              cumulative_cases: list[dict[str, Any]],
              current_approved_sketch: str,
              accumulated_discoveries: list[dict[str, Any]],
              active_discovery: Any, client: exp.ChatClient,
              ledger: exp.Ledger, max_repairs: int,
              rebuild: bool) -> dict[str, Any]:
    before_tokens = ledger.totals()
    before_strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    if rebuild:
        reset_implementation(workspace)
    sketch_for_workspace = (
        exp.INITIAL_SKETCH_PATH.read_text(encoding="utf-8")
        if arm == "replay_all" else current_approved_sketch
    )
    (workspace / "SKETCH.md").write_text(sketch_for_workspace, encoding="utf-8")

    active_rules = {
        rule_id for case in cumulative_cases for rule_id in case.get("rule_ids", [])
    }
    attempts = []
    failures = None
    first_gate = None
    gate: dict[str, Any] = {}
    for attempt in range(max_repairs + 1):
        parsed, record = call_world_developer(
            arm, workspace, epoch, current_approved_sketch,
            accumulated_discoveries, active_discovery, failures,
            f"epoch-{epoch:02d}-attempt-{attempt + 1:02d}", client, ledger,
        )
        if parsed:
            try:
                gate = exp.run_gate(
                    workspace, cumulative_cases, client, ledger,
                    f"{arm}-epoch-{epoch}-attempt-{attempt + 1}",
                )
            except Exception as exc:
                gate = {
                    "passed": False, "passed_count": 0,
                    "total": len(cumulative_cases) + 1, "cases": [],
                    "error": f"{type(exc).__name__}: {exc}",
                    "scope": "world epoch runtime failure",
                }
        else:
            gate = {
                "passed": False, "passed_count": 0,
                "total": len(cumulative_cases) + 1, "cases": [],
                "error": record.get("error"),
                "scope": "world Developer output contract failure",
            }
        if first_gate is None:
            first_gate = copy.deepcopy(gate)
        record["gate"] = gate
        record["repair_number"] = attempt
        record["visible_failures_supplied"] = failures or []
        attempt_dir = output / f"epoch-{epoch:02d}" / f"attempt-{attempt + 1:02d}"
        exp.write_json(attempt_dir / "record.json", record)
        exp.snapshot_generation(
            attempt_dir / "generation", workspace, cumulative_cases,
            gate, record, failures,
        )
        attempts.append(record)
        if gate["passed"]:
            break
        failures = exp.spec_failure_packets(
            cumulative_cases, gate, active_rules, record,
        )
    if not gate.get("passed"):
        raise exp.ExperimentError(
            f"{arm} did not close epoch {epoch} after {max_repairs} repairs"
        )

    current_case_id = (
        active_discovery["reviewed_discovery"]["id"] if active_discovery else None
    )
    prior_regressions = [
        item["id"] for item in (first_gate or {}).get("cases", [])
        if not item.get("passed") and item.get("id") != current_case_id
    ]
    after_strategy = (workspace / "strategy.py").read_text(encoding="utf-8")
    return {
        "epoch": epoch,
        "rebuild": rebuild,
        "attempts": attempts,
        "repair_attempts": len(attempts) - 1,
        "first_gate": first_gate,
        "final_gate": gate,
        "prior_regressions_on_first_attempt": prior_regressions,
        "first_request_chars": attempts[0]["input_chars"],
        "history_chars": len(json.dumps(accumulated_discoveries)),
        "approved_sketch_chars": len(current_approved_sketch),
        "code_churn_lines": changed_lines(before_strategy, after_strategy),
        "token_delta": token_delta(before_tokens, ledger.totals()),
    }


def evaluate_hidden_subset(workspace: Path, client: exp.ChatClient,
                           ledger: exp.Ledger, arm: str) -> dict[str, Any]:
    cases = [case for case in exp.hidden_cases() if case["id"] in SPIKE_HIDDEN_IDS]
    breeds, _, all_rules = exp.fixtures()
    source = (workspace / "strategy.py").read_text(encoding="utf-8")
    recommend = exp.load_recommend(source)
    prompt_text = (workspace / "oracle_prompt.txt").read_text(encoding="utf-8")
    results = []
    for case in cases:
        profile = case["profile"]
        expected = exp.reference_expected(
            profile, case["expected_tags"], case["rule_ids"],
            case.get("breed_names"),
        )
        tags = []
        trace = None
        try:
            if profile.get("narrative_note"):
                tags, trace = exp.oracle_tags(
                    prompt_text, profile["narrative_note"], client, ledger,
                    f"{arm}:spike-hidden:{case['id']}",
                )
            rules = [all_rules[rule_id] for rule_id in case["rule_ids"]]
            selected = None if "breed_names" not in case else set(case["breed_names"])
            candidate_breeds = [
                breed for breed in breeds
                if selected is None or breed["name"] in selected
            ]
            candidate = exp.normalize_candidate(
                recommend(profile, candidate_breeds, rules, tags)
            )
            actual = {
                "operation": candidate["operation"], "breed": candidate["breed"],
                "cited_rules": candidate["cited_rules"], "oracle_tags": tags,
            }
            results.append({"id": case["id"], "expected": expected,
                            "actual": actual, "passed": actual == expected,
                            "oracle_trace": trace})
        except Exception as exc:
            results.append({"id": case["id"], "expected": expected,
                            "actual": None, "passed": False,
                            "error": f"{type(exc).__name__}: {exc}",
                            "oracle_trace": trace})
    return {
        "cases": results,
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
    }


def run_arm(arm: str, output: Path, schedule: list[dict[str, Any]],
            cases_by_id: dict[str, dict[str, Any]], client: exp.ChatClient,
            max_repairs: int) -> dict[str, Any]:
    workspace = output / "workspace"
    exp.baseline_workspace(workspace)
    ledger = exp.Ledger()
    epochs = []
    discoveries = []
    cumulative_cases = []
    initial_sketch = approved_sketch([])

    epochs.append(run_epoch(
        arm, output, workspace, 0, [], initial_sketch, [], None,
        client, ledger, max_repairs, rebuild=True,
    ))

    for event in schedule:
        case = cases_by_id[event["case_id"]]
        packet = discovery_packet(event, case)
        pre_discovery_gate = None
        if arm == "sketch_ce":
            pre_discovery_gate = exp.run_gate(
                workspace, [case], client, ledger,
                f"{arm}-epoch-{event['epoch']}-pre-discovery",
            )
        discoveries.append(packet)
        cumulative_cases.append(case)
        current_sketch = approved_sketch(schedule[:event["epoch"]])
        epoch_result = run_epoch(
            arm, output, workspace, event["epoch"], cumulative_cases,
            current_sketch, discoveries, packet, client, ledger, max_repairs,
            rebuild=arm in {"replay_all", "reviewed_sketch"},
        )
        epoch_result["pre_discovery_gate"] = pre_discovery_gate
        if pre_discovery_gate is None:
            epoch_result["was_counterexample_to_incumbent"] = None
        else:
            epoch_result["was_counterexample_to_incumbent"] = introduced_case_failed(
                pre_discovery_gate, case["id"]
            )
        epochs.append(epoch_result)

    final_gate = exp.run_gate(
        workspace, cumulative_cases, client, ledger, f"{arm}-spike-final",
    )
    hidden = evaluate_hidden_subset(workspace, client, ledger, arm)
    quality = exp.quality_metrics(workspace)
    tokens = ledger.totals()
    developer = tokens["by_category"].get(f"developer_{arm}", {})
    return {
        "workspace": str(workspace),
        "epochs": epochs,
        "final_gate": final_gate,
        "hidden": hidden,
        "quality": quality,
        "tokens": tokens,
        "developer": developer,
        "metrics": {
            "epochs": len(epochs),
            "rebuilds": sum(1 for epoch in epochs if epoch["rebuild"]),
            "repair_attempts": sum(epoch["repair_attempts"] for epoch in epochs),
            "first_attempt_prior_regressions": sum(
                len(epoch["prior_regressions_on_first_attempt"]) for epoch in epochs
            ),
            "first_request_chars_total": sum(
                epoch["first_request_chars"] for epoch in epochs
            ),
            "code_churn_lines_total": sum(epoch["code_churn_lines"] for epoch in epochs),
            "scheduled_cases_that_failed_incumbent": sum(
                epoch.get("was_counterexample_to_incumbent") is True for epoch in epochs
            ),
            "scheduled_cases_already_covered": sum(
                epoch.get("was_counterexample_to_incumbent") is False for epoch in epochs
            ),
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Open-world Sketch-CE spike",
        "",
        f"Model: `{report['model']}` at `{report['inference']['effort']}` effort",
        "",
        "| Measure | Replay all | Reviewed sketch rebuild | Sketch-CE |",
        "|---|---:|---:|---:|",
    ]
    arms = report["arms"]
    values = [arms[name] for name in ARM_NAMES]
    rows = [
        ("Developer calls", [arm["developer"].get("calls", 0) for arm in values]),
        ("Developer tokens", [arm["developer"].get("total_tokens", 0) for arm in values]),
        ("Repair attempts", [arm["metrics"]["repair_attempts"] for arm in values]),
        ("Rebuilds", [arm["metrics"]["rebuilds"] for arm in values]),
        ("First-attempt prior regressions", [
            arm["metrics"]["first_attempt_prior_regressions"] for arm in values
        ]),
        ("First-request characters", [
            arm["metrics"]["first_request_chars_total"] for arm in values
        ]),
        ("Code churn lines", [arm["metrics"]["code_churn_lines_total"] for arm in values]),
        ("Scheduled cases failing incumbent", [
            "—", "—", values[2]["metrics"]["scheduled_cases_that_failed_incumbent"]
        ]),
        ("Scheduled cases already covered", [
            "—", "—", values[2]["metrics"]["scheduled_cases_already_covered"]
        ]),
        ("Final gate", [
            f"{arm['final_gate']['passed_count']}/{arm['final_gate']['total']}"
            for arm in values
        ]),
        ("Hidden siblings", [
            f"{arm['hidden']['passed']}/{arm['hidden']['total']}" for arm in values
        ]),
    ]
    for label, row in rows:
        lines.append(f"| {label} | {row[0]} | {row[1]} | {row[2]} |")
    validity = report["validity"]
    lines.extend([
        "",
        f"Validity: **{validity['classification']}**. "
        f"{validity['genuine_counterexamples']}/{validity['scheduled_discoveries']} "
        "scheduled discoveries failed the incumbent Sketch-CE implementation; "
        f"{validity['already_covered']} were already covered. The passing probes were still "
        "sent to the Developer and remain included in every cost and churn total. Do not "
        "describe this run as seven counterexample cycles.",
        "",
        "All arms received the same chronological reviewer decisions. Replay-all rebuilt from",
        "the initial sketch and raw history; reviewed-sketch rebuilt from the approved sketch;",
        "Sketch-CE retained implementation state and received only the active discovery.",
        "Hidden sibling cases were evaluated only after the final epoch.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    parser.add_argument("--max-repairs", type=int, default=6)
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (HERE / "artifacts" / f"open-world-{run_id}")
    output.mkdir(parents=True, exist_ok=False)
    schedule = load_schedule()
    cases_by_id = case_map()
    client = CodexAppServerClient(model=args.model, cwd=HERE, timeout=600)
    try:
        models = client.list_models()
        if args.model not in models:
            raise SystemExit(f"model {args.model!r} unavailable; available: {models}")
        arms = {}
        for arm in ARM_NAMES:
            arms[arm] = run_arm(
                arm, output / arm.replace("_", "-"), schedule,
                cases_by_id, client, args.max_repairs,
            )
            exp.write_json(output / arm.replace("_", "-") / "summary.json", arms[arm])
        sketch_metrics = arms["sketch_ce"]["metrics"]
        genuine = sketch_metrics["scheduled_cases_that_failed_incumbent"]
        covered = sketch_metrics["scheduled_cases_already_covered"]
        report = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "open_world_three_arm_spike",
            "model": args.model,
            "provider": client.provider,
            "inference": {
                "effort": client.effort, "summary": client.summary,
                "personality": client.personality, "tools": False,
                "environment_access": False, "model_fallback": False,
            },
            "max_repairs_per_epoch": args.max_repairs,
            "schedule": schedule,
            "hidden_case_ids": sorted(SPIKE_HIDDEN_IDS),
            "validity": {
                "classification": (
                    "clean counterexample schedule" if covered == 0
                    else "mixed world-discovery spike, not a clean counterexample schedule"
                ),
                "scheduled_discoveries": genuine + covered,
                "genuine_counterexamples": genuine,
                "already_covered": covered,
                "all_discoveries_failed_incumbent": covered == 0,
            },
            "arms": arms,
        }
        exp.write_json(output / "report.json", report)
        (output / "REPORT.md").write_text(markdown_report(report), encoding="utf-8")
        print(output)
    finally:
        client.close()


if __name__ == "__main__":
    main()
