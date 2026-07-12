"""Gate tests: the deterministic, model-free part of the loop.

These assert the paper's central lesson in code: policy mode is E-correct, and
the naive (tempting) resolver is caught by *semantic compare* on the allergy
counterexample even though *replay* accepts it.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from catsynth import db, resolver, seed
from catsynth.gate import run_gate
from catsynth.models import Operation
from catsynth.oracle_b import MockLLM, derive_soft_constraints


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(str(tmp_path / "test.db"))
    seed.seed_all(c, fetch_wiki_facts=False)  # offline: no network in tests
    yield c
    c.close()


def test_policy_gate_passes(conn):
    summary = run_gate(conn, mode="policy")
    assert summary["passed"], summary
    assert summary["passed_count"] == summary["total"] == 3


def test_naive_gate_fails_on_allergy_case(conn):
    summary = run_gate(conn, mode="naive")
    assert not summary["passed"]
    case = next(c for c in summary["cases"] if c["scenario_id"] == "allergy_lapcat")
    # The tempting repair passes replay (state gap closed) but fails compare.
    assert case["replay"]["passed"] is True
    assert case["compare"]["passed"] is False
    assert case["candidate"]["breed"] == "Persian"
    assert case["compare"]["fields"]["breed"]["expected"] == "Siberian"


def test_policy_recommends_hypoallergenic_for_allergic_owner(conn):
    owner = db.get_scenario(conn, "allergy_lapcat")
    rec = resolver.resolve(conn, owner, mode="policy")
    assert rec.operation == Operation.RECOMMEND
    assert rec.breed == "Siberian"
    assert "allergy_requires_hypoallergenic" in rec.cited_rules


def test_over_constrained_abstains(conn):
    owner = db.get_scenario(conn, "over_constrained")
    rec = resolver.resolve(conn, owner, mode="policy")
    assert rec.operation == Operation.ABSTAIN
    assert rec.breed is None
    assert "children_require_good_with_children" in rec.cited_rules


def test_oracle_b_derives_soft_constraint_from_note(conn):
    owner = db.get_scenario(conn, "narrative_travel")
    soft, trace = derive_soft_constraints(owner, MockLLM())
    assert trace["used"] is True
    assert "avoid_needy" in trace["tags"]
    assert any(r["id"] == "nb_avoid_needy" for r in soft)


def test_oracle_b_never_relaxes_hard_rule(conn):
    """Even with a narrative note, hard rules still bind: an allergic owner must
    never be routed to a non-hypoallergenic breed by Oracle B."""
    owner = db.get_scenario(conn, "allergy_lapcat")
    owner.narrative_note = "I travel constantly and want a calm quiet cat."
    rec = resolver.resolve(conn, owner, mode="policy")
    breed = db.get_breed(conn, rec.breed)
    assert breed.hypoallergenic is True
