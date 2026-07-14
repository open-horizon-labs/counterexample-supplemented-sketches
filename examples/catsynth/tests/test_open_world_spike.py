import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiment import open_world_spike as spike
from experiment import run_experiment as experiment


class OpenWorldSpikeTests(unittest.TestCase):
    def setUp(self):
        self.schedule = spike.load_schedule()
        self.cases = spike.case_map()

    def test_schedule_encodes_reviewed_double_and_single_loop_decisions(self):
        self.assertEqual([event["epoch"] for event in self.schedule], list(range(1, 8)))
        self.assertEqual(
            [event["loop_type"] for event in self.schedule].count("double"), 6
        )
        single = next(event for event in self.schedule if event["loop_type"] == "single")
        self.assertEqual(single["feedback_destination"], "implementation")
        self.assertIsNone(single["approved_clause"])
        for event in self.schedule:
            self.assertIn(event["case_id"], self.cases)

    def test_epoch_zero_policy_is_byte_identical_initial_sketch(self):
        self.assertEqual(
            spike.approved_sketch([]),
            experiment.INITIAL_SKETCH_PATH.read_text(encoding="utf-8"),
        )

    def test_single_loop_event_does_not_change_approved_sketch(self):
        before = spike.approved_sketch(self.schedule[:3])
        after = spike.approved_sketch(self.schedule[:4])
        self.assertEqual(before, after)

    def test_counterexample_classification_ignores_unrelated_gate_failure(self):
        gate = {
            "cases": [
                {"id": "initial-anchor", "passed": False},
                {"id": "new-case", "passed": True},
            ]
        }
        self.assertFalse(spike.introduced_case_failed(gate, "new-case"))

    def test_arm_prompts_have_only_their_declared_policy_state(self):
        event = self.schedule[1]
        packet = spike.discovery_packet(event, self.cases[event["case_id"]])
        history = [
            spike.discovery_packet(item, self.cases[item["case_id"]])
            for item in self.schedule[:2]
        ]
        reviewed = spike.approved_sketch(self.schedule[:2])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            experiment.baseline_workspace(workspace)
            payloads = {}
            for arm in spike.ARM_NAMES:
                messages = spike.world_messages(
                    arm, workspace, 2, reviewed, history, packet, None
                )
                payloads[arm] = json.loads(messages[1]["content"])

        replay = payloads["replay_all"]["policy_context"]
        self.assertEqual(replay["accumulated_reviewed_discoveries"], history)
        self.assertNotIn("current_reviewer_approved_sketch", replay)

        rebuilt = payloads["reviewed_sketch"]["policy_context"]
        self.assertEqual(rebuilt, {"current_reviewer_approved_sketch": reviewed})

        iterative = payloads["sketch_ce"]["policy_context"]
        self.assertEqual(iterative["current_reviewer_approved_sketch"], reviewed)
        self.assertEqual(iterative["active_reviewed_discovery"], packet)
        self.assertNotIn("accumulated_reviewed_discoveries", iterative)

        future = self.schedule[2]
        for payload in payloads.values():
            encoded = json.dumps(payload)
            self.assertNotIn(future["case_id"], encoded)
            self.assertNotIn(future["decision"], encoded)


if __name__ == "__main__":
    unittest.main()
