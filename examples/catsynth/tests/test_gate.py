"""Gate tests: the deterministic, model-free part of the loop.

These assert the paper's central lesson in code: policy mode is E-correct, and
the naive (tempting) resolver is caught by *semantic compare* on the allergy
counterexample even though *replay* accepts it.

Stdlib ``unittest`` (no third-party test runner), to match the repo's other
worked example. Run with ``python -m unittest discover -s tests``.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catsynth import db, resolver, seed
from catsynth.gate import run_gate
from catsynth.models import Operation
from catsynth.oracle_b import MockLLM, derive_soft_constraints


class GateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(os.path.join(self._tmp.name, "test.db"))
        seed.seed_all(self.conn, fetch_wiki_facts=False)  # offline: no network in tests

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_policy_gate_passes(self):
        summary = run_gate(self.conn, mode="policy")
        self.assertTrue(summary["passed"], summary)
        self.assertEqual(summary["passed_count"], summary["total"])
        self.assertEqual(summary["total"], 3)

    def test_naive_gate_fails_on_allergy_case(self):
        summary = run_gate(self.conn, mode="naive")
        self.assertFalse(summary["passed"])
        case = next(c for c in summary["cases"] if c["scenario_id"] == "allergy_lapcat")
        # The tempting repair passes replay (state gap closed) but fails compare.
        self.assertTrue(case["replay"]["passed"])
        self.assertFalse(case["compare"]["passed"])
        self.assertEqual(case["candidate"]["breed"], "Persian")
        self.assertEqual(case["compare"]["fields"]["breed"]["expected"], "Siberian")

    def test_policy_recommends_hypoallergenic_for_allergic_owner(self):
        owner = db.get_scenario(self.conn, "allergy_lapcat")
        rec = resolver.resolve(self.conn, owner, mode="policy")
        self.assertEqual(rec.operation, Operation.RECOMMEND)
        self.assertEqual(rec.breed, "Siberian")
        self.assertIn("allergy_requires_hypoallergenic", rec.cited_rules)

    def test_over_constrained_abstains(self):
        owner = db.get_scenario(self.conn, "over_constrained")
        rec = resolver.resolve(self.conn, owner, mode="policy")
        self.assertEqual(rec.operation, Operation.ABSTAIN)
        self.assertIsNone(rec.breed)
        self.assertIn("children_require_good_with_children", rec.cited_rules)

    def test_oracle_b_derives_soft_constraint_from_note(self):
        owner = db.get_scenario(self.conn, "narrative_travel")
        soft, trace = derive_soft_constraints(owner, MockLLM())
        self.assertTrue(trace["used"])
        self.assertIn("avoid_needy", trace["tags"])
        self.assertTrue(any(r["id"] == "nb_avoid_needy" for r in soft))

    def test_oracle_b_never_relaxes_hard_rule(self):
        """Even with a narrative note, hard rules still bind: an allergic owner
        must never be routed to a non-hypoallergenic breed by Oracle B."""
        owner = db.get_scenario(self.conn, "allergy_lapcat")
        owner.narrative_note = "I travel constantly and want a calm quiet cat."
        rec = resolver.resolve(self.conn, owner, mode="policy")
        breed = db.get_breed(self.conn, rec.breed)
        self.assertTrue(breed.hypoallergenic)


if __name__ == "__main__":
    unittest.main()
