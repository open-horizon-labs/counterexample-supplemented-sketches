def recommend(profile, breeds, rules, oracle_tags):
    levels = {"low": 0, "moderate": 1, "high": 2}
    sizes = {"small": 0, "medium": 1, "large": 2}

    def get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    def as_list(value):
        return value if isinstance(value, list) else []

    def split_csv(text):
        if not text:
            return []
        return [part.strip() for part in str(text).split(",") if part.strip()]

    def profile_matches(rule):
        trait = get(rule, "trait")
        op = get(rule, "trait_op")
        target = get(rule, "trait_value")
        value = get(profile, trait)
        if op == "eq":
            return value == target
        if op == "in":
            return str(value) in split_csv(target)
        if op == "is_true":
            return bool(value) is True
        if op == "is_false":
            return bool(value) is False
        return False

    def cat_matches(breed, rule):
        attr = get(rule, "cat_attribute")
        op = get(rule, "cat_op")
        target = get(rule, "cat_value")
        value = get(breed, attr)
        if op == "eq":
            return value == target
        if op == "in":
            return str(value) in split_csv(target)
        if op == "is_true":
            return bool(value) is True
        if op == "is_false":
            return bool(value) is False
        if op in ("gte", "lte"):
            left = levels.get(value, sizes.get(value))
            right = levels.get(target, sizes.get(target))
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    applicable_forbid_ids = []
    applicable_discourage_rules = []
    for rule in as_list(rules):
        if not profile_matches(rule):
            continue
        kind = get(rule, "kind")
        if kind == "forbid":
            applicable_forbid_ids.append(get(rule, "id"))
        elif kind == "discourage":
            applicable_discourage_rules.append(rule)

    filtered = []
    for breed in as_list(breeds):
        blocked = False
        for rule in as_list(rules):
            if get(rule, "kind") != "forbid":
                continue
            if profile_matches(rule) and cat_matches(breed, rule):
                blocked = True
                break
        if not blocked:
            filtered.append(breed)

    if not filtered:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": applicable_forbid_ids,
            "rationale": "No breed survives the applicable hard forbid rules."
        }

    tags = set(as_list(oracle_tags))
    best_breed = None
    best_score = None

    want_size = get(profile, "wants_size")
    want_affection = bool(get(profile, "wants_affection"))
    want_fluffy = bool(get(profile, "wants_fluffy"))

    for breed in filtered:
        score = 0
        if want_size in sizes:
            score += max(0, 2 - abs(sizes.get(get(breed, "size"), 1) - sizes[want_size]))
        if want_affection:
            score += levels.get(get(breed, "affection"), 0) + (2 - levels.get(get(breed, "energy"), 1))
        if want_fluffy:
            score += 2 if bool(get(breed, "fluffy")) else 0

        for tag in tags:
            if tag == "avoid_needy":
                if levels.get(get(breed, "sociability"), 0) >= levels["high"]:
                    score -= 1

        name = str(get(breed, "name", ""))
        if best_breed is None or score > best_score or (score == best_score and name < str(get(best_breed, "name", ""))):
            best_breed = breed
            best_score = score

    return {
        "operation": "recommend",
        "breed": get(best_breed, "name"),
        "cited_rules": applicable_forbid_ids,
        "rationale": "Filtered hard-forbidden breeds first, then ranked remaining breeds by explicit preferences with controlled oracle tag penalties."
    }
