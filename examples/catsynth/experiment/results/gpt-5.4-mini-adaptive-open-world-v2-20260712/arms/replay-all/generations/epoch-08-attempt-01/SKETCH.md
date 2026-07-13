# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`. `operation` is `recommend`, `abstain`, or `escalate`. The initial
strategy returns `recommend` because no policy removes candidates yet.

Rank breeds by the owner's explicit positive preferences. Use
`low = 0`, `moderate = 1`, and `high = 2`; use
`small = 0`, `medium = 1`, and `large = 2`. A breed's score is the sum of:

- If `wants_size` has a value, `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, the breed's ordinal `affection` value plus
  `2 - energy`; lower energy is the deterministic calmness proxy.
- If `wants_fluffy` is true, `2` when the breed's boolean `fluffy` field is
  true and `0` otherwise.
- Break ties by breed name.

`rules` and `oracle_tags` are reserved policy inputs. Do not invent their
semantics before the sketch or an active counterexample defines them. Never
inspect `scenario_id` or hard-code behavior for a named fixture.

Stable input shapes:

- Profiles contain categorical owner traits plus the three explicit preference
  fields above and an optional `narrative_note`.
- Breeds contain `name`; ordinal `energy`, `shedding`, `grooming`,
  `sociability`, `vocal`, and `affection`; `size`; and boolean
  `hypoallergenic`, `good_with_children`, and `fluffy`.
- Rule rows contain `id`, `trait`, `trait_op`, `trait_value`, `kind`,
  `cat_attribute`, `cat_op`, and `cat_value`. Operators describe predicates:
  `eq`, comma-separated `in`, `is_true`, `is_false`, and ordinal `gte`/`lte`.
  The initial sketch intentionally does not say what a matched rule does.
- `oracle_tags` is a list of controlled strings. The initial sketch intentionally
assigns no meaning to any tag.

If a later promoted clause removes every candidate but no promoted clause says
what to do with the empty set, return `escalate` with no breed. This preserves
the policy hole for a counterexample instead of silently choosing an answer.

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`. It must
contain a `{note}` placeholder and request JSON with a `tags` array. Until a
counterexample defines a narrative policy, it must return `{"tags": []}` for
every note.
