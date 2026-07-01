from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
SOURCE = EXAMPLE / "source"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from rostersynth.eval.comparer import compare_scenario
from rostersynth.eval.gate import run_gate
from rostersynth.eval.scenarios import load_manifest, load_scenario, llm_fallback_scenario_ids
from rostersynth.models import SuggestionRow
from rostersynth.oracle.prompt import build_user_prompt
from rostersynth.playbook import build_rows
from rostersynth.resolver.deterministic import payload_to_prompt_dict
from rostersynth.resolver.hybrid import resolve_hybrid
from rostersynth.verifier import verify_rows


KIOSK = "roster.kiosk_double_booking.v1"


class ExtractedRosterSynthTests(unittest.TestCase):
    def test_kiosk_oracle_a_cancels_higher_duplicate(self) -> None:
        scenario = load_scenario(SOURCE, KIOSK)
        row = build_rows(scenario.payload)[0]
        self.assertEqual("modify", row.op)
        self.assertIsNotNone(row.modify)
        self.assertEqual(1802, row.modify.booking_id)
        self.assertEqual({"status": 4}, row.modify.fields)

    def test_wrong_append_story_is_caught_by_compare_not_replay(self) -> None:
        scenario = load_scenario(SOURCE, KIOSK)
        wrong_append = SuggestionRow.from_dict(
            {
                "employeeId": "E-1800",
                "issueType": "coverage-hour-gap",
                "op": "append",
                "generatedBy": "tempting-wrong-patch",
                "suggestion": "Post an adjustment that closes the hours math.",
                "adjustment": {"shiftKind": 51, "hours": -40.0, "workDate": "2024-05-14"},
            }
        )
        replay_ok, replay_notes = verify_rows(scenario.payload, [wrong_append])
        compare_ok, compare_notes = compare_scenario(scenario.expected, [wrong_append])
        self.assertTrue(replay_ok, replay_notes)
        self.assertFalse(compare_ok)
        self.assertTrue(any("expected op modify, got append" in note for note in compare_notes), compare_notes)

    def test_wrong_cassette_is_caught_by_compare_not_replay(self) -> None:
        scenario = load_scenario(SOURCE, KIOSK)
        wrong = json.loads((SOURCE / "cassettes" / f"{KIOSK}.wrong.json").read_text(encoding="utf-8"))
        rows = [SuggestionRow.from_dict(item) for item in wrong["suggestions"]]
        replay_ok, replay_notes = verify_rows(scenario.payload, rows)
        compare_ok, compare_notes = compare_scenario(scenario.expected, rows)
        self.assertTrue(replay_ok, replay_notes)
        self.assertFalse(compare_ok)
        self.assertTrue(any("expected bookingId 1802, got 1801" in note for note in compare_notes), compare_notes)

    def test_hybrid_uses_deterministic_for_kiosk(self) -> None:
        scenario = load_scenario(SOURCE, KIOSK)
        rows = resolve_hybrid(scenario.payload, SOURCE, scenario.scenario_id, llm_backend="cassette")
        self.assertEqual("deterministic", rows[0].generated_by)
        self.assertIsNotNone(rows[0].modify)
        self.assertEqual(1802, rows[0].modify.booking_id)

    def test_prompt_carries_decision_order_and_payload(self) -> None:
        scenario = load_scenario(SOURCE, KIOSK)
        prompt = build_user_prompt(payload_to_prompt_dict(scenario.payload))
        self.assertIn("DECISION ORDER", prompt)
        self.assertIn("Op 2", prompt)
        self.assertIn("HIGHER bookingId", prompt)
        self.assertIn("E-1800", prompt)

    def test_full_corpus_gates_match_session_evidence(self) -> None:
        manifest_count = len(load_manifest(SOURCE))
        llm_fallbacks = llm_fallback_scenario_ids(SOURCE)

        deterministic_passed, deterministic_results = run_gate(SOURCE, "deterministic", exclude_llm_fallback=True)
        self.assertTrue(deterministic_passed, deterministic_results)
        self.assertEqual(manifest_count - len(llm_fallbacks), len([r for r in deterministic_results if not r.get("excluded")]))

        hybrid_passed, hybrid_results = run_gate(SOURCE, "hybrid", llm_backend="cassette")
        self.assertTrue(hybrid_passed, hybrid_results)
        self.assertEqual(manifest_count, len(hybrid_results))

        llm_passed, llm_results = run_gate(SOURCE, "llm-only", llm_backend="cassette")
        self.assertTrue(llm_passed, llm_results)
        self.assertEqual(manifest_count, len(llm_results))


if __name__ == "__main__":
    unittest.main()
