def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation strategy."""

    def get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    def to_bool(value):
        return value is True

    def ordinal(value, kind):
        if kind == "level":
            mapping = {"low": 0, "moderate": 1, "high": 2}
        else:
            mapping = {"small": 0, "medium": 1, "large": 2}
        return mapping.get(value, None)

    def split_csv(value):
        if value is None:
            return []
        if not isinstance(value, str):
            value = str(value)
        parts = [piece.strip() for piece in value.split(",")]
        return [piece for piece in parts if piece]

    def matches_trait(profile_value, op, target):
        if op == "eq":
            return profile_value == target
        if op == "in":
            options = split_csv(target)
            return profile_value in options
        if op == "is_true":
            return profile_value is True
        if op == "is_false":
            return profile_value is False
        if op in ("gte", "lte"):
            left = ordinal(profile_value, "level")
            right = ordinal(target, "level")
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        return False

    def matches_cat(breed_value, op, target, attribute):
        if op == "eq":
            return breed_value == target
        if op == "in":
            options = split_csv(target)
            return breed_value in options
        if op == "is_true":
            return breed_value is True
        if op == "is_false":
            return breed_value is False
        if op in ("gte", "lte"):
            kind = "level"
            if attribute == "size":
                kind = "size"
            left = ordinal(breed_value, kind)
            right = ordinal(target, kind)
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        return False

    def is_hard_rule(rule):
        return get(rule, "kind") == "forbid"

    def is_soft_rule(rule):
        return get(rule, "kind") == "discourage"

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No catalog was supplied, so there is nothing to rank.",
        }

    profile = profile or {}
    oracle_tags = oracle_tags or []

    remaining = []
    cited_hard_rules = []

    for breed in breeds:
        removed = False
        breed_hard_rule_ids = []
        for rule in rules or []:
            if not is_hard_rule(rule):
                continue
            trait = get(rule, "trait")
            trait_op = get(rule, "trait_op")
            trait_value = get(rule, "trait_value")
            cat_attribute = get(rule, "cat_attribute")
            cat_op = get(rule, "cat_op")
            cat_value = get(rule, "cat_value")
            if not matches_trait(get(profile, trait), trait_op, trait_value):
                continue
            if not matches_cat(get(breed, cat_attribute), cat_op, cat_value, cat_attribute):
                continue
            removed = True
            breed_hard_rule_ids.append(get(rule, "id"))
        if removed:
            for rid in breed_hard_rule_ids:
                if rid not in cited_hard_rules:
                    cited_hard_rules.append(rid)
        else:
            remaining.append(breed)

    if not remaining:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": cited_hard_rules,
            "rationale": "All supplied breeds were removed by hard rules.",
        }

    wanted_size = get(profile, "wants_size")
    wanted_size_ordinal = ordinal(wanted_size, "size") if wanted_size is not None else None
    wants_affection = to_bool(get(profile, "wants_affection"))
    wants_fluffy = to_bool(get(profile, "wants_fluffy"))
    avoid_needy = "avoid_needy" in oracle_tags

    scored = []
    for breed in remaining:
        score = 0
        if wanted_size_ordinal is not None:
            breed_size = ordinal(get(breed, "size"), "size")
            if breed_size is not None:
                score += max(0, 2 - abs(breed_size - wanted_size_ordinal))
        if wants_affection:
            affection = ordinal(get(breed, "affection"), "level")
            energy = ordinal(get(breed, "energy"), "level")
            if affection is not None:
                score += affection
            if energy is not None:
                score += 2 - energy
        if wants_fluffy and get(breed, "fluffy") is True:
            score += 2
        for rule in rules or []:
            if not is_soft_rule(rule):
                continue
            trait = get(rule, "trait")
            trait_op = get(rule, "trait_op")
            trait_value = get(rule, "trait_value")
            cat_attribute = get(rule, "cat_attribute")
            cat_op = get(rule, "cat_op")
            cat_value = get(rule, "cat_value")
            if not matches_trait(get(profile, trait), trait_op, trait_value):
                continue
            if not matches_cat(get(breed, cat_attribute), cat_op, cat_value, cat_attribute):
                continue
            score -= 1
        if avoid_needy:
            sociability = ordinal(get(breed, "sociability"), "level")
            if sociability is not None and sociability >= 2:
                score -= 1
        scored.append((score, get(breed, "name", ""), breed))

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_name, best_breed = scored[0]

    rationale_bits = []
    if wanted_size_ordinal is not None:
        rationale_bits.append("matched size preference")
    if wants_affection:
        rationale_bits.append("balanced affection and calmness")
    if wants_fluffy:
        rationale_bits.append("honored fluffy preference")
    if avoid_needy:
        rationale_bits.append("applied avoid_needy narrative tag")
    if not rationale_bits:
        rationale_bits.append("best fit after hard-rule filtering")

    return {
        "operation": "recommend",
        "breed": best_name,
        "cited_rules": cited_hard_rules,
        "rationale": "; ".join(rationale_bits),
    }
