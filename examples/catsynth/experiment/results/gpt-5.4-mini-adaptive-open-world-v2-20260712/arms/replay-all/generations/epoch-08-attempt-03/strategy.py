def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation with no imports or file access."""

    size_order = {"small": 0, "medium": 1, "large": 2}
    level_order = {"low": 0, "moderate": 1, "high": 2}
    valid_kind = {"forbid", "discourage"}
    valid_trait_ops = {"eq", "in", "is_true", "is_false", "gte", "lte"}
    valid_cat_ops = {"eq", "in", "is_true", "is_false", "gte", "lte"}
    valid_bool_text = {"true", "false"}
    valid_allergies = {"none", "mild", "severe"}

    def normalize_text(value):
        return "" if value is None else str(value).strip()

    def lower_text(value):
        return normalize_text(value).lower()

    def parse_csv(value):
        text = normalize_text(value)
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def as_bool(value):
        if isinstance(value, bool):
            return value
        text = lower_text(value)
        if text in valid_bool_text:
            return text == "true"
        return bool(value)

    def ordinal_value(field, value):
        text = lower_text(value)
        if field == "size":
            return size_order.get(text, None)
        return level_order.get(text, None)

    def get_profile_value(field):
        return profile.get(field)

    def get_breed_value(breed, field):
        return breed.get(field)

    def supports_rule_shape(rule):
        kind = lower_text(rule.get("kind"))
        trait_op = lower_text(rule.get("trait_op"))
        cat_op = lower_text(rule.get("cat_op"))
        attr = lower_text(rule.get("cat_attribute"))
        trait = lower_text(rule.get("trait"))
        if kind not in valid_kind:
            return False
        if trait_op not in valid_trait_ops or cat_op not in valid_cat_ops:
            return False
        if not trait or not attr:
            return False
        if trait_op in {"gte", "lte"} and trait not in {"wants_size", "activity_level", "noise_tolerance", "experience"}:
            return False
        if cat_op in {"gte", "lte"} and attr not in {"size", "energy", "shedding", "grooming", "sociability", "vocal", "affection"}:
            return False
        return True

    def trait_matches(rule):
        trait = rule.get("trait")
        op = lower_text(rule.get("trait_op"))
        expected = rule.get("trait_value")
        actual = get_profile_value(trait)
        actual_text = lower_text(actual)
        expected_text = lower_text(expected)

        if op == "eq":
            return actual_text == expected_text
        if op == "in":
            return actual_text in [lower_text(item) for item in parse_csv(expected)]
        if op == "is_true":
            return as_bool(actual) is True
        if op == "is_false":
            return as_bool(actual) is False
        if op == "gte":
            return ordinal_value(trait, actual) is not None and ordinal_value(trait, expected) is not None and ordinal_value(trait, actual) >= ordinal_value(trait, expected)
        if op == "lte":
            return ordinal_value(trait, actual) is not None and ordinal_value(trait, expected) is not None and ordinal_value(trait, actual) <= ordinal_value(trait, expected)
        return False

    def cat_matches(rule, breed):
        attr = rule.get("cat_attribute")
        op = lower_text(rule.get("cat_op"))
        expected = rule.get("cat_value")
        actual = get_breed_value(breed, attr)
        actual_text = lower_text(actual)
        expected_text = lower_text(expected)

        if op == "eq":
            return actual_text == expected_text
        if op == "in":
            return actual_text in [lower_text(item) for item in parse_csv(expected)]
        if op == "is_true":
            return as_bool(actual) is True
        if op == "is_false":
            return as_bool(actual) is False
        if op == "gte":
            return ordinal_value(attr, actual) is not None and ordinal_value(attr, expected) is not None and ordinal_value(attr, actual) >= ordinal_value(attr, expected)
        if op == "lte":
            return ordinal_value(attr, actual) is not None and ordinal_value(attr, expected) is not None and ordinal_value(attr, actual) <= ordinal_value(attr, expected)
        return False

    def rule_applies_to_profile(rule):
        if not supports_rule_shape(rule):
            return False
        return trait_matches(rule)

    def rule_blocks_breed(rule, breed):
        if lower_text(rule.get("kind")) != "forbid":
            return False
        return rule_applies_to_profile(rule) and cat_matches(rule, breed)

    def rule_discourages_breed(rule, breed):
        if lower_text(rule.get("kind")) != "discourage":
            return False
        return rule_applies_to_profile(rule) and cat_matches(rule, breed)

    allergies = lower_text(get_profile_value("allergies"))
    if allergies and allergies not in valid_allergies:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "Allergy status is unknown or unsupported, so the recommendation is escalated for clarification."
        }

    applicable_forbid_ids = []
    applicable_discourage_rules = []

    for rule in rules or []:
        if not rule_applies_to_profile(rule):
            if lower_text(rule.get("kind")) in valid_kind:
                continue
            if trait_matches(rule) or cat_matches(rule, (breeds or [{}])[0] if breeds else {}):
                rule_id = rule.get("id")
                return {
                    "operation": "escalate",
                    "breed": None,
                    "cited_rules": [str(rule_id)] if rule_id is not None else [],
                    "rationale": "An applicable policy row uses an unsupported or uninterpretable rule shape."
                }
            continue

        kind = lower_text(rule.get("kind"))
        rule_id = rule.get("id")
        if kind == "forbid" and rule_id is not None:
            applicable_forbid_ids.append(str(rule_id))
        elif kind == "discourage":
            applicable_discourage_rules.append(rule)

    available = []
    for breed in breeds or []:
        blocked = False
        for rule in rules or []:
            if rule_blocks_breed(rule, breed):
                blocked = True
                break
        if not blocked:
            available.append(breed)

    if not available:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": applicable_forbid_ids,
            "rationale": "No breed remains after applying all applicable hard rules."
        }

    has_avoid_needy = any(normalize_text(tag) == "avoid_needy" for tag in (oracle_tags or []))

    wanted_size = get_profile_value("wants_size")
    size_target = size_order.get(lower_text(wanted_size), None) if wanted_size else None
    wants_affection = as_bool(get_profile_value("wants_affection"))
    wants_fluffy = as_bool(get_profile_value("wants_fluffy"))

    best_breed = None
    best_score = None
    best_name = None

    for breed in available:
        score = 0
        breed_size = size_order.get(lower_text(get_breed_value(breed, "size")), -1)
        if size_target is not None and breed_size != -1:
            score += max(0, 2 - abs(breed_size - size_target))
        if wants_affection:
            affection = level_order.get(lower_text(get_breed_value(breed, "affection")), 0)
            energy = level_order.get(lower_text(get_breed_value(breed, "energy")), 0)
            score += affection + (2 - energy)
        if wants_fluffy:
            score += 2 if as_bool(get_breed_value(breed, "fluffy")) else 0
        if has_avoid_needy and level_order.get(lower_text(get_breed_value(breed, "sociability")), -1) >= level_order["high"]:
            score -= 1

        name = normalize_text(get_breed_value(breed, "name"))
        if best_breed is None or score > best_score or (score == best_score and name < best_name):
            best_breed = breed
            best_score = score
            best_name = name

    cited_rules = []
    seen = set()
    for rule_id in applicable_forbid_ids:
        if rule_id not in seen:
            cited_rules.append(rule_id)
            seen.add(rule_id)

    return {
        "operation": "recommend",
        "breed": best_name,
        "cited_rules": cited_rules,
        "rationale": "Selected the highest-scoring available breed using explicit preferences, hard-rule filtering, and any controlled soft penalty tags."
    }
