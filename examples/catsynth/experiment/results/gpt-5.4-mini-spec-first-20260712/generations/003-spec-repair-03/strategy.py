def recommend(profile, breeds, rules, oracle_tags):
    def norm_text(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower()

    def split_csv_set(value):
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set)):
            items = value
        else:
            items = str(value).split(',')
        out = set()
        for item in items:
            n = norm_text(item)
            if n not in (None, ''):
                out.add(n)
        return out

    def get_profile_value(obj, key):
        if not isinstance(obj, dict):
            return None
        if key in obj:
            return obj[key]
        nk = norm_text(key)
        for k, v in obj.items():
            if norm_text(k) == nk:
                return v
        return None

    def get_breed_attr(breed, attr):
        if not isinstance(breed, dict):
            return None
        candidates = [attr, 'breed_' + attr, 'cat_' + attr]
        for cand in candidates:
            if cand in breed:
                return breed[cand]
        na = norm_text(attr)
        for k, v in breed.items():
            nk = norm_text(k)
            if nk in (na, 'breed_' + na, 'cat_' + na):
                return v
        return None

    def parse_bool(value):
        if isinstance(value, bool):
            return value
        n = norm_text(value)
        if n in ('true', 'yes', '1'):
            return True
        if n in ('false', 'no', '0'):
            return False
        return None

    def valid_allergies(value):
        return norm_text(value) in ('none', 'mild', 'severe')

    def level_value(value):
        n = norm_text(value)
        if n == 'low':
            return 0
        if n == 'moderate':
            return 1
        if n == 'high':
            return 2
        return None

    def size_value(value):
        n = norm_text(value)
        if n == 'small':
            return 0
        if n == 'medium':
            return 1
        if n == 'large':
            return 2
        return None

    def comparable_value(value):
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        lv = level_value(value)
        if lv is not None:
            return lv
        sv = size_value(value)
        if sv is not None:
            return sv
        try:
            return float(str(value).strip())
        except Exception:
            return None

    def breed_matches_predicate(breed, attr, op, cmp_value):
        opn = norm_text(op)
        bv = get_breed_attr(breed, attr)
        if opn in ('is_true', 'is_false'):
            bb = parse_bool(bv)
            if bb is None:
                return None
            return bb if opn == 'is_true' else (not bb)
        if opn in ('eq', 'neq'):
            left = norm_text(bv)
            right = norm_text(cmp_value)
            if left is None or right is None:
                return None
            return left == right if opn == 'eq' else left != right
        if opn in ('gte', 'lte'):
            left = comparable_value(bv)
            right = comparable_value(cmp_value)
            if left is None or right is None:
                return None
            return left >= right if opn == 'gte' else left <= right
        return None

    def profile_trigger_status(row):
        op = norm_text(row.get('trait_op'))
        pv = get_profile_value(profile, row.get('trait'))
        tv = row.get('trait_value')
        if op == 'eq':
            if pv is None:
                return False
            return norm_text(pv) == norm_text(tv)
        if op == 'in':
            if pv is None:
                return False
            return norm_text(pv) in split_csv_set(tv)
        if op == 'is_true':
            return parse_bool(pv) is True
        if op == 'is_false':
            return parse_bool(pv) is False
        return None

    def canonical_predicate(row):
        return (norm_text(row.get('cat_attribute')), norm_text(row.get('cat_op')), norm_text(row.get('cat_value')))

    if not isinstance(breeds, list) or len(breeds) == 0:
        return {'operation': 'escalate', 'breed': None, 'cited_rules': [], 'rationale': 'empty breed catalog'}

    allergies = get_profile_value(profile, 'allergies')
    if not valid_allergies(allergies):
        return {'operation': 'escalate', 'breed': None, 'cited_rules': [], 'rationale': 'uninterpretable allergies'}

    applicable_hard = []
    hard_cited = []
    soft_preds = set()

    for row in rules or []:
        if not isinstance(row, dict):
            continue
        status = profile_trigger_status(row)
        if status is None or status is False:
            continue

        rid = row.get('id')
        kind = norm_text(row.get('kind'))
        attr = row.get('cat_attribute')
        op = row.get('cat_op')
        val = row.get('cat_value')
        opn = norm_text(op)

        if kind not in ('forbid', 'discourage'):
            return {'operation': 'escalate', 'breed': None, 'cited_rules': [rid] if rid is not None else [], 'rationale': 'unsupported applicable rule kind'}
        if opn not in ('is_true', 'is_false', 'eq', 'neq', 'gte', 'lte'):
            return {'operation': 'escalate', 'breed': None, 'cited_rules': [rid] if rid is not None else [], 'rationale': 'unsupported applicable breed predicate'}
        if breed_matches_predicate(breeds[0], attr, op, val) is None:
            return {'operation': 'escalate', 'breed': None, 'cited_rules': [rid] if rid is not None else [], 'rationale': 'unsupported applicable breed predicate'}

        if kind == 'forbid':
            applicable_hard.append((rid, attr, op, val))
        else:
            soft_preds.add(canonical_predicate(row))

    surviving = list(breeds)
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
            hard_cited.append(rid)
        surviving = next_survivors

    if not surviving:
        cited = []
        for rid, _, _, _ in applicable_hard:
            if rid is not None and rid not in cited:
                cited.append(rid)
        cited.sort(key=lambda x: norm_text(x))
        return {'operation': 'abstain', 'breed': None, 'cited_rules': cited, 'rationale': 'hard policy removes all candidates'}

    for tag in oracle_tags or []:
        tn = norm_text(tag)
        if tn == 'avoid_needy':
            soft_preds.add(('sociability', 'gte', 'high'))
        elif tn == 'avoid_vocal':
            soft_preds.add(('vocal', 'gte', 'high'))
        elif tn == 'avoid_high_energy':
            soft_preds.add(('energy', 'gte', 'high'))

    wants_size = comparable_value(get_profile_value(profile, 'wants_size'))
    wants_affection = parse_bool(get_profile_value(profile, 'wants_affection')) is True
    wants_fluffy = parse_bool(get_profile_value(profile, 'wants_fluffy')) is True

    scored = []
    for breed in surviving:
        score = 0
        if wants_size is not None:
            bs = comparable_value(get_breed_attr(breed, 'size'))
            if bs is not None:
                score += max(0, 2 - abs(bs - wants_size))
        if wants_affection:
            aff = comparable_value(get_breed_attr(breed, 'affection'))
            energy = comparable_value(get_breed_attr(breed, 'energy'))
            if aff is not None and energy is not None:
                score += aff + (2 - energy)
        if wants_fluffy and parse_bool(get_breed_attr(breed, 'fluffy')) is True:
            score += 2

        penalty = 0
        for attr, op, val in soft_preds:
            if breed_matches_predicate(breed, attr, op, val) is True:
                penalty += 1
        score -= penalty

        name = get_breed_attr(breed, 'name')
        if name is None:
            name = get_breed_attr(breed, 'breed')
        scored.append((score, norm_text(name) or '', breed, name))

    scored.sort(key=lambda x: (-x[0], x[1]))
    cited = sorted(set(hard_cited), key=lambda x: norm_text(x))
    return {'operation': 'recommend', 'breed': scored[0][3], 'cited_rules': cited, 'rationale': 'highest adjusted score after hard filtering'}
