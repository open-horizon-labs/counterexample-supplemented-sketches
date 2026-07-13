def recommend(profile, breeds, rules, oracle_tags):
    levels = {"low": 0, "moderate": 1, "high": 2}
    sizes = {"small": 0, "medium": 1, "large": 2}

    def get(d, key, default=None):
        return d[key] if isinstance(d, dict) and key in d else default

    def parse_set(value):
        if value is None or value == "":
            return set()
        return {part.strip() for part in str(value).split(",") if part.strip()}

    def trait_matches(profile_value, op, rule_value):
        if op == "eq":
            return profile_value == rule_value
        if op == "in":
            return profile_value in parse_set(rule_value)
        if op == "is_true":
            return bool(profile_value) is True
        if op == "is_false":
            return bool(profile_value) is False
        return False

    def cat_matches(cat_value, op, rule_value):
        if op == "eq":
            return cat_value == rule_value
        if op == "in":
            return cat_value in parse_set(rule_value)
        if op == "is_true":
            return bool(cat_value) is True
        if op == "is_false":
            return bool(cat_value) is False
        if op in ("gte", "lte"):
            left = levels.get(cat_value, cat_value)
            right = levels.get(rule_value, rule_value)
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    active_forbids = []
    for rule in rules or []:
        if get(rule, "kind") != "forbid":
            continue
        trait = get(rule, "trait")
        trait_op = get(rule, "trait_op")
        trait_value = get(rule, "trait_value")
        if not trait_matches(get(profile, trait), trait_op, trait_value):
            continue
        active_forbids.append(rule)

    candidates = []
    for breed in breeds or []:
        violated = []
        for rule in active_forbids:
            cat_attribute = get(rule, "cat_attribute")
            cat_op = get(rule, "cat_op")
            cat_value = get(rule, "cat_value")
            if cat_matches(get(breed, cat_attribute), cat_op, cat_value):
                violated.append(get(rule, "id"))
        if not violated:
            candidates.append((breed, violated))

    cited_rules = []
    if active_forbids:
        cited_rules = sorted({get(rule, "id") for rule in active_forbids if get(rule, "id")})

    if not candidates:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": cited_rules,
            "rationale": "All breeds were removed by applicable hard rules."
        }

    wants_size = get(profile, "wants_size")
    wants_affection = bool(get(profile, "wants_affection"))
    wants_fluffy = bool(get(profile, "wants_fluffy"))
    soft_tags = set(oracle_tags or [])

    scored = []
    for breed, _ in candidates:
        score = 0
        if wants_size in sizes:
            score += max(0, 2 - abs(sizes.get(get(breed, "size"), 1) - sizes[wants_size]))
        if wants_affection:
            score += levels.get(get(breed, "affection"), 0) + (2 - levels.get(get(breed, "energy"), 1))
        if wants_fluffy:
            score += 2 if bool(get(breed, "fluffy")) else 0
        if "avoid_needy" in soft_tags:
            score += 2 - levels.get(get(breed, "sociability"), 1)
        scored.append((score, str(get(breed, "name", "")), breed))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best = scored[0][2]

    return {
        "operation": "recommend",
        "breed": get(best, "name"),
        "cited_rules": cited_rules,
        "rationale": "Selected the highest-scoring breed after applying hard-rule filtering and preference ranking."
    }
