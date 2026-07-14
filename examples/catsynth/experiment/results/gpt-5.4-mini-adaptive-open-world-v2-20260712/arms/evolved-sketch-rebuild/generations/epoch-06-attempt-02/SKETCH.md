# CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and `rationale`.

## Core policy

- If `breeds` is empty, return `escalate` with `breed = null`.
- If hard rules eliminate every supplied breed, return `abstain` with `breed = null` and cite the applicable hard rule IDs.
- Do not inspect `scenario_id`.
- Do not hard-code behavior for named fixtures.
- Preserve deterministic behavior across identical inputs.

## Hard rules first

Some rule rows are promoted to hard filters.

A hard `forbid` rule removes a breed when both of these are true:

1. the profile matches the rule trigger, and
2. the breed matches the rule's cat predicate.

Supported predicate operators:

- `eq`
- comma-separated `in`
- `is_true`
- `is_false`
- ordinal `gte` / `lte`

For `in`, `trait_value` and `cat_value` are comma-separated strings. Empty values match nothing.

When a hard rule removes one or more breeds, include the applicable rule IDs in `cited_rules`.

If hard rules remove every breed, return `abstain` with `breed = null` and the applicable hard rule IDs in `cited_rules`. This is a safe no-solution signal, not an escalation.

## Ranking after filtering

Rank the remaining breeds by the owner's explicit positive preferences using stable ordinal encodings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

A breed's score is the sum of:

- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` value plus `2 - energy` as a calmness proxy.
- If `wants_fluffy` is true, add `2` when the breed's boolean `fluffy` field is true, otherwise add `0`.
- Apply every distinct applicable `discourage` rule as a soft penalty during ranking, but deduplicate soft penalties by semantic predicate. The same `(cat_attribute, cat_op, cat_value)` concern is only counted once even when it appears in both structured rules and narrative tags.
- Narrative tags may introduce the same soft predicates as structured rules. Their penalties also deduplicate against one another by semantic predicate.
- If the oracle tag `avoid_needy` is present, it maps to the predicate `sociability gte high` and adds a one-point soft penalty unless that predicate was already counted.
- If the oracle tag `avoid_high_energy` is present, it maps to the predicate `energy gte high` and adds a one-point soft penalty unless that predicate was already counted.
- Soft penalties affect ranking only and are not reported as cited rules.
- Break ties by breed name in ascending order.

## Output shape

Return a dictionary with:

- `operation`: one of `recommend`, `abstain`, or `escalate`
- `breed`: a breed name string or `null`
- `cited_rules`: a list of rule ID strings
- `rationale`: a short explanation string

`oracle_tags` only affects selection through controlled meanings defined in this sketch. The current controlled narrative tags are `avoid_needy` and `avoid_high_energy`.

## Stable input shapes

Profiles contain categorical owner traits plus the three explicit preference fields above and an optional `narrative_note`.

Breeds contain:

- `name`
- ordinal `energy`, `shedding`, `grooming`, `sociability`, `vocal`, and `affection`
- `size`
- boolean `hypoallergenic`, `good_with_children`, and `fluffy`

Rule rows contain `id`, `trait`, `trait_op`, `trait_value`, `kind`, `cat_attribute`, `cat_op`, and `cat_value`.

## Narrative prompt contract

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`.
It must contain a `{note}` placeholder and request JSON with a `tags` array.
The controlled output currently includes:

- `avoid_needy` for notes about frequent travel, repeated absence, or a lonely or miserable cat left alone.
- `avoid_high_energy` for notes about wanting a calm, low-key, quiet, or low-energy cat, or explicitly not wanting a high-energy companion.

## Empty-candidate fallback

If `breeds` is empty, return `escalate` with no breed because there is no catalog to evaluate.

If filtering removes every candidate, return `abstain` with no breed and cite the hard rules that caused removal. This keeps the hard-rule behavior explicit instead of silently choosing from forbidden breeds or escalating a solvable no-match case.
