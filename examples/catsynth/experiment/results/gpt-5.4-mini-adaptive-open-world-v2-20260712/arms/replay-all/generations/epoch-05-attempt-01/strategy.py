def recommend(profile, breeds, rules, oracle_tags):
    """Deterministic CatSynth recommender.

    Contract:
      - Return dict with operation, breed, cited_rules, rationale.
      - operation is recommend, abstain, or escalate.
      - Prefer explicit owner preferences, then apply hard forbids, then soft discourages.
      - Never inspect scenario_id or use named fixtures.
    """

    LEVEL = {"low": 0, "moderate": 1, "high": 2}
    SIZE = {"small": 0, "medium": 1, "large": 2}

    def parse_set(value):
        if value is None:
            return set()
        if isinstance(value, str):
            return {part.strip() for part in value.split(",") if part.strip()}
        return set(value)

    def get(d, key, default=None):
        return d.get(key, default) if isinstance(d, dict) else default

    def is_truthy(v):
        return bool(v) is True

    def match_profile_rule(rule, prof):
        trait = get(rule, "trait")
        op = get(rule, "trait_op")
        value = get(rule, "trait_value", "")
        pval = get(prof, trait)

        if op == "eq":
            return pval == value
        if op == "in":
            return pval in parse_set(value)
        if op == "is_true":
            return is_truthy(pval)
        if op == "is_false":
            return not is_truthy(pval)
        return False

    def match_cat_rule(rule, breed):
        attr = get(rule, "cat_attribute")
        op = get(rule, "cat_op")
        value = get(rule, "cat_value", "")
        bval = get(breed, attr)

        if op == "eq":
            return bval == value
        if op == "in":
            return bval in parse_set(value)
        if op == "is_true":
            return is_truthy(bval)
        if op == "is_false":
            return not is_truthy(bval)
        if op == "gte":
            return LEVEL.get(bval, -1) >= LEVEL.get(value, -1)
        if op == "lte":
            return LEVEL.get(bval, -1) <= LEVEL.get(value, -1)
        return False

    applicable = [rule for rule in (rules or []) if match_profile_rule(rule, profile)]
    hard_rules = [rule for rule in applicable if get(rule, "kind") == "forbid"]
    soft_rules = [rule for rule in applicable if get(rule, "kind") == "discourage"]

    surviving = []
    cited = []
    for breed in (breeds or []):
        violated = [rule for rule in hard_rules if match_cat_rule(rule, breed)]
        if violated:
            cited.extend(get(rule, "id") for rule in violated)
            continue
        score = 0
        wanted_size = get(profile, "wants_size")
        if wanted_size is not None:
            score += max(0, 2 - abs(SIZE.get(get(breed, "size"), -1) - SIZE.get(wanted_size, -1)))
        if get(profile, "wants_affection"):
            score += LEVEL.get(get(breed, "affection"), 0) + (2 - LEVEL.get(get(breed, "energy"), 0))
        if get(profile, "wants_fluffy"):
            score += 2 if get(breed, "fluffy") else 0
        for tag in oracle_tags or []:
            if tag == "avoid_needy" and LEVEL.get(get(breed, "sociability"), 0) >= LEVEL["high"]:
                score -= 1
        for rule in soft_rules:
            if match_cat_rule(rule, breed):
                score -= 1
        surviving.append((score, get(breed, "name"), breed))

    if not surviving:
        if hard_rules:
            # If every candidate was eliminated by hard policy, abstain and cite the applicable hard rules.
            cited_rules = []
            seen = set()
            for rule in hard_rules:
                rid = get(rule, "id")
                if rid and rid not in seen:
                    seen.add(rid)
                    cited_rules.append(rid)
            return {
                "operation": "abstain",
                "breed": None,
                "cited_rules": cited_rules,
                "rationale": "All candidates were removed by applicable hard forbid rules."
            }
        return {
            "operation": "escalate",
            "breed": None,
            "cited_rules": [],
            "rationale": "No candidates were provided or no deterministic preference path was available."
        }

    surviving.sort(key=lambda item: (-item[0], item[1]))
    best = surviving[0][2]

    cited_rules = []
    seen = set()
    for rule in hard_rules:
        rid = get(rule, "id")
        if rid and rid not in seen:
            seen.add(rid)
            cited_rules.append(rid)

    return {
        "operation": "recommend",
        "breed": get(best, "name"),
        "cited_rules": cited_rules,
        "rationale": "Selected the highest-scoring surviving breed after applying hard forbids, soft discourages, and explicit owner preferences."
    }
