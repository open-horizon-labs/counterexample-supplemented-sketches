import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment.publish_experiment import compact_case, compact_failure, compact_gate


class PublishExperimentTests(unittest.TestCase):
    def test_compact_gate_keeps_outcomes_but_drops_oracle_transport(self):
        gate = {
            "passed": False,
            "passed_count": 0,
            "total": 1,
            "cases": [{
                "id": "ce-x",
                "scenario_id": "scenario-x",
                "passed": False,
                "expected": {"operation": "abstain"},
                "actual": {"operation": "recommend"},
                "fields": {"operation": {
                    "expected": "abstain", "actual": "recommend",
                    "checked": True, "match": False,
                }},
                "oracle_trace": {"response": "large transport"},
            }],
        }
        compact = compact_gate(gate)
        self.assertEqual(compact["cases"][0]["mismatches"]["operation"]["actual"], "recommend")
        self.assertNotIn("oracle_trace", compact["cases"][0])

    def test_compact_failure_drops_shared_catalog_not_failure_meaning(self):
        value = {
            "shared_breed_catalog": [{"name": "large repeated fixture"}],
            "failures": [{
                "id": "ce-x", "reviewer_policy": "policy", "expected": {"x": 1},
                "actual": {"x": 0}, "mismatches": {"x": {"match": False}},
            }],
        }
        compact = compact_failure(value)
        self.assertNotIn("shared_breed_catalog", compact)
        self.assertEqual(compact["failures"][0]["reviewer_policy"], "policy")

    def test_compact_case_keeps_hidden_expected_and_actual(self):
        compact = compact_case({
            "id": "hidden-x", "passed": False,
            "expected": {"breed": "A"}, "actual": {"breed": "B"},
            "oracle_trace": {"request": "transport"},
        })
        self.assertEqual(compact["expected"]["breed"], "A")
        self.assertEqual(compact["actual"]["breed"], "B")
        self.assertNotIn("oracle_trace", compact)


if __name__ == "__main__":
    unittest.main()
