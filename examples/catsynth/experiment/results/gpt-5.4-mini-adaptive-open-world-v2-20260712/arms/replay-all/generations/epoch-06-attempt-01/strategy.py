def recommend(profile, breeds, rules, oracle_tags):
    low = {"low": 0, "moderate": 1, "high": 2}
    size = {"small": 0, "medium": 1, "large": 2}

    def parse_set(value):
        if value is None or value == "":
            return set()
        return {item.strip() for item in str(value).split(",") if item.strip()}

    def getv(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def match_trait(profile_val, op, rule_val):
        if op == "eq":
            return profile_val == rule_val
        if op == "in":
            return profile_val in parse_set(rule_val)
        if op == "is_true":
            return bool(profile_val) is True
        if op == "is_false":
            return bool(profile_val) is False
        return False

    def match_cat(cat_val, op, rule_val):
        if op == "eq":
            return cat_val == rule_val
        if op == "in":
            return cat_val in parse_set(rule_val)
        if op == "is_true":
            return bool(cat_val) is True
        if op == "is_false":
            return bool(cat_val) is False
        if op == "gte":
            return low.get(cat_val, -1) >= low.get(rule_val, -1)
        if op == "lte":
            return low.get(cat_val, -1) <= low.get(rule_val, -1)
        return False

    hard_rule_ids = []
    hard_forbids = []
    soft_predicates = []

    for rule in rules or []:
        trait = getv(rule, "trait")
        trait_op = getv(rule, "trait_op")
        trait_value = getv(rule, "trait_value")
        kind = getv(rule, "kind")
        cat_attribute = getv(rule, "cat_attribute")
        cat_op = getv(rule, "cat_op")
        cat_value = getv(rule, "cat_value")
        rule_id = getv(rule, "id")

        if not match_trait(getv(profile, trait), trait_op, trait_value):
            continue

        if kind == "forbid":
            hard_rule_ids.append(rule_id)
            hard_forbids.append((cat_attribute, cat_op, cat_value))
        elif kind == "discourage":
            soft_predicates.append((cat_attribute, cat_op, cat_value))

    survivors = []
    for breed in breeds or []:
        ok = True
        for cat_attribute, cat_op, cat_value in hard_forbids:
            if match_cat(getv(breed, cat_attribute), cat_op, cat_value):
                ok = False
                break
        if ok:
            survivors.append(breed)

    if not survivors:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": hard_rule_ids,
            "rationale": "No breed survives the applicable hard rules."
        }

    tag_preds = []
    for tag in oracle_tags or []:
        if tag == "avoid_needy":
            tag_preds.append(("sociability", "gte", "high"))
        elif tag == "avoid_high_energy":
            tag_preds.append(("energy", "gte", "high"))

    # Deduplicate soft penalties by semantic predicate.
    seen = set()
    penalties = []
    for pred in soft_predicates + tag_preds:
        if pred not in seen:
            seen.add(pred)
            penalties.append(pred)

    def breed_score(breed):
        score = 0
        wanted_size = getv(profile, "wants_size")
        if wanted_size:
            score += max(0, 2 - abs(size.get(getv(breed, "size"), -1) - size.get(wanted_size, -1)))
        if getv(profile, "wants_affection"):
            score += low.get(getv(breed, "affection"), 0) + (2 - low.get(getv(breed, "energy"), 0))
        if getv(profile, "wants_fluffy"):
            score += 2 if bool(getv(breed, "fluffy")) else 0

        for cat_attribute, cat_op, cat_value in penalties:
            if match_cat(getv(breed, cat_attribute), cat_op, cat_value):
                score -= 1
        return score

    best = sorted(survivors, key=lambda b: (-breed_score(b), getv(b, "name", "")))[0]
    return {
        "operation": "recommend",
        "breed": getv(best, "name"),
        "cited_rules": hard_rule_ids,
        "rationale": "Chosen by deterministic ranking after applying hard rules and any applicable soft penalties."
    }
