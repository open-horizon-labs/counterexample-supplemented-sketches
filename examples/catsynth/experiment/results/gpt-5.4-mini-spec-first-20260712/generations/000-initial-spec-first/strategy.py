def recommend(profile, breeds, rules, oracle_tags):
    def norm_str(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return str(value).strip().lower()
        return str(value).strip().lower()

    def norm_csv_set(value):
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set)):
            parts = []
            for item in value:
                n = norm_str(item)
                if n is not None and n != "":
                    parts.append(n)
            return set(parts)
        text = str(value)
        pieces = text.split(',')
        out = set()
        for piece in pieces:
            n = norm_str(piece)
            if n is not None and n != "":
                out.add(n)
        return out

    def is_blank(value):
        return value is None or (isinstance(value, str) and value.strip() == "")

    def get_profile_value(obj, key):
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            nk = norm_str(key)
            for k, v in obj.items():
                if norm_str(k) == nk:
                    return v
        return None

    def get_breed_attr(breed, attr):
        if not isinstance(breed, dict):
            return None
        candidates = [attr, "breed_" + attr, "cat_" + attr]
        for cand in candidates:
            if cand in breed:
                return breed[cand]
        na = norm_str(attr)
        for k, v in breed.items():
            if norm_str(k) in (na, "breed_" + na, "cat_" + na):
                return v
        return None

    def parse_bool(value):
        if isinstance(value, bool):
            return value
        n = norm_str(value)
        if n in ("true", "yes", "1"):
            return True
        if n in ("false", "no", "0"):
            return False
        return None

    def valid_allergies(value):
        n = norm_str(value)
        return n in ("none", "mild", "severe")

    def ordinal_value(attr_value):
        n = norm_str(attr_value)
        if n == "low":
            return 0
        if n == "moderate":
            return 1
        if n == "high":
            return 2
        return None

    def numeric_or_ordinal(value):
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        n = ordinal_value(value)
        if n is not None:
            return n
        try:
            return float(str(value).strip())
        except Exception:
            return None

    def breed_matches_predicate(breed, attr, op, cmp_value):
        bv = get_breed_attr(breed, attr)
        opn = norm_str(op)
        if opn in ("is_true", "is_false"):
            bb = parse_bool(bv)
            cv = parse_bool(cmp_value)
            if bb is None or cv is None:
                return False
            return bb is cv if opn == "is_true" else bb is not cv
        if opn in ("eq", "neq"):
            left = norm_str(bv)
            right = norm_str(cmp_value)
            if left is None or right is None:
                return False
            return (left == right) if opn == "eq" else (left != right)
        if opn in ("gte", "lte"):
            left = numeric_or_ordinal(bv)
            right = numeric_or_ordinal(cmp_value)
            if left is None or right is None:
                return False
            return (left >= right) if opn == "gte" else (left <= right)
        return None

    def profile_trigger_true(row):
        trait = row.get("trait")
        op = norm_str(row.get("trait_op"))
        val = row.get("trait_value")
        pv = get_profile_value(profile, trait)
        if op == "eq":
            return norm_str(pv) == norm_str(val)
        if op == "in":
            return norm_str(pv) in norm_csv_set(val)
        if op == "is_true":
            return parse_bool(pv) is True
        if op == "is_false":
            return parse_bool(pv) is False
        return None

    def canonical_predicate(row):
        return (norm_str(row.get("cat_attribute")), norm_str(row.get("cat_op")), norm_str(row.get("cat_value")))

    if not isinstance(breeds, list) or len(breeds) == 0:
        return {"operation": "escalate", "breed": None, "cited_rules": [], "rationale": "empty breed catalog"}

    allergies = get_profile_value(profile, "allergies")
    if not valid_allergies(allergies):
        return {"operation": "escalate", "breed": None, "cited_rules": [], "rationale": "uninterpretable allergies"}

    applicable_hard = []
    hard_matched_ids = set()
    surviving = []
    for breed in breeds:
        surviving.append(breed)

    for row in rules or []:
        if not isinstance(row, dict):
            continue
        trigger = profile_trigger_true(row)
        if trigger is None:
            continue
        if trigger is False:
            continue
        kind = norm_str(row.get("kind"))
        attr = row.get("cat_attribute")
        op = row.get("cat_op")
        val = row.get("cat_value")
        rid = row.get("id")
        if kind not in ("forbid", "discourage"):
            return {"operation": "escalate", "breed": None, "cited_rules": [rid] if rid is not None else [], "rationale": "unsupported applicable rule kind"}
        pred_ok = breed_matches_predicate(breeds[0], attr, op, val)
        if pred_ok is None:
            return {"operation": "escalate", "breed": None, "cited_rules": [rid] if rid is not None else [], "rationale": "unsupported applicable breed predicate"}
        if kind == "forbid":
            applicable_hard.append((rid, attr, op, val))

    hard_rule_ids = []
    for rid, attr, op, val in applicable_hard:
        matched = False
        next_survivors = []
        for breed in surviving:
            res = breed_matches_predicate(breed, attr, op, val)
            if res is True:
                matched = True
            else:
                next_survivors.append(breed)
        if matched and rid is not None:
            hard_matched_ids.add(rid)
        surviving = next_survivors
        hard_rule_ids.append(rid)

    if len(surviving) == 0:
        cited = []
        for rid, _, _, _ in applicable_hard:
            if rid is not None and rid not in cited:
                cited.append(rid)
        return {"operation": "abstain", "breed": None, "cited_rules": cited, "rationale": "hard policy removes all candidates"}

    soft_preds = set()
    for row in rules or []:
        if not isinstance(row, dict):
            continue
        trigger = profile_trigger_true(row)
        if trigger is not True:
            continue
        if norm_str(row.get("kind")) != "discourage":
            continue
        soft_preds.add(canonical_predicate(row))

    for tag in oracle_tags or []:
        tn = norm_str(tag)
        if tn == "avoid_needy":
            soft_preds.add(("sociability", "gte", "high"))
        elif tn == "avoid_vocal":
            soft_preds.add(("vocal", "gte", "high"))
        elif tn == "avoid_high_energy":
            soft_preds.add(("energy", "gte", "high"))

    wants_size = numeric_or_ordinal(get_profile_value(profile, "wants_size"))
    wants_affection = parse_bool(get_profile_value(profile, "wants_affection")) is True
    wants_fluffy = parse_bool(get_profile_value(profile, "wants_fluffy")) is True

    scored = []
    for breed in surviving:
        score = 0
        if wants_size is not None:
            bs = numeric_or_ordinal(get_breed_attr(breed, "size"))
            if bs is not None:
                score += max(0, 2 - abs(bs - wants_size))
        if wants_affection:
            aff = numeric_or_ordinal(get_breed_attr(breed, "affection"))
            energy = numeric_or_ordinal(get_breed_attr(breed, "energy"))
            if aff is not None and energy is not None:
                score += aff + (2 - energy)
        if wants_fluffy and parse_bool(get_breed_attr(breed, "fluffy")) is True:
            score += 2
        penalty = 0
        for attr, op, val in soft_preds:
            res = breed_matches_predicate(breed, attr, op, val)
            if res is True:
                penalty += 1
        score -= penalty
        scored.append((score, norm_str(get_breed_attr(breed, "name")) or norm_str(get_breed_attr(breed, "breed")) or norm_str(breed.get("name")) or norm_str(breed.get("breed")) or "", breed))

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = scored[0][2]
    chosen_name = None
    if isinstance(chosen, dict):
        chosen_name = chosen.get("name") if chosen.get("name") is not None else chosen.get("breed")
    if chosen_name is None:
        chosen_name = scored[0][1]

    cited = []
    for rid in hard_matched_ids:
        if rid is not None:
            cited.append(rid)
    cited = sorted(set(cited), key=lambda x: norm_str(x))
    return {"operation": "recommend", "breed": chosen_name, "cited_rules": cited, "rationale": "highest adjusted score after hard filtering"}
