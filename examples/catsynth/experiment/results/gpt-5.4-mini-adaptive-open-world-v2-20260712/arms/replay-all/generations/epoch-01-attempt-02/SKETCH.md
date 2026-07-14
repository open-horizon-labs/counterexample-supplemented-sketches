# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and `rationale`. `operation` is `recommend`, `abstain`, or `escalate`.

Use `low = 0`, `moderate = 1`, and `high = 2`; use `small = 0`, `medium = 1`, and `large = 2`.

The recommendation flow is:

1. Evaluate the supplied `rules` against the profile and breeds.
2. Apply any matching `forbid` rules as hard filters before ranking.
3. Rank the remaining breeds by the owner's explicit positive preferences.
4. Break ties by breed name.

A rule row matches a profile when its `trait`, `trait_op`, and `trait_value` condition is satisfied. Supported profile operators are `eq` and comma-separated `in`. For `in`, the rule value is encoded as a comma-separated string.

A matched `forbid` rule removes a breed when the breed satisfies the rule's cat predicate. Supported cat operators are `eq`, comma-separated `in`, `is_true`, `is_false`, and ordinal `gte`/`lte`.

When one or more forbid rules match the profile, include their IDs in `cited_rules` for the final answer because they were active hard filters, even if the chosen breed survives those filters. If no breed remains after filtering, return `escalate` with those matching forbid rule IDs.

The ranking score is the sum of:

- If `wants_size` has a value, `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, the breed's ordinal `affection` value plus `2 - energy`; lower energy is the deterministic calmness proxy.
- If `wants_fluffy` is true, `2` when the breed's boolean `fluffy` field is true and `0` otherwise.

`rules` are policy inputs, not fixtures. Do not hard-code named breeds or inspect `scenario_id`.

If all candidate breeds are removed by applicable hard filters, return `escalate` with no breed and cite the matching forbid rule IDs.

`oracle_tags` is a list of controlled strings. The prompt-mediated oracle must receive `{note}` and return one JSON object with a `tags` array. Until a specific tag meaning is established by the sketch or a supplied counterexample, treat unknown tags as having no effect.

Profiles contain categorical owner traits plus the three explicit preference fields above and an optional `narrative_note`.
Breeds contain `name`; ordinal `energy`, `shedding`, `grooming`, `sociability`, `vocal`, and `affection`; `size`; and boolean `hypoallergenic`, `good_with_children`, and `fluffy`.
