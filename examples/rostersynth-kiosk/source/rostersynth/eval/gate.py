from __future__ import annotations

from pathlib import Path

from rostersynth.eval.comparer import compare_scenario
from rostersynth.eval.scenarios import load_manifest, load_scenario, llm_fallback_scenario_ids
from rostersynth.resolver.deterministic import resolve_deterministic
from rostersynth.resolver.hybrid import resolve_hybrid
from rostersynth.resolver.llm import default_llm_backend, resolve_llm_only
from rostersynth.verifier import verify_rows


def run_gate(
    repo_root: Path,
    mode: str,
    llm_backend: str | None = None,
    *,
    exclude_llm_fallback: bool = False,
) -> tuple[bool, list[dict]]:
    results: list[dict] = []
    all_passed = True
    if mode in ("hybrid", "llm-only") and llm_backend is None:
        llm_backend = default_llm_backend()

    skipped = llm_fallback_scenario_ids(repo_root) if exclude_llm_fallback else frozenset()

    for scenario_id in load_manifest(repo_root):
        if scenario_id in skipped:
            results.append(
                {
                    "scenarioId": scenario_id,
                    "passed": True,
                    "excluded": True,
                    "excludeReason": "requiresLlmFallback",
                    "verifyPassed": None,
                    "comparePassed": None,
                    "verifyNotes": ["excluded from deterministic gate (Oracle A abstains)"],
                    "compareNotes": [],
                }
            )
            continue

        scenario = load_scenario(repo_root, scenario_id)
        if mode == "deterministic":
            actual = resolve_deterministic(scenario.payload)
        elif mode == "hybrid":
            actual = resolve_hybrid(
                scenario.payload,
                repo_root,
                scenario_id,
                llm_backend=llm_backend,
            )
        elif mode == "llm-only":
            actual = resolve_llm_only(
                scenario.payload, repo_root, scenario_id, backend=llm_backend
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        verify_ok, verify_notes = verify_rows(scenario.payload, actual)
        compare_ok, compare_notes = compare_scenario(scenario.expected, actual)
        passed = verify_ok and compare_ok
        all_passed = all_passed and passed
        results.append(
            {
                "scenarioId": scenario_id,
                "passed": passed,
                "excluded": False,
                "verifyPassed": verify_ok,
                "comparePassed": compare_ok,
                "verifyNotes": verify_notes,
                "compareNotes": compare_notes,
            }
        )
    return all_passed, results
