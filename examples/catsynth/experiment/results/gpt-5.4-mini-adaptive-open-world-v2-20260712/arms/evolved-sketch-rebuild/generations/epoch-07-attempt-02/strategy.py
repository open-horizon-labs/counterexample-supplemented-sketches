def recommend(profile, breeds, rules, oracle_tags):
    def get(obj, key, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def norm_text(value):
        if value is None:
            return ""
        return str(value).strip().lower()

    def split_csv(value):
        text = norm_text(value)
        if not text:
            return []
        return [part.strip().lower() for part in text.split(",") if part.strip()]

    def as_bool(value):
        if isinstance(value, bool):
            return value
        text = norm_text(value)
        if text in ("true", "1", "yes", "y"):
            return True
        if text in ("false", "0", "no", "n"):
            return False
        return None

    def ordinal_level(value, kind):
        text = norm_text(value)
        if kind == "size":
            return {"small": 0, "medium": 1, "large": 2}.get(text)
        return {"low": 0, "moderate": 1, "high": 2}.get(text)

    def matches_profile(rule):
        trait = norm_text(get(rule, "trait"))
        op = norm_text(get(rule, "trait_op"))
        value = get(rule, "trait_value")
        profile_value = get(profile, trait)

        if op == "eq":
            return norm_text(profile_value) == norm_text(value)
        if op == "in":
            choices = split_csv(value)
            return norm_text(profile_value) in choices
        if op == "is_true":
            return as_bool(profile_value) is True
        if op == "is_false":
            return as_bool(profile_value) is False
        if op in ("gte", "lte"):
            left = ordinal_level(profile_value, trait if trait == "size" else "level")
            right = ordinal_level(value, trait if trait == "size" else "level")
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    def matches_breed(rule, breed):
        attr = norm_text(get(rule, "cat_attribute"))
        op = norm_text(get(rule, "cat_op"))
        value = get(rule, "cat_value")
        breed_value = get(breed, attr)

        if op == "eq":
            return norm_text(breed_value) == norm_text(value)
        if op == "in":
            choices = split_csv(value)
            return norm_text(breed_value) in choices
        if op == "is_true":
            return as_bool(breed_value) is True
        if op == "is_false":
            return as_bool(breed_value) is False
        if op in ("gte", "lte"):
            left = ordinal_level(breed_value, attr if attr == "size" else "level")
            right = ordinal_level(value, attr if attr == "size" else "level")
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    def soft_predicate(rule):
        return (
            norm_text(get(rule, "cat_attribute")),
            norm_text(get(rule, "cat_op")),
            norm_text(get(rule, "cat_value")),
        )

    def rule_applies(rule):
        return norm_text(get(rule, "kind")) == "forbid" and matches_profile(rule)

    allergies = norm_text(get(profile, "allergies"))
    if allergies not in ("none", "mild", "severe"):
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "Allergy safety input is unresolved.",
        }

    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breed catalog was supplied.",
        }

    survivors = []
    hard_cited = []
    seen_hard = set()

    for breed in breeds:
        blocked = False
        for rule in rules or []:
            if rule_applies(rule) and matches_breed(rule, breed):
                blocked = True
                rid = get(rule, "id")
                if rid is not None and rid not in seen_hard:
                    seen_hard.add(rid)
                    hard_cited.append(rid)
        if not blocked:
            survivors.append(breed)

    if not survivors:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": hard_cited,
            "rationale": "Hard rules eliminate every supplied breed.",
        }

    wants_size = ordinal_level(get(profile, "wants_size"), "size")
    wants_affection = as_bool(get(profile, "wants_affection")) is True
    wants_fluffy = as_bool(get(profile, "wants_fluffy")) is True

    soft_sources = []
    seen_soft = set()

    for rule in rules or []:
        if norm_text(get(rule, "kind")) == "discourage" and matches_profile(rule):
            pred = soft_predicate(rule)
            if pred not in seen_soft:
                seen_soft.add(pred)
                soft_sources.append((pred, 1, norm_text(get(rule, "id"))))

    for tag in oracle_tags or []:
        tag_text = norm_text(tag)
        if tag_text == "avoid_needy":
            pred = ("sociability", "gte", "high")
            if pred not in seen_soft:
                seen_soft.add(pred)
                soft_sources.append((pred, 1, None))
        elif tag_text == "avoid_high_energy":
            pred = ("energy", "gte", "high")
            if pred not in seen_soft:
                seen_soft.add(pred)
                soft_sources.append((pred, 1, None))

    best = None
    best_score = None
    best_name = None

    for breed in survivors:
        score = 0
        if wants_size is not None:
            breed_size = ordinal_level(get(breed, "size"), "size")
            if breed_size is not None:
                score += max(0, 2 - abs(breed_size - wants_size))
        if wants_affection:
            affection = ordinal_level(get(breed, "affection"), "level")
            energy = ordinal_level(get(breed, "energy"), "level")
            if affection is not None:
                score += affection
            if energy is not None:
                score += 2 - energy
        if wants_fluffy and as_bool(get(breed, "fluffy")) is True:
            score += 2

        for pred, penalty, rid in soft_sources:
            attr, op, value = pred
            candidate = get(breed, attr)
            matched = False
            if op == "eq":
                matched = norm_text(candidate) == value
            elif op == "in":
                matched = norm_text(candidate) in split_csv(value)
            elif op == "is_true":
                matched = as_bool(candidate) is True
            elif op == "is_false":
                matched = as_bool(candidate) is False
            elif op in ("gte", "lte"):
                left = ordinal_level(candidate, attr if attr == "size" else "level")
                right = ordinal_level(value, attr if attr == "size" else "level")
                if left is not None and right is not None:
                    matched = left >= right if op == "gte" else left <= right
            if matched:
                score -= penalty

        name = norm_text(get(breed, "name"))
        if best is None or score > best_score or (score == best_score and name < best_name):
            best = breed
            best_score = score
            best_name = name

    rationale_parts = ["Selected the highest-scoring breed after filtering."]
    if hard_cited:
        rationale_parts.append("Hard rules removed some breeds.")
    return {
        "operation": "recommend",
        "breed": get(best, "name"),
        "cited_rules": hard_cited,
        "rationale": " ".join(rationale_parts),
    }
