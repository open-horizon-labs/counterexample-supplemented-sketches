"""Deterministic cat recommendation strategy for CatSynth.

Public entry point:
    recommend(profile, breeds, rules, oracle_tags)

The implementation is defensive and data-driven:
- validates safety inputs and rule schema
- applies hard forbid rules before ranking
- uses stable ordinal encodings for ranking
- deduplicates soft penalties by semantic predicate
- never branches on scenario_id or hard-coded fixture names
"""

LEVELS = {"low": 0, "moderate": 1, "high": 2}
SIZES = {"small": 0, "medium": 1, "large": 2}
ALLOWED_ALLERGIES = {"none", "mild", "severe"}
ALLOWED_KINDS = {"forbid", "discourage"}
ALLOWED_TRAIT_OPS = {"eq", "in", "is_true", "is_false"}
ALLOWED_CAT_ATTRS = {
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
ALLOWED_CAT_OPS = {"eq", "in", "is_true", "is_false", "gte", "lte"}


def recommend(profile, breeds, rules, oracle_tags):
    profile = profile or {}
    breeds = list(breeds or [])
    rules = list(rules or [])
    oracle_tags = list(oracle_tags or [])

    allergies = _norm(profile.get("allergies"))
    if not allergies or allergies not in ALLOWED_ALLERGIES:
        return _result("escalate", None, [], "profile.allergies is missing or unsupported")

    if not breeds:
        return _result("escalate", None, [], "no breeds were supplied")

    validation = _validate_applicable_rules(profile, rules)
    if validation is not None:
        rid, reason = validation
        return _result("escalate", None, [rid], reason)

    hard_matches = []
    soft_rules = []
    for rule in rules:
        if not _rule_applies_to_profile(profile, rule):
            continue
        if _kind(rule) == "forbid":
            hard_matches.append(rule)
        elif _kind(rule) == "discourage":
            soft_rules.append(rule)

    remaining = []
    cited = []
    for breed in breeds:
        breed_removed = False
        for rule in hard_matches:
            if _breed_matches_rule_predicate(breed, rule):
                breed_removed = True
                cited.append(_rule_id(rule))
        if not breed_removed:
            remaining.append(breed)

    cited = _dedupe_preserve_order(cited)
    if not remaining:
        return _result("abstain", None, cited, "all candidates were removed by hard rules")

    want_size = _ordinal_value(profile.get("wants_size"), SIZES)
    wants_affection = _truthy(profile.get("wants_affection"))
    wants_fluffy = _truthy(profile.get("wants_fluffy"))

    narrative_tags = _normalize_oracle_tags(oracle_tags)
    soft_predicates = []
    for rule in soft_rules:
        soft_predicates.append(_predicate_key(rule))
    for tag in narrative_tags:
        pred = _tag_to_predicate(tag)
        if pred is not None:
            soft_predicates.append(pred)

    soft_predicates = _dedupe_preserve_order(soft_predicates)

    scored = []
    for breed in remaining:
        score = 0
        if want_size is not None:
            bs = _ordinal_value(breed.get("size"), SIZES)
            if bs is not None:
                score += max(0, 2 - abs(bs - want_size))
        if wants_affection:
            aff = _ordinal_value(breed.get("affection"), LEVELS)
            energy = _ordinal_value(breed.get("energy"), LEVELS)
            if aff is not None:
                score += aff
            if energy is not None:
                score += (2 - energy)
        if wants_fluffy and _truthy(breed.get("fluffy")):
            score += 2

        for pred in soft_predicates:
            if _breed_matches_predicate(breed, pred):
                score -= 1

        scored.append((score, _breed_name(breed), breed))

    scored.sort(key=lambda t: (-t[0], t[1]))
    best_score, best_name, best_breed = scored[0]

    rationale_parts = []
    if cited:
        rationale_parts.append("hard rules removed some candidates")
    if soft_predicates:
        rationale_parts.append("soft preferences and narrative tags were applied")
    if not rationale_parts:
        rationale_parts.append("selected the highest-scoring remaining breed")

    return _result("recommend", best_name, cited, "; ".join(rationale_parts))


def _result(operation, breed, cited_rules, rationale):
    return {
        "operation": operation,
        "breed": breed,
        "cited_rules": cited_rules,
        "rationale": str(rationale),
    }


def _validate_applicable_rules(profile, rules):
    for rule in rules:
        if not _rule_applies_to_profile(profile, rule):
            continue
        kind = _kind(rule)
        trait_op = _rule_get(rule, "trait_op")
        cat_attr = _rule_get(rule, "cat_attribute")
        cat_op = _rule_get(rule, "cat_op")
        if kind not in ALLOWED_KINDS:
            return _rule_id(rule), f"unsupported rule kind: {kind}"
        if trait_op not in ALLOWED_TRAIT_OPS:
            return _rule_id(rule), f"unsupported trait operator: {trait_op}"
        if cat_attr not in ALLOWED_CAT_ATTRS:
            return _rule_id(rule), f"unsupported cat attribute: {cat_attr}"
        if cat_op not in ALLOWED_CAT_OPS:
            return _rule_id(rule), f"unsupported cat operator: {cat_op}"
        if cat_op in {"gte", "lte"}:
            cat_value = _rule_get(rule, "cat_value")
            if cat_value not in LEVELS and cat_value not in SIZES:
                return _rule_id(rule), f"unsupported ordinal value: {cat_value}"
    return None


def _is_forbidden(breed, hard_rules):
    for rule in hard_rules:
        if _breed_matches_rule_predicate(breed, rule):
            return True
    return False


def _rule_applies_to_profile(profile, rule):
    trait = _rule_get(rule, "trait")
    trait_op = _rule_get(rule, "trait_op")
    trait_value = _rule_get(rule, "trait_value")
    actual = profile.get(trait)
    if trait_op == "eq":
        return _norm(actual) == _norm(trait_value)
    if trait_op == "in":
        return _norm(actual) in _split_csv(trait_value)
    if trait_op == "is_true":
        return _truthy(actual)
    if trait_op == "is_false":
        return not _truthy(actual)
    return False


def _breed_matches_rule_predicate(breed, rule):
    return _breed_matches_predicate(breed, _predicate_key(rule))


def _breed_matches_predicate(breed, pred):
    attr, op, value = pred
    actual = breed.get(attr)
    if op == "is_true":
        return _truthy(actual)
    if op == "is_false":
        return not _truthy(actual)
    if op == "eq":
        return _compare_eq(actual, value)
    if op == "in":
        return _norm(actual) in _split_csv(value)
    if op in {"gte", "lte"}:
        scale = LEVELS if attr in {"energy", "shedding", "grooming", "sociability", "vocal", "affection"} else SIZES
        av = _ordinal_value(actual, scale)
        cv = _ordinal_value(value, scale)
        if av is None or cv is None:
            return False
        return av >= cv if op == "gte" else av <= cv
    return False


def _predicate_key(rule):
    return (_rule_get(rule, "cat_attribute"), _rule_get(rule, "cat_op"), _rule_get(rule, "cat_value"))


def _tag_to_predicate(tag):
    if tag == "avoid_needy":
        return ("sociability", "gte", "high")
    if tag == "avoid_high_energy":
        return ("energy", "gte", "high")
    return None


def _normalize_oracle_tags(tags):
    out = []
    for tag in tags:
        t = _norm(tag)
        if t in {"avoid_needy", "avoid_high_energy"}:
            out.append(t)
    return out


def _rule_id(rule):
    return str(_rule_get(rule, "id") or "")


def _kind(rule):
    return _norm(_rule_get(rule, "kind"))


def _rule_get(rule, key):
    if isinstance(rule, dict):
        return rule.get(key)
    return None


def _breed_name(breed):
    return str(breed.get("name") or "")


def _truthy(value):
    if isinstance(value, bool):
        return value
    return _norm(value) in {"true", "1", "yes", "y"}


def _norm(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _split_csv(value):
    s = _norm(value)
    if not s:
        return set()
    return {part.strip() for part in s.split(",") if part.strip()}


def _ordinal_value(value, mapping):
    v = _norm(value)
    if v in mapping:
        return mapping[v]
    return None


def _compare_eq(actual, expected):
    return _norm(actual) == _norm(expected)


def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
