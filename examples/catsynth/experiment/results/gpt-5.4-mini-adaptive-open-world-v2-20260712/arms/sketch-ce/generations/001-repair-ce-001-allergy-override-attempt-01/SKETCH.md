# CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`.

## Core policy

- If `breeds` is empty, return `escalate` with `breed = null`.
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

For `in`, `trait_value` and `cat_value` are comma-separated strings. Empty values
match nothing.

When a hard rule removes one or more breeds, include the applicable rule IDs in
`cited_rules`.

If hard rules remove every breed, return `escalate` with `breed = null` and the
applicable hard rule IDs in `cited_rules`.

## Ranking after filtering

Rank the remaining breeds by the owner's explicit positive preferences using
stable ordinal encodings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

A breed's score is the sum of:

- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` value plus
  `2 - energy` as a calmness proxy.
- If `wants_fluffy` is true, add `2` when the breed's boolean `fluffy` field is
  true, otherwise add `0`.
- Break ties by breed name in ascending order.

## Output shape

Return a dictionary with:

- `operation`: one of `recommend`, `abstain`, or `escalate`
- `breed`: a breed name string or `null`
- `cited_rules`: a list of rule ID strings
- `rationale`: a short explanation string

`oracle_tags` does not affect selection unless a later sketch promotion assigns
it meaning.

## Stable input shapes

Profiles contain categorical owner traits plus the three explicit preference
fields above and an optional `narrative_note`.

Breeds contain:

- `name`
- ordinal `energy`, `shedding`, `grooming`, `sociability`, `vocal`, and
  `affection`
- `size`
- boolean `hypoallergenic`, `good_with_children`, and `fluffy`

Rule rows contain `id`, `trait`, `trait_op`, `trait_value`, `kind`,
`cat_attribute`, `cat_op`, and `cat_value`.

## Narrative prompt contract

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`.
It must contain a `{note}` placeholder and request JSON with a `tags` array.
At this stage, the only valid response is `{"tags": []}`.

## Empty-candidate fallback

If filtering removes every candidate, return `escalate` with no breed and cite
the hard rules that caused removal. This keeps the hard-rule behavior explicit
instead of silently choosing from forbidden breeds.
