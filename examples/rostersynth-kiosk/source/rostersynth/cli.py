from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rostersynth.eval.gate import run_gate
from rostersynth.eval.scenarios import load_scenario
from rostersynth.oracle.prompt import build_user_prompt, load_sketch
from rostersynth.resolver.deterministic import payload_to_prompt_dict, resolve_deterministic
from rostersynth.resolver.hybrid import resolve_hybrid
from rostersynth.resolver.llm import default_llm_backend, resolve_llm_only


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="RosterSynth CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    gate = sub.add_parser("gate", help="Run regression gate")
    gate.add_argument(
        "--mode",
        choices=["deterministic", "hybrid", "llm-only"],
        default="hybrid",
        help="deterministic=Oracle A; hybrid=A+LLM fallback; llm-only=Oracle B",
    )
    gate.add_argument(
        "--llm",
        choices=["bedrock", "cassette"],
        default=None,
        help="Oracle B backend for hybrid/llm-only (default: ROSTERSYNTH_LLM or bedrock)",
    )
    gate.add_argument("--json", action="store_true", help="Emit JSON report")
    gate.add_argument(
        "--exclude-llm-fallback",
        action="store_true",
        help="Skip scenarios tagged requiresLlmFallback (deterministic tractable subset)",
    )
    gate.add_argument(
        "--include-llm-fallback",
        action="store_true",
        help="Run full corpus including requiresLlmFallback scenarios",
    )

    oracle = sub.add_parser("oracle", help="Run Oracle B on one scenario")
    oracle.add_argument("scenario_id", help="Scenario id")
    oracle.add_argument(
        "--llm",
        choices=["bedrock", "cassette"],
        default=None,
        help="Oracle B backend",
    )
    oracle.add_argument("--record-cassette", action="store_true", help="Save Bedrock output")

    prompt = sub.add_parser(
        "prompt",
        help="Print Oracle B system (sketch) and user prompts for a scenario",
    )
    prompt.add_argument("scenario_id", help="Scenario id")
    prompt.add_argument(
        "--part",
        choices=["system", "user", "all"],
        default="all",
        help="Which prompt block to print",
    )

    args = parser.parse_args(argv)
    root = _repo_root()

    if args.command == "gate":
        if args.exclude_llm_fallback and args.include_llm_fallback:
            print("error: use only one of --exclude-llm-fallback or --include-llm-fallback", file=sys.stderr)
            return 2
        llm_backend = args.llm
        if args.mode in ("hybrid", "llm-only") and llm_backend is None:
            llm_backend = default_llm_backend()
        exclude_llm = args.exclude_llm_fallback or (
            args.mode == "deterministic" and not args.include_llm_fallback
        )
        passed, results = run_gate(
            root,
            args.mode,
            llm_backend=llm_backend,
            exclude_llm_fallback=exclude_llm,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "passed": passed,
                        "mode": args.mode,
                        "llmBackend": llm_backend,
                        "excludeLlmFallback": exclude_llm,
                        "scenarios": results,
                    },
                    indent=2,
                )
            )
        else:
            backend_note = (
                f", llm={llm_backend}" if args.mode in ("hybrid", "llm-only") else ""
            )
            exclude_note = ", excluding requiresLlmFallback" if exclude_llm else ""
            for r in results:
                if r.get("excluded"):
                    print(f"[SKIP] {r['scenarioId']} (requiresLlmFallback)")
                    continue
                status = "PASS" if r["passed"] else "FAIL"
                print(f"[{status}] {r['scenarioId']}")
                if not r["passed"]:
                    for note in r["compareNotes"] + r["verifyNotes"]:
                        print(f"  - {note}")
            n_run = sum(1 for r in results if not r.get("excluded"))
            n_pass = sum(1 for r in results if r["passed"] and not r.get("excluded"))
            n_skip = sum(1 for r in results if r.get("excluded"))
            skip_note = f", {n_skip} excluded" if n_skip else ""
            print(
                f"\nGate ({args.mode}{backend_note}{exclude_note}): "
                f"{'PASSED' if passed else 'FAILED'} ({n_pass}/{n_run}{skip_note})"
            )
        return 0 if passed else 1

    if args.command == "oracle":
        if args.record_cassette:
            os.environ["ROSTERSYNTH_RECORD_CASSETTE"] = "1"
        scenario = load_scenario(root, args.scenario_id)
        llm_backend = args.llm or default_llm_backend()
        rows = resolve_llm_only(
            scenario.payload, root, args.scenario_id, backend=llm_backend
        )
        print(json.dumps({"suggestions": [r.to_dict() for r in rows]}, indent=2))
        return 0

    if args.command == "prompt":
        scenario = load_scenario(root, args.scenario_id)
        system = load_sketch(root)
        user = build_user_prompt(payload_to_prompt_dict(scenario.payload))
        if args.part in ("system", "all"):
            print("=== SYSTEM (docs/sketch.md) ===")
            print(system.rstrip())
            if args.part == "all":
                print()
        if args.part in ("user", "all"):
            print("=== USER (oracle/prompt.py build_user_prompt) ===")
            print(user.rstrip())
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
