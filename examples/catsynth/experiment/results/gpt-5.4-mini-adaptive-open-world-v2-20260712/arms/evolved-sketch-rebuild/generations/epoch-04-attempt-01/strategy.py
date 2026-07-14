"""Deterministic cat recommendation strategy.

Public entry point:
    recommend(profile, breeds, rules, oracle_tags)

The implementation follows the sketch policy:
- escalate when the catalog is empty
- apply hard forbid rules as filters
- abstain when hard rules eliminate every candidate
- otherwise rank remaining breeds by explicit preferences and a small
  controlled oracle tag penalty
- keep deterministic tie-breaking by breed name
"""


def recommend(profile, breeds, rules, oracle_tags):
    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breed catalog was supplied, so the case needs escalation.",
        }

    oracle_tags = oracle_tags or []
    rules = rules or []

    hard_rule_ids = []
    candidates = []

    for breed in breeds:
        removed = False
        matched_rule_ids = []
        for rule in rules:
            if not _is_hard_forbid(rule):
                continue
            if _matches_rule(profile, breed, rule):
                removed = True
                matched_rule_ids.append(rule.get("id"))
        if removed:
            hard_rule_ids.extend([rid for rid in matched_rule_ids if rid])
        else:
            candidates.append(breed)

    if not candidates:
        return {
            "operation": "abstain",
            "breed": None,
            "cited_rules": _dedupe_preserve_order(hard_rule_ids),
            "rationale": "All supplied breeds were removed by hard rules, so no safe recommendation remains.",
        }

    best_breed = None
    best_score = None

    for breed in candidates:
        score = _score_breed(profile, breed, oracle_tags)
        key = (score, _breed_name(breed))
        if best_score is None or key > best_score:
            best_score = key
            best_breed = breed

    cited_rules = []
    rationale_parts = ["Selected the highest-scoring remaining breed after hard-rule filtering."]
    if "avoid_needy" in set(oracle_tags or []):
        rationale_parts.append("Applied a small soft penalty for needy-seeming breeds.")

    return {
        "operation": "recommend",
        "breed": _breed_name(best_breed),
        "cited_rules": cited_rules,
        "rationale": " ".join(rationale_parts),
    }


def _is_hard_forbid(rule):
    return (rule or {}).get("kind") == "forbid"


def _matches_rule(profile, breed, rule):
    return _matches_trait(profile, rule) and _matches_cat(breed, rule)


def _matches_trait(profile, rule):
    trait = (rule or {}).get("trait")
    op = (rule or {}).get("trait_op")
    value = (rule or {}).get("trait_value")
    actual = (profile or {}).get(trait)
    return _compare(actual, op, value, trait_is_profile=True)


def _matches_cat(breed, rule):
    attr = (rule or {}).get("cat_attribute")
    op = (rule or {}).get("cat_op")
    value = (rule or {}).get("cat_value")
    actual = (breed or {}).get(attr)
    return _compare(actual, op, value, trait_is_profile=False)


def _compare(actual, op, expected, trait_is_profile):
    if op == "eq":
        return str(actual) == str(expected)
    if op == "in":
        actual_values = _split_csv(actual)
        expected_values = _split_csv(expected)
        if not actual_values or not expected_values:
            return False
        return any(v in expected_values for v in actual_values)
    if op == "is_true":
        return bool(actual) is True
    if op == "is_false":
        return bool(actual) is False
    if op in ("gte", "lte"):
        actual_rank = _ordinal_rank(actual)
        expected_rank = _ordinal_rank(expected)
        if actual_rank is None or expected_rank is None:
            return False
        return actual_rank >= expected_rank if op == "gte" else actual_rank <= expected_rank
    return False


def _score_breed(profile, breed, oracle_tags):
    score = 0

    wanted_size = (profile or {}).get("wants_size")
    if wanted_size:
        score += max(0, 2 - abs(_size_rank(_breed_size(breed)) - _size_rank(wanted_size)))

    if (profile or {}).get("wants_affection"):
        score += _ordinal_rank(_breed_field(breed, "affection")) or 0
        score += 2 - (_ordinal_rank(_breed_field(breed, "energy")) or 0)

    if (profile or {}).get("wants_fluffy"):
        score += 2 if bool(_breed_field(breed, "fluffy")) else 0

    if "avoid_needy" in set(oracle_tags or []):
        if (_ordinal_rank(_breed_field(breed, "sociability")) or 0) >= 2:
            score -= 1

    return score


def _breed_name(breed):
    return (breed or {}).get("name") or ""


def _breed_size(breed):
    return _breed_field(breed, "size")


def _breed_field(breed, field):
    return (breed or {}).get(field)


def _ordinal_rank(value):
    mapping = {"low": 0, "moderate": 1, "high": 2}
    return mapping.get(value)


def _size_rank(value):
    mapping = {"small": 0, "medium": 1, "large": 2}
    return mapping.get(value)


def _split_csv(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        values = value
    else:
        values = str(value).split(",")
    return [item.strip() for item in values if str(item).strip()]


def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
