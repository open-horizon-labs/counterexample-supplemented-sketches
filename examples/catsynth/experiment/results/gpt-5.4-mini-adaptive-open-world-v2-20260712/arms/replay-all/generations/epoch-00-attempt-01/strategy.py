"""Deterministic CatSynth initial recommendation strategy."""

SIZE_ORDER = {"small": 0, "medium": 1, "large": 2}
LEVEL_ORDER = {"low": 0, "moderate": 1, "high": 2}


def _ordinal_value(value, mapping):
    return mapping.get(value, None)


def _breed_score(profile, breed):
    score = 0

    wanted_size = profile.get("wants_size")
    breed_size = _ordinal_value(breed.get("size"), SIZE_ORDER)
    if wanted_size is not None and breed_size is not None:
        score += max(0, 2 - abs(breed_size - wanted_size))

    if profile.get("wants_affection"):
        affection = _ordinal_value(breed.get("affection"), LEVEL_ORDER)
        energy = _ordinal_value(breed.get("energy"), LEVEL_ORDER)
        if affection is not None:
            score += affection
        if energy is not None:
            score += 2 - energy

    if profile.get("wants_fluffy"):
        score += 2 if breed.get("fluffy") is True else 0

    return score


def recommend(profile, breeds, rules, oracle_tags):
    """Return the best-scoring breed from the supplied catalog."""
    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is nothing to rank.",
        }

    ranked = sorted(
        breeds,
        key=lambda breed: (-_breed_score(profile, breed), breed.get("name", "")),
    )
    best = ranked[0]
    return {
        "operation": "recommend",
        "breed": best.get("name"),
        "cited_rules": [],
        "rationale": "Selected the highest-scoring breed under the current initial preference-only policy.",
    }
