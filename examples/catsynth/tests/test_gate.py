"""Gate tests: the deterministic, model-free part of the loop.

These assert the paper's central lesson in code: policy mode is E-correct, and
the naive (tempting) resolver is caught by *approved-output compare* on the allergy
counterexample even though *replay* accepts it.

Stdlib ``unittest`` (no third-party test runner), to match the repo's other
worked example. Run with ``python -m unittest discover -s tests``.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catsynth import db, oracle_a, resolver, seed
from catsynth.gate import run_gate
from catsynth.models import Operation, OwnerProfile
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

    def test_empty_corpus_does_not_pass(self):
        self.conn.execute("DELETE FROM golden_corpus")
        self.conn.commit()
        summary = run_gate(self.conn, mode="policy")
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["total"], 0)

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

    def test_narrative_tag_changes_the_selected_breed(self):
        owner = db.get_scenario(self.conn, "narrative_travel")
        without_tag = oracle_a.resolve(owner, seed.BREEDS, seed.RULES)
        soft, _ = derive_soft_constraints(owner, MockLLM())
        with_tag = oracle_a.resolve(owner, seed.BREEDS, seed.RULES, extra_soft=soft)
        self.assertEqual(without_tag.breed, "Balinese")
        self.assertEqual(with_tag.breed, "Persian")

    def test_oracle_b_never_relaxes_hard_rule(self):
        """Even with a narrative note, hard rules still bind: an allergic owner
        must never be routed to a non-hypoallergenic breed by Oracle B."""
        owner = db.get_scenario(self.conn, "allergy_lapcat")
        owner.narrative_note = "I travel constantly and want a calm quiet cat."
        rec = resolver.resolve(self.conn, owner, mode="policy")
        breed = db.get_breed(self.conn, rec.breed)
        self.assertTrue(breed.hypoallergenic)

    def test_soft_rule_never_filters_the_only_candidate(self):
        owner = OwnerProfile(
            scenario_id="soft-only", label="soft-only", noise_tolerance="low",
        )
        siamese = [breed for breed in seed.BREEDS if breed.name == "Siamese"]
        rule = [rule for rule in seed.RULES
                if rule["id"] == "low_noise_discourage_vocal"]
        rec = oracle_a.resolve(owner, siamese, rule)
        self.assertEqual(rec.operation, Operation.RECOMMEND)
        self.assertEqual(rec.breed, "Siamese")
        self.assertEqual(rec.cited_rules, [])

    def test_duplicate_soft_predicates_apply_once(self):
        owner = OwnerProfile(
            scenario_id="dedup", label="dedup", activity_level="low",
            wants_size="medium",
        )
        breeds = [breed for breed in seed.BREEDS
                  if breed.name in {"Bengal", "British Shorthair"}]
        structured = [rule for rule in seed.RULES
                      if rule["id"] == "low_activity_discourage_high_energy"]
        extra = [dict(structured[0], id="narrative_duplicate")]
        rec = oracle_a.resolve(owner, breeds, structured, extra_soft=extra)
        self.assertEqual(rec.breed, "Bengal")

    def test_empty_catalog_escalates_instead_of_abstaining(self):
        owner = OwnerProfile(scenario_id="empty", label="empty")
        rec = oracle_a.resolve(owner, [], seed.RULES)
        self.assertEqual(rec.operation, Operation.ESCALATE)
        self.assertIsNone(rec.breed)

    def test_unknown_allergy_status_escalates(self):
        owner = OwnerProfile(
            scenario_id="missing", label="missing", allergies="unknown",
        )
        rec = oracle_a.resolve(owner, seed.BREEDS, seed.RULES)
        self.assertEqual(rec.operation, Operation.ESCALATE)
        self.assertEqual(rec.cited_rules, [])

    def test_applicable_invalid_rule_escalates_with_provenance(self):
        owner = OwnerProfile(
            scenario_id="invalid", label="invalid", experience="reviewer_required",
        )
        invalid = [rule for rule in seed.RULES
                   if rule["id"] == "invalid_reviewer_policy"]
        rec = oracle_a.resolve(owner, seed.BREEDS, invalid)
        self.assertEqual(rec.operation, Operation.ESCALATE)
        self.assertEqual(rec.cited_rules, ["invalid_reviewer_policy"])

    def test_recommendation_cites_only_hard_rules_that_removed_candidates(self):
        owner = OwnerProfile(
            scenario_id="citation", label="citation", allergies="mild",
            young_children=True, wants_size="large", wants_affection=True,
            wants_fluffy=True,
        )
        breeds = [breed for breed in seed.BREEDS
                  if breed.name in {"Persian", "Siberian", "Balinese", "Devon Rex"}]
        rules = [rule for rule in seed.RULES if rule["id"] in {
            "allergy_requires_hypoallergenic", "children_require_good_with_children",
        }]
        rec = oracle_a.resolve(owner, breeds, rules)
        self.assertEqual(rec.breed, "Siberian")
        self.assertEqual(rec.cited_rules, ["allergy_requires_hypoallergenic"])

    def test_normalization_is_case_and_whitespace_insensitive(self):
        owner = OwnerProfile(
            scenario_id="normalized", label="normalized", allergies=" MILD ",
            wants_size=" LARGE ", wants_affection=True, wants_fluffy=True,
        )
        rules = [rule for rule in seed.RULES
                 if rule["id"] == "allergy_requires_hypoallergenic"]
        rec = oracle_a.resolve(owner, seed.BREEDS, rules)
        self.assertEqual(rec.breed, "Siberian")
        self.assertEqual(rec.cited_rules, ["allergy_requires_hypoallergenic"])

    def test_invalid_nonapplicable_rule_is_ignored(self):
        owner = OwnerProfile(
            scenario_id="nonapplicable", label="nonapplicable",
            experience="experienced", wants_affection=True, wants_fluffy=True,
        )
        invalid = [rule for rule in seed.RULES
                   if rule["id"] == "invalid_reviewer_policy"]
        rec = oracle_a.resolve(owner, seed.BREEDS, invalid)
        self.assertEqual(rec.operation, Operation.RECOMMEND)
        self.assertEqual(rec.breed, "Persian")

    def test_hard_rule_provenance_is_order_invariant(self):
        owner = OwnerProfile(
            scenario_id="order", label="order", allergies="mild",
            young_children=True, wants_size="large", wants_affection=True,
            wants_fluffy=True,
        )
        breeds = [breed for breed in seed.BREEDS
                  if breed.name in {"Persian", "Siberian", "Balinese", "Devon Rex"}]
        rules = [rule for rule in seed.RULES if rule["id"] in {
            "allergy_requires_hypoallergenic", "children_require_good_with_children",
        }]
        forward = oracle_a.resolve(owner, breeds, rules)
        reverse = oracle_a.resolve(owner, breeds, list(reversed(rules)))
        self.assertEqual(forward.policy_fields(), reverse.policy_fields())
        self.assertEqual(forward.cited_rules, ["allergy_requires_hypoallergenic"])

if __name__ == "__main__":
    unittest.main()
