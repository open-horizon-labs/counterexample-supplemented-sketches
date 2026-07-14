# CatSynth deterministic recommendation sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary with exactly these keys:

- `operation`: one of `recommend`, `abstain`, or `escalate`
- `breed`: a breed name string or `null`
- `cited_rules`: a list of rule ID strings
- `rationale`: a short explanation string

## Policy

1. Apply every rule whose profile predicate matches the current profile.
2. Treat `kind == "forbid"` as a hard filter.
3. If a matching forbid rule's cat predicate matches a breed, remove that breed and cite that rule ID.
4. If filtering removes every breed, return `abstain` with `breed = null` and cite every applicable forbid rule ID.
5. Otherwise, rank the surviving breeds by the owner's explicit positive preferences.

## Preference ranking

Use these ordinal encodings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

Score each surviving breed as follows:

- If `wants_size` is set, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` value plus `2 - energy`.
- If `wants_fluffy` is true and the breed is fluffy, add `2`.
- Break ties by breed name.

Choose the top-ranked surviving breed and return `recommend`.

## Rule predicate semantics

Rule rows contain:

- `id`
- `trait`
- `trait_op`
- `trait_value`
- `kind`
- `cat_attribute`
- `cat_op`
- `cat_value`
- `reason`

Supported operators:

- profile-side: `eq`, comma-separated `in`, `is_true`, `is_false`
- breed-side: `eq`, comma-separated `in`, `is_true`, `is_false`, `gte`, `lte`

For ordinal comparisons, use the same `low / moderate / high` mapping above.
For `in`, treat `trait_value` and `cat_value` as comma-separated strings.

## Input contract

- Do not inspect `scenario_id`.
- Do not hard-code named fixture outputs.
- Do not import modules or access files/network.
- Follow the supplied `breeds` list exactly, whether it is full, partial, or empty.
- Preserve the `recommend(profile, breeds, rules, oracle_tags)` signature.

## Oracle tags

`oracle_tags` is reserved for prompt-mediated narrative interpretation. Unless a future sketch or counterexample defines a tag meaning, it has no effect on ranking or filtering.

## Oracle prompt contract

`oracle_prompt.txt` must contain a `{note}` placeholder and return one JSON object with a `tags` array. With no defined tag meanings, the oracle should always return `{"tags": []}`.
