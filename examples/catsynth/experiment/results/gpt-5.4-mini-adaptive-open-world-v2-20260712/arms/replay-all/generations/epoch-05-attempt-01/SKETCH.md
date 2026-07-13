# CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`. `operation` is `recommend`, `abstain`, or `escalate`.

## Deterministic ranking

Use ordinal encodings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

Score each surviving breed using only the explicit preference fields and the
promoted soft tag meaning:

- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` value plus
  `2 - energy`.
- If `wants_fluffy` is true, add `2` when `breed.fluffy` is true and `0`
  otherwise.
- If `oracle_tags` contains `avoid_needy`, subtract `1` for breeds with
  `sociability >= high`.
- Apply every distinct applicable `discourage` rule as an additional `-1`
  penalty each.
- Break ties by breed name.

Default owner traits such as `activity_level`, `noise_tolerance`, and
`experience` add no score unless a promoted rule says otherwise.

## Rule handling

`rules` are policy inputs with fields `id`, `trait`, `trait_op`, `trait_value`,
`kind`, `cat_attribute`, `cat_op`, `cat_value`, and `reason`.

Operators mean:

- `eq`: equality
- `in`: comma-separated membership on `trait_value`
- `is_true` / `is_false`: boolean predicate
- `gte` / `lte`: ordinal comparison using the level encoding above

For each rule whose profile predicate matches:

- `kind == forbid`: remove breeds whose cat predicate matches the rule.
- `kind == discourage`: keep the breed, but apply a one-point soft penalty.

If the hard forbid rules remove every candidate, return `abstain` with no breed
and cite every applicable hard rule id. Do not relax hard policy to force a
recommendation.

If no candidate survives for any other deterministic reason, return `escalate`
with no breed.

## Narrative tag handling

`oracle_tags` are controlled soft tags produced by `oracle_prompt.txt`.
The only promoted tag meaning is `avoid_needy`, which marks notes about frequent
travel, repeated absence, or a lonely cat. The prompt must classify only the
note and must not invent additional tags.

## Input shapes

- Profiles contain categorical owner traits plus the three explicit preference
  fields above and an optional `narrative_note`.
- Breeds contain `name`; ordinal `energy`, `shedding`, `grooming`,
  `sociability`, `vocal`, and `affection`; `size`; and boolean
  `hypoallergenic`, `good_with_children`, and `fluffy`.
- Breed selection must follow the supplied `breeds` list rather than any named
  fixture or hidden catalog.

Never inspect `scenario_id` or hard-code behavior for a named fixture.
