def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic cat recommendation strategy.

    Public contract:
        recommend(profile, breeds, rules, oracle_tags) -> dict

    Returned dict keys:
        operation: recommend | abstain | escalate
        breed: breed name or None
        cited_rules: list[str]
        rationale: str
    """

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    def _truthy(v):
        return v is True or v == 1 or v == "true" or v == "True"

    def _ordinal(v, kind):
        if kind == "level":
            mapping = {"low": 0, "moderate": 1, "high": 2}
        else:
            mapping = {"small": 0, "medium": 1, "large": 2}
        return mapping.get(v)

    def _split_csv(s):
        if s is None:
            return []
        if not isinstance(s, str):
            s = str(s)
        return [part.strip() for part in s.split(",") if part.strip()]

    def _matches_rule_trigger(rule, profile_obj):
        trait = _get(rule, "trait")
        op = _get(rule, "trait_op")
        value = _get(rule, "trait_value")
        prof_val = _get(profile_obj, trait)

        if op == "eq":
            return prof_val == value
        if op == "in":
            return prof_val in _split_csv(value)
        if op == "is_true":
            return _truthy(prof_val)
        if op == "is_false":
            return not _truthy(prof_val)
        if op in ("gte", "lte"):
            if trait == "wants_size":
                left = _ordinal(prof_val, "size")
                right = _ordinal(value, "size")
            else:
                left = _ordinal(prof_val, "level")
                right = _ordinal(value, "level")
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    def _matches_cat_predicate(rule, breed_obj):
        attr = _get(rule, "cat_attribute")
        op = _get(rule, "cat_op")
        value = _get(rule, "cat_value")
        breed_val = _get(breed_obj, attr)

        if op == "eq":
            return breed_val == value
        if op == "in":
            return breed_val in _split_csv(value)
        if op == "is_true":
            return _truthy(breed_val)
        if op == "is_false":
            return not _truthy(breed_val)
        if op in ("gte", "lte"):
            if attr == "size":
                left = _ordinal(breed_val, "size")
                right = _ordinal(value, "size")
            else:
                left = _ordinal(breed_val, "level")
                right = _ordinal(value, "level")
            if left is None or right is None:
                return False
            return left >= right if op == "gte" else left <= right
        return False

    def _semantic_predicate(rule):
        return (
            _get(rule, "cat_attribute"),
            _get(rule, "cat_op"),
            _get(rule, "cat_value"),
        )

    profile_obj = profile or {}
    breed_list = list(breeds or [])
    rule_list = list(rules or [])
    tags = list(oracle_tags or [])

    if not breed_list:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were supplied, so there is no catalog to evaluate.",
        }

    hard_hits = []
    filtered = []
    for breed in breed_list:
        removed = False
        for rule in rule_list:
            if _get(rule, "kind") == "forbid" and _matches_rule_trigger(rule, profile_obj) and _matches_cat_predicate(rule, breed):
                hard_hits.append(_get(rule, "id"))
                removed = True
        if not removed:
            filtered.append(breed)

    hard_hit_ids = []
    seen_hard = set()
    for rid in hard_hits:
        if rid is not None and rid not in seen_hard:
            seen_hard.add(rid)
            hard_hit_ids.append(rid)

    if not filtered:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": hard_hit_ids,
            "rationale": "Hard rules removed every supplied breed, so no safe recommendation remains.",
        }

    soft_predicates = []
    soft_seen = set()

    def _add_soft_predicate(pred):
        if pred not in soft_seen:
            soft_seen.add(pred)
            soft_predicates.append(pred)

    for rule in rule_list:
        if _get(rule, "kind") == "discourage" and _matches_rule_trigger(rule, profile_obj):
            _add_soft_predicate(_semantic_predicate(rule))

    for tag in tags:
        if tag == "avoid_needy":
            _add_soft_predicate(("sociability", "gte", "high"))
        elif tag == "avoid_high_energy":
            _add_soft_predicate(("energy", "gte", "high"))

    def _breed_score(breed):
        score = 0
        wanted_size = _get(profile_obj, "wants_size")
        if wanted_size is not None:
            bs = _ordinal(_get(breed, "size"), "size")
            ws = _ordinal(wanted_size, "size")
            if bs is not None and ws is not None:
                score += max(0, 2 - abs(bs - ws))

        if _truthy(_get(profile_obj, "wants_affection")):
            aff = _ordinal(_get(breed, "affection"), "level")
            energy = _ordinal(_get(breed, "energy"), "level")
            if aff is not None:
                score += aff
            if energy is not None:
                score += 2 - energy

        if _truthy(_get(profile_obj, "wants_fluffy")):
            score += 2 if _truthy(_get(breed, "fluffy")) else 0

        for attr, op, val in soft_predicates:
            bval = _get(breed, attr)
            matched = False
            if op == "eq":
                matched = bval == val
            elif op == "in":
                matched = bval in _split_csv(val)
            elif op == "is_true":
                matched = _truthy(bval)
            elif op == "is_false":
                matched = not _truthy(bval)
            elif op in ("gte", "lte"):
                left = _ordinal(bval, "level")
                right = _ordinal(val, "level")
                if left is not None and right is not None:
                    matched = left >= right if op == "gte" else left <= right
            if matched:
                score -= 1
        return score

    ranked = sorted(
        ((-_breed_score(b), _get(b, "name"), b) for b in filtered),
        key=lambda item: (item[0], item[1]),
    )
    _, best_name, _best_breed = ranked[0]

    rationale = "Selected the highest-scoring remaining breed after applying hard filters and preference-based ranking."
    if soft_predicates:
        rationale = "Selected the highest-scoring remaining breed after applying hard filters and soft discouragements."

    return {
        "operation": "recommend",
        "breed": best_name,
        "cited_rules": hard_hit_ids,
        "rationale": rationale,
    }
