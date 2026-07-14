import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment import adaptive_open_world_experiment as adaptive
from experiment import run_experiment as experiment


class AdaptiveOpenWorldTests(unittest.TestCase):
    def test_preregistered_pool_hash_and_order_are_enforced(self):
        manifest, candidates = adaptive.load_preregistered_candidates()
        self.assertEqual(len(candidates), 14)
        self.assertEqual(
            [case["id"] for case in candidates], manifest["candidate_ids"]
        )
        self.assertEqual(candidates[0]["id"], "ce-001-allergy-override")
        self.assertEqual(candidates[-1]["id"], "ce-014-post-soft-tiebreak")

    def test_replay_prompt_gets_only_cumulative_promoted_cases(self):
        _, candidates = adaptive.load_preregistered_candidates()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            experiment.baseline_workspace(workspace)
            messages = experiment.developer_messages(
                workspace,
                candidates[:2],
                None,
                "replay_all",
                "one_shot",
                complete_corpus=experiment.complete_case_packets(candidates[:2]),
            )
        payload = json.loads(messages[1]["content"])
        self.assertEqual(
            [case["id"] for case in payload["complete_corpus"]],
            [case["id"] for case in candidates[:2]],
        )
        encoded = json.dumps(payload)
        self.assertNotIn(candidates[2]["id"], encoded)
        self.assertNotIn(candidates[2]["policy"], encoded)

    def test_reviewed_sketch_prompt_gets_no_counterexample_corpus(self):
        _, candidates = adaptive.load_preregistered_candidates()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            experiment.baseline_workspace(workspace)
            (workspace / "SKETCH.md").write_text(
                "# Evolved generic policy\nApply applicable hard rules.\n"
            )
            messages = experiment.developer_messages(
                workspace, candidates[:5], None, "reviewed_sketch", "initial"
            )
        payload = json.loads(messages[1]["content"])
        self.assertNotIn("complete_corpus", payload)
        self.assertIsNone(payload["active_failing_counterexample"])
        encoded = json.dumps(payload)
        for case in candidates:
            self.assertNotIn(case["id"], encoded)

    def test_diff_churn_ignores_unified_diff_headers(self):
        diffs = {"x": "--- before\n+++ after\n-old\n+new\n unchanged\n"}
        self.assertEqual(adaptive.diff_churn(diffs), 2)

    def test_sketch_ce_developer_bucket_uses_iterative_ledger_category(self):
        arm = {
            "tokens": {
                "by_category": {
                    "developer_iterative": {"calls": 9, "total_tokens": 123}
                }
            }
        }
        self.assertEqual(
            adaptive.developer_bucket(arm, "sketch_ce"),
            {"calls": 9, "total_tokens": 123},
        )

    def test_repair_failures_share_catalog_without_dropping_failures(self):
        _, candidates = adaptive.load_preregistered_candidates()
        gate = {
            "cases": [
                {
                    "id": case["id"],
                    "scenario_id": case["scenario_id"],
                    "expected": case["expected"],
                    "actual": {
                        **case["expected"],
                        "operation": "escalate",
                    },
                    "checked_fields": ["operation", "breed", "cited_rules", "oracle_tags"],
                    "fields": {
                        key: {
                            "expected": case["expected"][key],
                            "actual": "escalate" if key == "operation" else case["expected"][key],
                            "match": key != "operation",
                            "checked": True,
                        }
                        for key in ("operation", "breed", "cited_rules", "oracle_tags")
                    },
                    "passed": False,
                }
                for case in candidates[:2]
            ]
        }
        compact = adaptive.compact_repair_failures(candidates[:2], gate, {})
        self.assertEqual(len(compact["failures"]), 2)
        self.assertEqual(len(compact["shared_breed_catalog"]), 12)
        self.assertTrue(all("candidate_breeds" not in item for item in compact["failures"]))
        self.assertTrue(all("candidate_breed_names" in item for item in compact["failures"]))
        raw = experiment.one_shot_failure_packets(candidates[:2], gate, {})
        self.assertLess(len(json.dumps(compact)), len(json.dumps(raw)))



if __name__ == "__main__":
    unittest.main()
