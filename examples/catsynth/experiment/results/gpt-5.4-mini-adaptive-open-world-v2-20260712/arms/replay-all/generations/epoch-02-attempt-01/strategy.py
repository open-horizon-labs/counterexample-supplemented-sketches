def recommend(profile, breeds, rules, oracle_tags):
    levels = {"low": 0, "moderate": 1, "high": 2}
    sizes = {"small": 0, "medium": 1, "large": 2}

    def get_value(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def norm_bool(v):
        return bool(v) is True

    def parse_set(value):
        if value is None or value == "":
            return set()
        if isinstance(value, str):
            return {part.strip() for part in value.split(",") if part.strip() != ""}
        return {str(value)}

    def profile_matches(rule, profile):
        trait = get_value(rule, "trait")
        op = get_value(rule, "trait_op")
        value = get_value(rule, "trait_value")
        actual = get_value(profile, trait)

        if op == "eq":
            return actual == value
        if op == "in":
            return actual in parse_set(value)
        if op == "is_true":
            return bool(actual) is True
        if op == "is_false":
            return bool(actual) is False
        return False

    def cat_matches(rule, breed):
        attr = get_value(rule, "cat_attribute")
        op = get_value(rule, "cat_op")
        value = get_value(rule, "cat_value")
        actual = get_value(breed, attr)

        if op == "eq":
            return actual == value
        if op == "in":
            return actual in parse_set(value)
        if op == "is_true":
            return bool(actual) is True
        if op == "is_false":
            return bool(actual) is False
        if op in ("gte", "lte"):
            if attr == "size":
                actual_n = sizes.get(actual)
                value_n = sizes.get(value)
            else:
                actual_n = levels.get(actual)
                value_n = levels.get(value)
            if actual_n is None or value_n is None:
                return False
            if op == "gte":
                return actual_n >= value_n
            return actual_n <= value_n
        return False

    applicable_rules = []
    for rule in rules or []:
        if profile_matches(rule, profile):
            applicable_rules.append(rule)

    forbidden_ids = []
    survivors = []
    for breed in breeds or []:
        violated = False
        violated_rules = []
        for rule in applicable_rules:
            if get_value(rule, "kind") == "forbid" and cat_matches(rule, breed):
                violated = True
                violated_rules.append(get_value(rule, "id"))
        if violated:
            forbidden_ids.extend(violated_rules)
        else:
            survivors.append(breed)

    cited_rules = []
    seen = set()
    for rid in forbidden_ids:
        if rid not in seen:
            seen.add(rid)
            cited_rules.append(rid)

    if not survivors:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": cited_rules,
            "rationale": "All breeds were removed by applicable hard forbid rules.",
        }

    want_size = get_value(profile, "wants_size")
    want_affection = bool(get_value(profile, "wants_affection"))
    want_fluffy = bool(get_value(profile, "wants_fluffy"))

    want_size_n = sizes.get(want_size) if want_size is not None else None

    scored = []
    for breed in survivors:
        score = 0
        breed_size = sizes.get(get_value(breed, "size"))
        if want_size_n is not None and breed_size is not None:
            score += max(0, 2 - abs(breed_size - want_size_n))
        if want_affection:
            score += levels.get(get_value(breed, "affection"), 0)
            score += 2 - levels.get(get_value(breed, "energy"), 0)
        if want_fluffy and bool(get_value(breed, "fluffy")):
            score += 2
        scored.append((score, str(get_value(breed, "name")), breed))

    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    return {
        "operation": "recommend",
        "breed": get_value(best, "name"),
        "cited_rules": cited_rules,
        "rationale": "Selected the highest-scoring surviving breed after applying all applicable hard forbid rules.",
    }
