# CatSynth initial strategy
# Deterministic, no imports, no scenario branching.

_LEVELS = {"low": 0, "moderate": 1, "high": 2}
_SIZES = {"small": 0, "medium": 1, "large": 2}


def _split_csv(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _matches_profile(profile, rule):
    trait = rule.get("trait")
    op = rule.get("trait_op")
    expected = rule.get("trait_value")
    actual = profile.get(trait)

    if op == "eq":
        return actual == expected
    if op == "in":
        values = _split_csv(expected)
        return actual in values
    if op == "is_true":
        return actual is True
    if op == "is_false":
        return actual is False
    return False


def _coerce_ord(value, table):
    if value in table:
        return table[value]
    return None


def _matches_cat(breed, rule):
    attr = rule.get("cat_attribute")
    op = rule.get("cat_op")
    expected = rule.get("cat_value")
    actual = breed.get(attr)

    if op == "eq":
        return actual == expected
    if op == "in":
        values = _split_csv(expected)
        if not values:
            return False
        return str(actual) in values
    if op == "is_true":
        return actual is True
    if op == "is_false":
        return actual is False
    if op in ("gte", "lte"):
        if actual is None:
            return False
        a = _coerce_ord(actual, _LEVELS if attr in ("energy", "shedding", "grooming", "sociability", "vocal", "affection") else _SIZES)
        b = _coerce_ord(expected, _LEVELS if expected in _LEVELS else _SIZES)
        if a is None or b is None:
            return False
        return a >= b if op == "gte" else a <= b
    return False


def _hard_forbid_rule(rule):
    return rule.get("kind") == "forbid"


def _score_breed(profile, breed):
    score = 0

    wanted_size = profile.get("wants_size")
    if wanted_size:
        want = _SIZES.get(wanted_size)
        have = _SIZES.get(breed.get("size"))
        if want is not None and have is not None:
            score += max(0, 2 - abs(have - want))

    if profile.get("wants_affection") is True:
        affection = _LEVELS.get(breed.get("affection"), 0)
        energy = _LEVELS.get(breed.get("energy"), 0)
        score += affection + (2 - energy)

    if profile.get("wants_fluffy") is True and breed.get("fluffy") is True:
        score += 2

    return score


def _append_unique(items, value):
    if value is None:
        return
    if value not in items:
        items.append(value)


def recommend(profile, breeds, rules, oracle_tags):
    if not breeds:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No breeds were provided, so there is nothing to rank.",
        }

    remaining = []
    cited = []
    removed_any = False

    for breed in breeds:
        blocked = []
        for rule in rules or []:
            if not _hard_forbid_rule(rule):
                continue
            if _matches_profile(profile, rule) and _matches_cat(breed, rule):
                _append_unique(blocked, rule.get("id"))
        if blocked:
            removed_any = True
            for rule_id in blocked:
                _append_unique(cited, rule_id)
        else:
            remaining.append(breed)

    if not remaining:
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": cited,
            "rationale": "All candidate breeds were removed by hard rules.",
        }

    scored = []
    for breed in remaining:
        scored.append((_score_breed(profile, breed), breed.get("name"), breed))
    scored.sort(key=lambda item: (-item[0], item[1]))

    best = scored[0][2]
    rationale_parts = ["Selected the highest-scoring remaining breed."]
    if removed_any:
        rationale_parts.append("Some breeds were removed by hard rules first.")

    return {
        "operation": "recommend",
        "breed": best.get("name"),
        "cited_rules": cited,
        "rationale": " ".join(rationale_parts),
    }
