def recommend(profile, breeds, rules, oracle_tags):
    levels = {"low": 0, "moderate": 1, "high": 2}
    sizes = {"small": 0, "medium": 1, "large": 2}

    def norm(v):
        return v.strip().lower() if isinstance(v, str) else v

    def parse_csv_set(value):
        if value is None:
            return set()
        if not isinstance(value, str):
            value = str(value)
        return {part.strip().lower() for part in value.split(",") if part.strip()}

    def profile_value_matches(trait_op, trait_value, actual):
        actual = norm(actual)
        op = norm(trait_op)
        if op == "eq":
            return actual == norm(trait_value)
        if op == "in":
            return actual in parse_csv_set(trait_value)
        if op == "is_true":
            return actual is True or actual == "true"
        if op == "is_false":
            return actual is False or actual == "false"
        return False

    def cat_matches(cat_op, cat_value, cat_actual):
        op = norm(cat_op)
        if op == "is_true":
            return bool(cat_actual) is True
        if op == "is_false":
            return bool(cat_actual) is False
        if op in ("eq", "gte", "lte", "in"):
            if isinstance(cat_actual, bool):
                actual_rank = 1 if cat_actual else 0
            else:
                actual_rank = levels.get(norm(cat_actual), sizes.get(norm(cat_actual)))
            if op == "eq":
                return norm(cat_actual) == norm(cat_value)
            if op == "in":
                return norm(cat_actual) in parse_csv_set(cat_value)
            if actual_rank is None:
                return False
            target_rank = levels.get(norm(cat_value), sizes.get(norm(cat_value)))
            if target_rank is None:
                return False
            if op == "gte":
                return actual_rank >= target_rank
            if op == "lte":
                return actual_rank <= target_rank
        return False

    # Safety gate: unknown allergy status requires escalation.
    allergies = norm(profile.get("allergies"))
    if allergies not in {"none", "mild", "severe"}:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "Allergy status is missing or unsupported, so safety cannot be resolved deterministically."
        }

    # Hard rule filtering.
    hard_hits = []
    candidates = []
    for breed in breeds or []:
        violated = []
        for rule in rules or []:
            if norm(rule.get("kind")) != "forbid":
                continue
            if not profile_value_matches(rule.get("trait_op"), rule.get("trait_value"), profile.get(rule.get("trait"))):
                continue
            if cat_matches(rule.get("cat_op"), rule.get("cat_value"), breed.get(rule.get("cat_attribute"))):
                violated.append(rule.get("id"))
        if violated:
            for rid in violated:
                if rid not in hard_hits:
                    hard_hits.append(rid)
        else:
            candidates.append(breed)

    if not candidates:
        if hard_hits:
            return {
                "operation": "abstain",
                "breed": None,
                "cited_rules": hard_hits,
                "rationale": "No breed survives the applicable hard rules."
            }
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No candidates were supplied."
        }

    # Soft signals: structured discourage rules and controlled narrative tags.
    active_soft_predicates = {}
    for rule in rules or []:
        if norm(rule.get("kind")) != "discourage":
            continue
        if profile_value_matches(rule.get("trait_op"), rule.get("trait_value"), profile.get(rule.get("trait"))):
            key = (norm(rule.get("cat_attribute")), norm(rule.get("cat_op")), norm(rule.get("cat_value")))
            active_soft_predicates[key] = rule

    tags = set(norm(tag) for tag in (oracle_tags or []))
    if "avoid_needy" in tags:
        active_soft_predicates[("sociability", "gte", "high")] = None
    if "avoid_high_energy" in tags:
        active_soft_predicates[("energy", "gte", "high")] = None

    def rank_value(v):
        v = norm(v)
        return levels.get(v, sizes.get(v, 0))

    best = None
    best_score = None
    for breed in candidates:
        score = 0
        wanted_size = norm(profile.get("wants_size"))
        if wanted_size in sizes:
            score += max(0, 2 - abs(rank_value(breed.get("size")) - sizes[wanted_size]))
        if profile.get("wants_affection"):
            score += rank_value(breed.get("affection")) + (2 - rank_value(breed.get("energy")))
        if profile.get("wants_fluffy"):
            score += 2 if breed.get("fluffy") else 0
        for (attr, op, value) in active_soft_predicates.keys():
            if cat_matches(op, value, breed.get(attr)):
                score -= 1
        key = (score, breed.get("name", ""))
        if best is None or key > best_score:
            best = breed
            best_score = key

    return {
        "operation": "recommend",
        "breed": best.get("name") if best else None,
        "cited_rules": hard_hits,
        "rationale": "Recommended the highest-scoring candidate after hard-rule filtering and soft-penalty application."
    }
