def _ordinal_value(value, mapping):
    return mapping.get(value, None)


def _size_value(value):
    return _ordinal_value(value, {"small": 0, "medium": 1, "large": 2})


def _ord_value(value):
    return _ordinal_value(value, {"low": 0, "moderate": 1, "high": 2})


def _as_bool(value):
    return bool(value)


def _preference_score(profile, breed):
    score = 0

    wants_size = profile.get("wants_size")
    if wants_size:
        wanted = _size_value(wants_size)
        actual = _size_value(breed.get("size"))
        if wanted is not None and actual is not None:
            score += max(0, 2 - abs(actual - wanted))

    if _as_bool(profile.get("wants_affection")):
        affection = _ord_value(breed.get("affection"))
        energy = _ord_value(breed.get("energy"))
        if affection is not None:
            score += affection
        if energy is not None:
            score += 2 - energy

    if _as_bool(profile.get("wants_fluffy")):
        if _as_bool(breed.get("fluffy")):
            score += 2

    return score


def recommend(profile, breeds, rules, oracle_tags):
    candidates = list(breeds or [])
    if not candidates:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is nothing to recommend.",
        }

    ranked = []
    for breed in candidates:
        name = breed.get("name")
        if not isinstance(name, str) or not name:
            continue
        ranked.append((
            _preference_score(profile or {}, breed or {}),
            name,
            breed,
        ))

    if not ranked:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breed rows had a usable name, so the strategy cannot choose one.",
        }

    ranked.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_name, _best_breed = ranked[0]

    rationale_bits = ["Selected the highest-scoring breed from the supplied catalog."]
    if profile and profile.get("wants_size"):
        rationale_bits.append(f"Matched size preference {profile.get('wants_size')} when possible.")
    if _as_bool(profile.get("wants_affection")):
        rationale_bits.append("Rewarded affectionate, calmer breeds.")
    if _as_bool(profile.get("wants_fluffy")):
        rationale_bits.append("Added a bonus for fluffy coats.")

    return {
        "operation": "recommend",
        "breed": best_name,
        "cited_rules": [],
        "rationale": f"{rationale_bits[0]} Score={best_score}. " + " ".join(rationale_bits[1:]),
    }
