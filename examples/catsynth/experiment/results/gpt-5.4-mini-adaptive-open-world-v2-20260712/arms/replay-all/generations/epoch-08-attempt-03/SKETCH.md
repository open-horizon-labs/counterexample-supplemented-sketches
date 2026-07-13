# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`. `operation` is `recommend`, `abstain`, or `escalate`.

Do not import modules. Keep the implementation self-contained and deterministic.

Use the supplied catalog and rules rather than named fixtures. The strategy must
respect hard safety rules before any preference ranking, and it must surface
policy failures instead of silently skipping them.

Stable input shapes:

- Profiles contain categorical owner traits plus the three explicit preference
  fields above and an optional `narrative_note`.
- Breeds contain `name`; ordinal `energy`, `shedding`, `grooming`,
  `sociability`, `vocal`, and `affection`; `size`; and boolean
  `hypoallergenic`, `good_with_children`, and `fluffy`.
- Rule rows contain `id`, `trait`, `trait_op`, `trait_value`, `kind`,
  `cat_attribute`, `cat_op`, and `cat_value`. Operators describe predicates:
  `eq`, comma-separated `in`, `is_true`, `is_false`, and ordinal `gte`/`lte`.
  A rule blocks a breed only when it clearly matches and its kind is `forbid`.
  A rule is a soft discouragement only when it clearly matches and its kind is
  `discourage`.

Policy behavior:

- If `allergies` is missing, null, blank, or not one of `none`, `mild`, or
  `severe`, return `escalate` with no breed.
- If an applicable rule row has an unsupported kind, trait operator, cat
  operator, attribute, or ordinal value, return `escalate` and cite that rule
  id.
- Hard rules compose. Filter every breed that matches every applicable `forbid`
  rule before ranking. If filtering removes every breed, return `abstain` and
  cite every applicable hard rule id.
- A `forbid` rule that matches the profile should be cited whenever it is
  applicable, even if the selected breed survives it because another breed was
  filtered instead.
- `discourage` rules never filter candidates.
- Distinct applicable `discourage` rules each contribute one point of soft
  penalty when they match a breed.
- The controlled oracle tag `avoid_needy` applies a one-point soft penalty to
  breeds whose sociability is high or greater. It never filters candidates or
  relaxes hard rules.

Ranking:

- Rank breeds by the owner's explicit positive preferences.
- Use `low = 0`, `moderate = 1`, and `high = 2`; use
  `small = 0`, `medium = 1`, and `large = 2`.
- A breed's base score is the sum of:
  - If `wants_size` has a value, `max(0, 2 - abs(breed_size - wanted_size))`.
  - If `wants_affection` is true, the breed's ordinal `affection` value plus
    `2 - energy`; lower energy is the deterministic calmness proxy.
  - If `wants_fluffy` is true, `2` when the breed's boolean `fluffy` field is
    true and `0` otherwise.
- Add one penalty point for each applicable soft rule that matches the breed.
- If `avoid_needy` is present, add one more penalty point to breeds whose
  sociability is high or greater.
- Break ties by breed name.

`rules` and `oracle_tags` are reserved policy inputs. Use only meanings that the
sketch or a supplied counterexample has already defined. Never inspect
`scenario_id` or hard-code behavior for a named fixture.

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`. It must
contain a `{note}` placeholder and request JSON with a `tags` array.
