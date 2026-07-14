def _parse_bool(value):
    return value is True or (isinstance(value, str) and value.lower() == 'true')


def _parse_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == '':
            return None
        if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
            return int(text)
    return None


def _csv_set(value):
    if not isinstance(value, str) or value.strip() == '':
        return set()
    return set(part.strip() for part in value.split(',') if part.strip() != '')


def _matches_eq(candidate, expected):
    return candidate == expected


def _matches_in(candidate, expected_csv):
    allowed = _csv_set(expected_csv)
    if not allowed:
        return False
    return str(candidate) in allowed


def _matches_is_true(candidate):
    return candidate is True


def _matches_is_false(candidate):
    return candidate is False


def _matches_ordinal(candidate, op, expected):
    left = _parse_int(candidate)
    right = _parse_int(expected)
    if left is None or right is None:
        return False
    if op == 'gte':
        return left >= right
    if op == 'lte':
        return left <= right
    return False


def _profile_matches_rule(profile, rule):
    trait = rule.get('trait')
    op = rule.get('trait_op')
    expected = rule.get('trait_value')
    value = profile.get(trait)

    if op == 'eq':
        return _matches_eq(value, expected)
    if op == 'in':
        return _matches_in(value, expected)
    if op == 'is_true':
        return _matches_is_true(value)
    if op == 'is_false':
        return _matches_is_false(value)
    if op in ('gte', 'lte'):
        return _matches_ordinal(value, op, expected)
    return False


def _breed_matches_rule(breed, rule):
    attr = rule.get('cat_attribute')
    op = rule.get('cat_op')
    expected = rule.get('cat_value')
    value = breed.get(attr)

    if op == 'eq':
        return _matches_eq(value, expected)
    if op == 'in':
        return _matches_in(value, expected)
    if op == 'is_true':
        return _matches_is_true(value)
    if op == 'is_false':
        return _matches_is_false(value)
    if op in ('gte', 'lte'):
        return _matches_ordinal(value, op, expected)
    return False


def _hard_forbidden_breeds(profile, breeds, rules):
    forbidden = set()
    cited = []
    for rule in rules or []:
        if rule.get('kind') != 'forbid':
            continue
        if not _profile_matches_rule(profile, rule):
            continue
        rule_id = rule.get('id')
        hit = False
        for breed in breeds:
            if _breed_matches_rule(breed, rule):
                hit = True
                forbidden.add(breed.get('name'))
        if hit and rule_id is not None:
            cited.append(rule_id)
    return forbidden, cited


def _ord(value):
    parsed = _parse_int(value)
    return parsed if parsed is not None else 0


def _size_ord(value):
    mapping = {'small': 0, 'medium': 1, 'large': 2}
    return mapping.get(value, 0)


def _score_breed(profile, breed, oracle_tags):
    score = 0

    wanted_size = profile.get('wants_size')
    if wanted_size in ('small', 'medium', 'large'):
        score += max(0, 2 - abs(_size_ord(breed.get('size')) - _size_ord(wanted_size)))

    if _parse_bool(profile.get('wants_affection')):
        score += _ord(breed.get('affection')) + (2 - _ord(breed.get('energy')))

    if _parse_bool(profile.get('wants_fluffy')):
        score += 2 if breed.get('fluffy') is True else 0

    if oracle_tags and 'avoid_needy' in set(oracle_tags):
        score -= _ord(breed.get('sociability'))
        score -= _ord(breed.get('affection'))

    return score


def recommend(profile, breeds, rules, oracle_tags):
    breeds = list(breeds or [])
    if not breeds:
        return {
            'operation': 'escalate',
            'breed': None,
            'cited_rules': [],
            'rationale': 'No breeds were supplied, so there is no catalog to evaluate.'
        }

    forbidden, cited = _hard_forbidden_breeds(profile or {}, breeds, rules or [])
    survivors = [breed for breed in breeds if breed.get('name') not in forbidden]

    if not survivors:
        return {
            'operation': 'abstain',
            'breed': None,
            'cited_rules': cited,
            'rationale': 'All supplied breeds were removed by applicable hard rules.'
        }

    best = None
    best_score = None
    for breed in survivors:
        score = _score_breed(profile or {}, breed, oracle_tags or [])
        key = (score, breed.get('name') or '')
        if best is None or key > best_score:
            best = breed
            best_score = key

    rationale_bits = ['Selected the highest-scoring remaining breed after hard-rule filtering.']
    if oracle_tags and 'avoid_needy' in set(oracle_tags):
        rationale_bits.append('Applied a soft penalty for needier cats.')

    return {
        'operation': 'recommend',
        'breed': best.get('name'),
        'cited_rules': cited,
        'rationale': ' '.join(rationale_bits)
    }
