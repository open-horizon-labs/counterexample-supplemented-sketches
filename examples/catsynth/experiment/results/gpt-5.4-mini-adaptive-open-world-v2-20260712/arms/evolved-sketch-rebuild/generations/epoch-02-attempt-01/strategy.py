def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation strategy.

    Inputs are treated as plain dictionaries / lists with the contract fields.
    oracle_tags is accepted for signature stability but does not affect selection.
    """

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is no catalog to evaluate.",
        }

    size_rank = {"small": 0, "medium": 1, "large": 2}
    ordinal_rank = {"low": 0, "moderate": 1, "high": 2}

    def get_value(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    def as_bool(value):
        return value is True

    def split_csv(value):
        if value is None:
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return []

    def profile_matches(rule):
        trait = get_value(rule, "trait")
        op = get_value(rule, "trait_op")
        raw = get_value(rule, "trait_value")
        profile_value = get_value(profile, trait)

        if op == "eq":
            return profile_value == raw
        if op == "in":
            options = split_csv(raw)
            return str(profile_value) in options
        if op == "gte":
            return ordinal_rank.get(profile_value, -1) >= ordinal_rank.get(raw, -1)
        if op == "lte":
            return ordinal_rank.get(profile_value, -1) <= ordinal_rank.get(raw, -1)
        if op == "is_true":
            return as_bool(profile_value)
        if op == "is_false":
            return not as_bool(profile_value)
        return False

    def breed_matches(rule, breed):
        attr = get_value(rule, "cat_attribute")
        op = get_value(rule, "cat_op")
        raw = get_value(rule, "cat_value")
        breed_value = get_value(breed, attr)

        if op == "eq":
            return breed_value == raw
        if op == "in":
            options = split_csv(raw)
            return str(breed_value) in options
        if op == "gte":
            return ordinal_rank.get(breed_value, -1) >= ordinal_rank.get(raw, -1)
        if op == "lte":
            return ordinal_rank.get(breed_value, -1) <= ordinal_rank.get(raw, -1)
        if op == "is_true":
            return as_bool(breed_value)
        if op == "is_false":
            return not as_bool(breed_value)
        return False

    def is_hard_forbid(rule):
        return get_value(rule, "kind") == "forbid"

    def size_score(breed):
        wanted = get_value(profile, "wants_size")
        if wanted is None:
            return 0
        return max(0, 2 - abs(size_rank.get(get_value(breed, "size"), -1) - size_rank.get(wanted, -1)))

    def affection_score(breed):
        if not as_bool(get_value(profile, "wants_affection")):
            return 0
        return ordinal_rank.get(get_value(breed, "affection"), 0) + (2 - ordinal_rank.get(get_value(breed, "energy"), 0))

    def fluffy_score(breed):
        return 2 if as_bool(get_value(profile, "wants_fluffy")) and as_bool(get_value(breed, "fluffy")) else 0

    hard_rule_ids = []
    remaining = []

    for breed in breeds:
        removed_by = []
        for rule in rules or []:
            if not is_hard_forbid(rule):
                continue
            if profile_matches(rule) and breed_matches(rule, breed):
                rid = get_value(rule, "id")
                if rid is not None:
                    removed_by.append(str(rid))
        if removed_by:
            hard_rule_ids.extend(removed_by)
        else:
            remaining.append(breed)

    seen = set()
    hard_rule_ids = [rid for rid in hard_rule_ids if not (rid in seen or seen.add(rid))]

    if not remaining:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": hard_rule_ids,
            "rationale": "All supplied breeds were removed by applicable hard rules.",
        }

    scored = []
    for breed in remaining:
        score = size_score(breed) + affection_score(breed) + fluffy_score(breed)
        scored.append((score, str(get_value(breed, "name", "")), breed))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_name, best_breed = scored[0]

    return {
        "operation": "recommend",
        "breed": best_name,
        "cited_rules": hard_rule_ids,
        "rationale": "Selected the highest-ranked remaining breed after applying hard-rule filters.",
    }
