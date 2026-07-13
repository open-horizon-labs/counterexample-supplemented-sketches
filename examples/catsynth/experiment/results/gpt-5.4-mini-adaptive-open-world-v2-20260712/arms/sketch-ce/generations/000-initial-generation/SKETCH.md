# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`.

## Current policy

- `operation` is `recommend` when at least one breed candidate is available.
- If `breeds` is empty, return `escalate` with `breed = null`.
- Do not inspect `scenario_id`.
- Do not assign any policy meaning to `rules` or `oracle_tags` yet.
- Do not hard-code behavior for named fixtures.

## Ranking

Rank breeds by the owner's explicit positive preferences using deterministic
ordinal encodings:

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

For this initial sketch, `cited_rules` is always an empty list because no rule
semantics are promoted yet.

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

Operators describe predicates:

- `eq`
- comma-separated `in`
- `is_true`
- `is_false`
- ordinal `gte` / `lte`

The initial sketch intentionally does not say what a matched rule does.

`oracle_tags` is a list of controlled strings. The initial sketch intentionally
assigns no meaning to any tag.

## Narrative prompt contract

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`.
It must contain a `{note}` placeholder and request JSON with a `tags` array.
At this stage, the only valid response is `{"tags": []}`.

## Empty-candidate fallback

If a later promoted clause removes every candidate but no promoted clause says
what to do with the empty set, return `escalate` with no breed. This preserves
the policy hole for a counterexample instead of silently choosing an answer.
