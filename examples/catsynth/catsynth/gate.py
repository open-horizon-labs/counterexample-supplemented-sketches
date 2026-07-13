"""The gate G: two layers over regression set R.

CatSynth uses every operator-approved CE as a regression, so R = A in this
small teaching app. The general method may curate R as a subset of archive A.

- Replay:  did the candidate repair the encoded *state* gap? (Owner ends up with
           a preference-satisfying suggestion, or a correct abstention.)
- Compare: did the candidate use the encoded *policy-bearing* fields from the
           approved expectation? (operation, breed, cited_rules)

Replay and compare fail differently on purpose. A preference-satisfying breed
that violates a hard rule (e.g. Persian for an allergic owner) passes replay and
is rejected by compare -- exactly the tempting-repair case.
"""

from __future__ import annotations

from typing import Optional

from . import db, resolver, oracle_a
from .models import Breed, OwnerProfile, Operation, Recommendation, SIZES, LEVELS
from .oracle_b import LLMClient


def hard_survivors(owner: OwnerProfile, breeds: list[Breed], rules: list[dict]) -> list[Breed]:
    hard = [r for r in rules if r["kind"] == "forbid" and oracle_a.trait_applies(r, owner)]
    return [b for b in breeds if not any(oracle_a.breed_targeted(r, b) for r in hard)]


def _preferences_met(owner: OwnerProfile, breed: Breed) -> tuple[bool, list[str]]:
    """State predicate for a RECOMMEND: does the breed clear the owner's stated
    preference bar? (Independent of policy -- that is compare's job.)"""
    misses = []
    if owner.wants_size and abs(SIZES[breed.size] - SIZES[owner.wants_size]) > 1:
        misses.append(f"size {breed.size} far from wanted {owner.wants_size}")
    if owner.wants_affection and LEVELS[breed.affection] < LEVELS["moderate"]:
        misses.append("affection below moderate")
    if owner.wants_fluffy and not breed.fluffy:
        misses.append("not fluffy")
    return (len(misses) == 0), misses


def replay(owner: OwnerProfile, candidate: Recommendation,
           breeds: list[Breed], rules: list[dict]) -> tuple[bool, str]:
    """Return (accepted, detail)."""
    if candidate.operation == Operation.RECOMMEND:
        breed = next((b for b in breeds if b.name == candidate.breed), None)
        if breed is None:
            return False, f"recommended breed {candidate.breed!r} not in catalog"
        met, misses = _preferences_met(owner, breed)
        if met:
            return True, f"{breed.name} closes the state gap (meets stated preferences)"
        return False, f"{breed.name} does not meet preferences: {', '.join(misses)}"

    if candidate.operation == Operation.ABSTAIN:
        survivors = hard_survivors(owner, breeds, rules)
        if not survivors:
            return True, "abstention is correct: no breed survives the hard rules"
        names = ", ".join(b.name for b in survivors)
        return False, f"abstained though breeds survive the hard rules: {names}"

    return False, f"operation {candidate.operation} has no encoded replay predicate"


def semantic_compare(expected: Recommendation, candidate: Recommendation) -> tuple[bool, dict]:
    """Compare the policy-bearing fields only."""
    e, c = expected.policy_fields(), candidate.policy_fields()
    fields = {}
    for key in ("operation", "breed", "cited_rules"):
        fields[key] = {"expected": e[key], "actual": c[key], "match": e[key] == c[key]}
    passed = all(f["match"] for f in fields.values())
    return passed, fields


def _interpret(replay_ok: bool, compare_ok: bool) -> str:
    if not replay_ok:
        return "Candidate fails encoded state repair (replay reject)."
    if not compare_ok:
        return "Repairs state but violates a policy field (compare reject)."
    return "Satisfies the selected regression under current repository semantics."


def run_gate(conn, mode: str = "policy", llm_client: Optional[LLMClient] = None) -> dict:
    breeds = db.get_breeds(conn)
    rules = db.get_rules(conn)
    corpus = db.get_corpus(conn)

    cases = []
    for case in corpus:
        owner = db.get_scenario(conn, case["scenario_id"])
        candidate = resolver.resolve(conn, owner, mode=mode, llm_client=llm_client)
        replay_ok, replay_detail = replay(owner, candidate, breeds, rules)
        compare_ok, compare_fields = semantic_compare(case["expected"], candidate)
        cases.append({
            "corpus_id": case["id"],
            "scenario_id": case["scenario_id"],
            "scenario_label": owner.label,
            "sketch_clause": case["sketch_clause"],
            "expected": case["expected"].to_dict(),
            "tempting": case["tempting"].to_dict() if case["tempting"] else None,
            "candidate": candidate.to_dict(),
            "replay": {"passed": replay_ok, "detail": replay_detail},
            "compare": {"passed": compare_ok, "fields": compare_fields},
            "passed": replay_ok and compare_ok,
            "interpretation": _interpret(replay_ok, compare_ok),
        })

    # An empty corpus carries no evidence. Report it as not passing instead of
    # relying on Python's vacuous all([]) == True behavior.
    passed = bool(cases) and all(c["passed"] for c in cases)
    summary = {
        "mode": mode,
        "passed": passed,
        "total": len(cases),
        "passed_count": sum(1 for c in cases if c["passed"]),
        "cases": cases,
    }
    db.log_gate_run(conn, mode, passed, {
        "passed": passed, "total": summary["total"],
        "passed_count": summary["passed_count"],
        "failed_cases": [c["scenario_id"] for c in cases if not c["passed"]],
    })
    return summary
