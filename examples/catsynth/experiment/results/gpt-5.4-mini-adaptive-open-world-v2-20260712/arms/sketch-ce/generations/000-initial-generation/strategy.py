def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic initial CatSynth recommendation strategy.

    This implementation follows the current sketch:
    - rank breeds by explicit owner preferences
    - do not assign semantics to rules or oracle_tags yet
    - never inspect scenario_id
    - break ties by breed name
    """

    size_order = {"small": 0, "medium": 1, "large": 2}
    ordinal_order = {"low": 0, "moderate": 1, "high": 2}

    def norm_bool(value):
        return value is True

    def norm_size(value):
        return size_order.get(value, None)

    def norm_ord(value):
        return ordinal_order.get(value, None)

    def score_breed(breed):
        score = 0

        wanted_size = norm_size(profile.get("wants_size"))
        breed_size = norm_size(breed.get("size"))
        if wanted_size is not None and breed_size is not None:
            score += max(0, 2 - abs(breed_size - wanted_size))

        if norm_bool(profile.get("wants_affection")):
            affection = norm_ord(breed.get("affection"))
            energy = norm_ord(breed.get("energy"))
            if affection is not None:
                score += affection
            if energy is not None:
                score += 2 - energy

        if norm_bool(profile.get("wants_fluffy")) and breed.get("fluffy") is True:
            score += 2

        return score

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is no candidate to recommend."
        }

    ranked = []
    for breed in breeds:
        name = breed.get("name")
        if name is None:
            continue
        ranked.append((score_breed(breed), name, breed))

    if not ranked:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breed names were available to rank."
        }

    ranked.sort(key=lambda item: (-item[0], item[1]))
    _, chosen_name, _chosen_breed = ranked[0]

    rationale_parts = ["Chosen by explicit preference score"]
    if profile.get("wants_size") is not None:
        rationale_parts.append("size match")
    if profile.get("wants_affection") is True:
        rationale_parts.append("affection and calmness")
    if profile.get("wants_fluffy") is True:
        rationale_parts.append("fluffiness")

    return {
        "operation": "recommend",
        "breed": chosen_name,
        "cited_rules": [],
        "rationale": "; ".join(rationale_parts) + "."
    }
