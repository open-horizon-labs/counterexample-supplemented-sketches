def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic CatSynth recommendation strategy.

    Behavior:
    - Apply promoted hard rules first.
    - Forbid rules remove breeds that match the rule's cat predicate when the
      profile matches the rule's trait trigger.
    - If hard rules eliminate every breed, abstain and cite the applicable hard
      rule IDs.
    - If breeds is empty, escalate because there is no supplied catalog to
      evaluate.
    - Then rank any remaining breeds by explicit owner preferences.
    - Never inspect scenario_id.
    - Do not use oracle_tags for selection.
    """

    size_order = {"small": 0, "medium": 1, "large": 2}
    ordinal_order = {"low": 0, "moderate": 1, "high": 2}

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
            left = norm_ord(target) if target in ordinal_order else target
            right = norm_ord(rule_value) if rule_value in ordinal_order else rule_value
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
            left = norm_ord(target) if target in ordinal_order else target
            right = norm_ord(rule_value) if rule_value in ordinal_order else rule_value
            if left is None or right is None:
                return False
            if op == "gte":
                return left >= right
            return left <= right
        return False

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

        return score

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is no candidate to recommend."
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
    if applicable_forbid_ids:
        rationale_parts.append("hard rules applied")

    return {
        "operation": "recommend",
        "breed": chosen_name,
        "cited_rules": applicable_forbid_ids,
        "rationale": "; ".join(rationale_parts) + "."
    }
