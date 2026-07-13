def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic CatSynth recommendation strategy.

    Policy:
    - Apply promoted hard rules first.
    - If allergies is missing, blank, unknown, or outside the approved set,
      escalate because the safety input is unresolved.
    - If any applicable rule row is malformed or uses an unsupported kind,
      trait operator, cat operator, attribute, or ordinal value, escalate and
      cite that rule ID so the policy source can be repaired.
    - If hard rules eliminate every supplied breed, abstain and cite the hard
      rule IDs.
    - If breeds is empty, escalate because there is no catalog to evaluate.
    - Rank remaining breeds by explicit owner preferences.
    - Apply every distinct applicable discourage rule as a soft penalty during
      ranking, but deduplicate soft penalties by semantic predicate so the same
      concern is only counted once even if it appears in both structured rules
      and narrative tags.
    - Consume controlled soft tags from oracle_tags only as described in the
      sketch.
    - Never inspect scenario_id.
    - Do not hard-code named fixtures.
    """

    size_order = {"small": 0, "medium": 1, "large": 2}
    ordinal_order = {"low": 0, "moderate": 1, "high": 2}
    valid_allergies = {"none", "mild", "severe"}
    valid_kinds = {"forbid", "discourage"}
    valid_trait_ops = {"eq", "in", "is_true", "is_false", "gte", "lte"}
    valid_cat_ops = {"eq", "in", "is_true", "is_false", "gte", "lte"}
    valid_cat_attributes = {
        "size",
        "energy",
        "shedding",
        "grooming",
        "sociability",
        "vocal",
        "affection",
        "hypoallergenic",
        "good_with_children",
        "fluffy",
    }

    def norm_bool(value):
        return value is True

    def norm_size(value):
        return size_order.get(value, None)

    def norm_ord(value):
        return ordinal_order.get(value, None)

    def split_csv(value):
        if value is None or value == "":
            return []
        parts = []
        for item in str(value).split(","):
            item = item.strip()
            if item:
                parts.append(item)
        return parts

    def ordinal_value_ok(value):
        return value in ordinal_order

    def profile_matches(rule):
        trait = rule.get("trait")
        op = rule.get("trait_op")
        target = profile.get(trait)
        rule_value = rule.get("trait_value")

        if op == "eq":
            return target == rule_value
        if op == "in":
            return target in split_csv(rule_value)
        if op == "is_true":
            return target is True
        if op == "is_false":
            return target is False
        if op in ("gte", "lte"):
            if target is None:
                return False
            if trait in ("wants_size",):
                left = norm_size(target)
                right = norm_size(rule_value)
            elif trait in ("wants_affection", "wants_fluffy"):
                left = 1 if target is True else 0 if target is False else None
                right = 1 if rule_value in (True, "true", "True") else 0 if rule_value in (False, "false", "False") else None
            else:
                left = norm_ord(target) if ordinal_value_ok(target) else target
                right = norm_ord(rule_value) if ordinal_value_ok(rule_value) else rule_value
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        return False

    def cat_matches(rule, breed):
        attr = rule.get("cat_attribute")
        op = rule.get("cat_op")
        target = breed.get(attr)
        rule_value = rule.get("cat_value")

        if op == "eq":
            return target == rule_value
        if op == "in":
            return target in split_csv(rule_value)
        if op == "is_true":
            return target is True
        if op == "is_false":
            return target is False
        if op in ("gte", "lte"):
            if target is None:
                return False
            left = norm_ord(target) if ordinal_value_ok(target) else target
            right = norm_ord(rule_value) if ordinal_value_ok(rule_value) else rule_value
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        return False

    def rule_is_supported(rule):
        kind = rule.get("kind")
        trait = rule.get("trait")
        trait_op = rule.get("trait_op")
        cat_attribute = rule.get("cat_attribute")
        cat_op = rule.get("cat_op")
        trait_value = rule.get("trait_value")
        cat_value = rule.get("cat_value")

        if kind not in valid_kinds:
            return False
        if trait_op not in valid_trait_ops:
            return False
        if cat_attribute not in valid_cat_attributes:
            return False
        if cat_op not in valid_cat_ops:
            return False
        if trait_op in ("gte", "lte") and trait in ("wants_size",) and trait_value not in size_order:
            return False
        if trait_op in ("gte", "lte") and trait not in ("wants_size",) and trait not in ("wants_affection", "wants_fluffy"):
            if trait_value not in ordinal_order:
                return False
        if cat_op in ("gte", "lte") and cat_attribute == "size" and cat_value not in size_order:
            return False
        if cat_op in ("gte", "lte") and cat_attribute != "size" and cat_value not in ordinal_order:
            return False
        return True

    def soft_predicates_from_tags(tags):
        predicates = []
        for tag in tags or []:
            if tag == "avoid_needy":
                predicates.append(("sociability", "gte", "high"))
            elif tag == "avoid_high_energy":
                predicates.append(("energy", "gte", "high"))
        return predicates

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

        soft_penalty = 0
        seen_soft_predicates = set()

        for rule in rules or []:
            if rule.get("kind") != "discourage":
                continue
            if not profile_matches(rule):
                continue
            if not cat_matches(rule, breed):
                continue
            predicate = (rule.get("cat_attribute"), rule.get("cat_op"), rule.get("cat_value"))
            if predicate not in seen_soft_predicates:
                seen_soft_predicates.add(predicate)
                soft_penalty += 1

        for predicate in soft_predicates_from_tags(oracle_tags):
            attr, op, value = predicate
            target = breed.get(attr)
            matched = False
            if op == "gte":
                left = norm_ord(target) if ordinal_value_ok(target) else target
                right = norm_ord(value) if ordinal_value_ok(value) else value
                matched = left is not None and right is not None and left >= right
            elif op == "lte":
                left = norm_ord(target) if ordinal_value_ok(target) else target
                right = norm_ord(value) if ordinal_value_ok(value) else value
                matched = left is not None and right is not None and left <= right
            elif op == "eq":
                matched = target == value
            elif op == "in":
                matched = target in split_csv(value)
            elif op == "is_true":
                matched = target is True
            elif op == "is_false":
                matched = target is False
            if matched and predicate not in seen_soft_predicates:
                seen_soft_predicates.add(predicate)
                soft_penalty += 1

        score -= soft_penalty
        return score

    allergies = profile.get("allergies")
    if allergies is None:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "Allergy status is missing, so the safety input is unresolved and needs human clarification."
        }
    if isinstance(allergies, str):
        allergies_value = allergies.strip().lower()
    else:
        allergies_value = allergies
    if allergies_value not in valid_allergies:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "Allergy status is unknown or outside the supported set, so the safety input is unresolved and needs human clarification."
        }

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is no candidate to evaluate."
        }

    applicable_invalid_rule_ids = []
    for rule in rules or []:
        if profile_matches(rule):
            if not rule_is_supported(rule):
                rule_id = rule.get("id")
                if rule_id is not None and rule_id not in applicable_invalid_rule_ids:
                    applicable_invalid_rule_ids.append(rule_id)

    if applicable_invalid_rule_ids:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": applicable_invalid_rule_ids,
            "rationale": "An applicable policy row uses unsupported or malformed rule language, so the policy source must be repaired before recommendation."
        }

    applicable_forbid_ids = []
    filtered = []
    for breed in breeds:
        name = breed.get("name")
        if name is None:
            continue

        violated = False
        for rule in rules or []:
            if rule.get("kind") != "forbid":
                continue
            if not profile_matches(rule):
                continue
            if cat_matches(rule, breed):
                violated = True
                rule_id = rule.get("id")
                if rule_id is not None and rule_id not in applicable_forbid_ids:
                    applicable_forbid_ids.append(rule_id)
                break

        if not violated:
            filtered.append(breed)

    if not filtered:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": applicable_forbid_ids,
            "rationale": "All supplied breeds were removed by applicable hard rules, so no safe recommendation remains."
        }

    ranked = []
    for breed in filtered:
        name = breed.get("name")
        if name is None:
            continue
        ranked.append((score_breed(breed), name, breed))

    if not ranked:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": applicable_forbid_ids,
            "rationale": "No breed names were available to rank after applying hard rules."
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
    if any(r.get("kind") == "discourage" for r in (rules or [])) or (oracle_tags or []):
        rationale_parts.append("soft discouragements were applied during ranking")
    if applicable_forbid_ids:
        rationale_parts.append("hard rules applied")

    return {
        "operation": "recommend",
        "breed": chosen_name,
        "cited_rules": applicable_forbid_ids,
        "rationale": "; ".join(rationale_parts) + "."
    }
