"""Oracle A: deterministic policy code.

All hard-rule enforcement lives here. It reads the rule tables generically
(there is no second hard-coded rule engine), filters out breeds that violate
hard `forbid` rules, ranks survivors by preference match minus soft-rule
penalties, and abstains when nothing survives.
"""

from __future__ import annotations

from typing import Optional

from .models import Breed, OwnerProfile, Operation, Recommendation, LEVELS, SIZES

# attribute name -> ordinal scale (None means it is a boolean attribute)
_SCALES = {
    "size": SIZES,
    "energy": LEVELS, "shedding": LEVELS, "grooming": LEVELS,
    "sociability": LEVELS, "vocal": LEVELS, "affection": LEVELS,
    "hypoallergenic": None, "good_with_children": None, "fluffy": None,
}


def trait_applies(rule: dict, owner: OwnerProfile) -> bool:
    """Does the owner's trait satisfy the rule's trigger condition?"""
    value = getattr(owner, rule["trait"], None)
    op = rule["trait_op"]
    target = rule["trait_value"]
    if op == "eq":
        return str(value) == target
    if op == "in":
        return str(value) in [t.strip() for t in target.split(",")]
    if op == "is_true":
        return value is True
    if op == "is_false":
        return value is False
    raise ValueError(f"unknown trait_op {op!r}")


def breed_targeted(rule: dict, breed: Breed) -> bool:
    """Does this breed match the rule's cat-attribute condition (i.e. is it the
    thing the rule forbids/discourages)?"""
    attr = rule["cat_attribute"]
    op = rule["cat_op"]
    bval = getattr(breed, attr)
    scale = _SCALES.get(attr)
    if op == "is_true":
        return bool(bval) is True
    if op == "is_false":
        return bool(bval) is False
    if scale is None:
        raise ValueError(f"cat_op {op!r} needs an ordinal attribute, got {attr!r}")
    cval = scale[rule["cat_value"]]
    b = scale[bval]
    if op == "gte":
        return b >= cval
    if op == "lte":
        return b <= cval
    if op == "eq":
        return b == cval
    if op == "neq":
        return b != cval
    raise ValueError(f"unknown cat_op {op!r}")


def preference_score(owner: OwnerProfile, breed: Breed) -> int:
    """How well the breed matches the owner's stated soft preferences."""
    score = 0
    if owner.wants_size:
        diff = abs(SIZES[breed.size] - SIZES[owner.wants_size])
        score += max(0, 2 - diff)
    if owner.wants_affection:
        score += LEVELS[breed.affection]
        score += (2 - LEVELS[breed.energy])  # a lap cat should be calmer
    if owner.wants_fluffy:
        score += 2 if breed.fluffy else 0
    return score


def resolve(owner: OwnerProfile, breeds: list[Breed], rules: list[dict],
            extra_soft: Optional[list[dict]] = None, mode: str = "policy",
            oracle_label: str = "A") -> Recommendation:
    """Produce a recommendation.

    mode="policy": enforce hard rules, rank, abstain when empty (the sketch).
    mode="naive":  ignore all rules and rank purely by preference match.
                   This is the *tempting repair* surface used to demonstrate
                   the gate catching a forbidden repair.
    """
    extra_soft = extra_soft or []

    if mode == "naive":
        ranked = sorted(breeds, key=lambda b: (-preference_score(owner, b), b.name))
        best = ranked[0]
        return Recommendation(
            operation=Operation.RECOMMEND, breed=best.name, cited_rules=[],
            oracle="naive",
            rationale="Best preference match overall (ignores owner-trait rules).",
            trace={"mode": "naive",
                   "ranking": [{"breed": b.name, "score": preference_score(owner, b)}
                               for b in ranked]},
        )

    hard = [r for r in rules if r["kind"] == "forbid" and trait_applies(r, owner)]
    soft = [r for r in rules if r["kind"] == "discourage" and trait_applies(r, owner)]
    soft = soft + extra_soft
    cited_hard = sorted(r["id"] for r in hard)

    survivors = [b for b in breeds if not any(breed_targeted(r, b) for r in hard)]

    if not survivors:
        return Recommendation(
            operation=Operation.ABSTAIN, breed=None, cited_rules=cited_hard,
            oracle=oracle_label,
            rationale="No breed satisfies all hard rules; declining rather than forcing a fit.",
            trace={"mode": "policy", "hard_rules": cited_hard,
                   "eliminated_all": True},
        )

    def score_breed(b: Breed):
        pref = preference_score(owner, b)
        pen = sum(1 for r in soft if breed_targeted(r, b))
        return pref, pen

    # Score each survivor once, then reuse for ranking, selection, and trace.
    scores = {b.name: score_breed(b) for b in survivors}

    ranked = sorted(survivors, key=lambda b: (-(scores[b.name][0] - scores[b.name][1]),
                                              scores[b.name][1], b.name))
    best = ranked[0]
    pref, pen = scores[best.name]
    soft_hits = sorted(r["id"] for r in soft if breed_targeted(r, best))
    return Recommendation(
        operation=Operation.RECOMMEND, breed=best.name, cited_rules=cited_hard,
        oracle=oracle_label,
        rationale=f"Best preference match among breeds that satisfy the hard rules "
                  f"(score {pref}, soft penalties {pen}).",
        trace={
            "mode": "policy",
            "hard_rules_in_force": cited_hard,
            "soft_rules_in_force": sorted(r["id"] for r in soft),
            "soft_hits_on_choice": soft_hits,
            "ranking": [
                {"breed": b.name, "pref": scores[b.name][0], "soft_penalty": scores[b.name][1]}
                for b in ranked
            ],
        },
    )
