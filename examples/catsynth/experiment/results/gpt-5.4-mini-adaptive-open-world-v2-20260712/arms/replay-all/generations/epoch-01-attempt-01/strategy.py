def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation.

    Returns a dict with keys: operation, breed, cited_rules, rationale.
    """

    size_order = {"small": 0, "medium": 1, "large": 2}
    level_order = {"low": 0, "moderate": 1, "high": 2}

    def norm(v):
        if isinstance(v, str):
            return v.strip().lower()
        return v

    def as_bool(v):
        return bool(v) if isinstance(v, bool) else str(v).strip().lower() == "true"

    def parse_in_values(raw):
        if raw is None:
            return set()
        if isinstance(raw, str):
            return {part.strip().lower() for part in raw.split(",") if part.strip()}
        return {norm(raw)}

    def get_trait_value(row):
        return norm(profile.get(row.get("trait")))

    def profile_matches(row):
        trait_op = row.get("trait_op")
        trait_value = row.get("trait_value")
        value = get_trait_value(row)
        if trait_op == "eq":
            return value == norm(trait_value)
        if trait_op == "in":
            return value in parse_in_values(trait_value)
        return False

    def cat_violates(row, breed):
        attr = row.get("cat_attribute")
        op = row.get("cat_op")
        expected = row.get("cat_value")
        actual = breed.get(attr)
        if op == "is_true":
            return as_bool(actual) is True
        if op == "is_false":
            return as_bool(actual) is False
        if op == "eq":
            return norm(actual) == norm(expected)
        if op == "in":
            return norm(actual) in parse_in_values(expected)
        if op == "gte":
            return level_order.get(norm(actual), -1) >= level_order.get(norm(expected), -1)
        if op == "lte":
            return level_order.get(norm(actual), -1) <= level_order.get(norm(expected), -1)
        return False

    applicable_rules = [row for row in (rules or []) if profile_matches(row)]

    filtered = []
    for breed in (breeds or []):
        violated = []
        for row in applicable_rules:
            if row.get("kind") == "forbid" and cat_violates(row, breed):
                violated.append(row.get("id"))
        if not violated:
            filtered.append((breed, violated))

    if not filtered:
        cited = []
        for row in applicable_rules:
            if row.get("kind") == "forbid":
                cited.append(row.get("id"))
        cited = [r for r in cited if r]
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": cited,
            "rationale": "All candidate breeds violate one or more applicable forbid rules; no safe recommendation remains."
        }

    wanted_size = size_order.get(norm(profile.get("wants_size"))) if profile.get("wants_size") else None
    wants_affection = bool(profile.get("wants_affection"))
    wants_fluffy = bool(profile.get("wants_fluffy"))

    scored = []
    for breed, _violated in filtered:
        score = 0
        if wanted_size is not None:
            score += max(0, 2 - abs(size_order.get(norm(breed.get("size")), 1) - wanted_size))
        if wants_affection:
            score += level_order.get(norm(breed.get("affection")), 0)
            score += 2 - level_order.get(norm(breed.get("energy")), 1)
        if wants_fluffy:
            score += 2 if as_bool(breed.get("fluffy")) else 0
        scored.append((score, norm(breed.get("name")), breed))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, best_breed = scored[0]

    cited_rules = []
    for row in applicable_rules:
        if row.get("kind") == "forbid" and cat_violates(row, best_breed):
            cited_rules.append(row.get("id"))
    cited_rules = [r for r in cited_rules if r]

    rationale_bits = ["Selected the highest-scoring breed after applying applicable hard policy filters."]
    if wanted_size is not None:
        rationale_bits.append("Size preference contributed to ranking.")
    if wants_affection:
        rationale_bits.append("Affection preference and lower energy contributed to ranking.")
    if wants_fluffy:
        rationale_bits.append("Fluffy preference contributed to ranking.")
    if cited_rules:
        rationale_bits.append("The chosen breed satisfies the applicable forbid rules.")

    return {
        "operation": "recommend",
        "breed": best_breed.get("name"),
        "cited_rules": cited_rules,
        "rationale": " ".join(rationale_bits)
    }
