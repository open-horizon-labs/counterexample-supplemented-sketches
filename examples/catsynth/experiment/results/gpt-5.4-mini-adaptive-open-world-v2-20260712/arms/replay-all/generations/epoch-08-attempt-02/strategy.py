def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation with no imports or file access."""

    size_order = {"small": 0, "medium": 1, "large": 2}
    level_order = {"low": 0, "moderate": 1, "high": 2}

    def as_bool(value):
        return bool(value)

    def normalize_text(value):
        return "" if value is None else str(value)

    def parse_csv(value):
        text = normalize_text(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def get_profile_value(field):
        return profile.get(field)

    def get_breed_value(breed, field):
        return breed.get(field)

    def matches_trait(rule, breed):
        trait = rule.get("trait")
        op = rule.get("trait_op")
        expected = rule.get("trait_value")
        actual = get_profile_value(trait) if trait in profile else get_breed_value(breed, trait)

        if op == "eq":
            return normalize_text(actual) == normalize_text(expected)
        if op == "in":
            return normalize_text(actual) in parse_csv(expected)
        if op == "is_true":
            return as_bool(actual)
        if op == "is_false":
            return not as_bool(actual)
        if op == "gte":
            if trait in ("wants_size",):
                return size_order.get(normalize_text(actual), -1) >= size_order.get(normalize_text(expected), -1)
            return level_order.get(normalize_text(actual), -1) >= level_order.get(normalize_text(expected), -1)
        if op == "lte":
            if trait in ("wants_size",):
                return size_order.get(normalize_text(actual), -1) <= size_order.get(normalize_text(expected), -1)
            return level_order.get(normalize_text(actual), -1) <= level_order.get(normalize_text(expected), -1)
        return False

    def matches_cat(rule, breed):
        attr = rule.get("cat_attribute")
        op = rule.get("cat_op")
        expected = rule.get("cat_value")
        actual = get_breed_value(breed, attr)

        if op == "eq":
            return normalize_text(actual) == normalize_text(expected)
        if op == "in":
            return normalize_text(actual) in parse_csv(expected)
        if op == "is_true":
            return as_bool(actual)
        if op == "is_false":
            return not as_bool(actual)
        if op == "gte":
            if attr == "size":
                return size_order.get(normalize_text(actual), -1) >= size_order.get(normalize_text(expected), -1)
            return level_order.get(normalize_text(actual), -1) >= level_order.get(normalize_text(expected), -1)
        if op == "lte":
            if attr == "size":
                return size_order.get(normalize_text(actual), -1) <= size_order.get(normalize_text(expected), -1)
            return level_order.get(normalize_text(actual), -1) <= level_order.get(normalize_text(expected), -1)
        return False

    def rule_matches(rule, breed):
        return matches_trait(rule, breed) and matches_cat(rule, breed)

    def rule_blocks_breed(rule, breed):
        kind = normalize_text(rule.get("kind")).lower()
        if kind in {"exclude", "ban", "block", "forbid", "reject"}:
            return rule_matches(rule, breed)
        return False

    candidates = []
    for breed in breeds or []:
        blocked = False
        cited = []
        for rule in rules or []:
            if rule_blocks_breed(rule, breed):
                blocked = True
                rule_id = rule.get("id")
                if rule_id is not None:
                    cited.append(str(rule_id))
        if not blocked:
            candidates.append((breed, cited))

    if not candidates:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breed remains after applying active blocking rules."
        }

    wanted_size = get_profile_value("wants_size")
    size_target = size_order.get(normalize_text(wanted_size), None) if wanted_size else None
    wants_affection = as_bool(get_profile_value("wants_affection"))
    wants_fluffy = as_bool(get_profile_value("wants_fluffy"))

    best_breed = None
    best_score = None
    best_cited = []

    for breed, cited in candidates:
        score = 0
        breed_size = size_order.get(normalize_text(get_breed_value(breed, "size")), -1)
        if size_target is not None:
            score += max(0, 2 - abs(breed_size - size_target))
        if wants_affection:
            affection = level_order.get(normalize_text(get_breed_value(breed, "affection")), 0)
            energy = level_order.get(normalize_text(get_breed_value(breed, "energy")), 0)
            score += affection + (2 - energy)
        if wants_fluffy:
            score += 2 if as_bool(get_breed_value(breed, "fluffy")) else 0

        name = normalize_text(get_breed_value(breed, "name"))
        if best_breed is None or score > best_score or (score == best_score and name < normalize_text(get_breed_value(best_breed, "name"))):
            best_breed = breed
            best_score = score
            best_cited = cited

    return {
        "operation": "recommend",
        "breed": normalize_text(get_breed_value(best_breed, "name")),
        "cited_rules": best_cited,
        "rationale": "Selected the highest-scoring available breed using explicit size, affection, and fluffy preferences."
    }
