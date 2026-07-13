# CatSynth strategy sketch

Implement `recommend(profile, breeds, rules, oracle_tags)` deterministically.

Return a dictionary with:
- `operation`: `recommend`, `abstain`, or `escalate`
- `breed`: a breed name string or `null`
- `cited_rules`: list of rule ID strings
- `rationale`: a short explanation string

## Core behavior

1. Apply hard forbid rules before ranking.
2. If any hard forbid rule matches the profile and a breed violates that rule, remove that breed.
3. If no breeds remain after hard filtering, return `abstain` with no breed.
4. Otherwise rank the remaining breeds by explicit owner preferences.
5. Use oracle tags only through controlled, documented meanings.
6. Break score ties by breed name.

## Supported value encoding

Ordinal maps:
- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

Rule operators:
- profile-side: `eq`, comma-separated `in`, `is_true`, `is_false`
- cat-side: `eq`, comma-separated `in`, `is_true`, `is_false`, `gte`, `lte`

For `gte` and `lte`, compare using the ordinal maps above.

## Hard rules

A rule row with `kind == "forbid"` removes a breed when:
- the profile matches the rule trigger, and
- the breed matches the cat predicate.

Collect and cite every applicable hard rule ID in `cited_rules`.

## Preference ranking

Only these profile fields contribute to the base score:
- `wants_size`
- `wants_affection`
- `wants_fluffy`

Scoring:
- If `wants_size` is set, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` plus `2 - energy`.
- If `wants_fluffy` is true, add `2` when the breed is fluffy, else `0`.

Do not add preference score from other profile fields unless a promoted clause defines that behavior.

## Oracle tags

The prompt-mediated note classifier returns a JSON object with a `tags` array.

Current controlled meaning:
- `avoid_needy`: a soft penalty for breeds whose `sociability` is `high` or greater.

This tag:
- never filters candidates
- never relaxes hard rules
- only changes ranking

## Tie-breaking

If two breeds have the same score, choose the breed whose `name` sorts first lexicographically.

## Safety on empty set

If hard filtering removes every breed, return `abstain` rather than forcing a recommendation or escalating.

## Constraints

- Preserve `recommend(profile, breeds, rules, oracle_tags)`.
- Do not inspect `scenario_id`.
- Do not hard-code named fixture outputs.
- Follow the supplied `breeds` list as the source of truth, even if it is partial or empty.
