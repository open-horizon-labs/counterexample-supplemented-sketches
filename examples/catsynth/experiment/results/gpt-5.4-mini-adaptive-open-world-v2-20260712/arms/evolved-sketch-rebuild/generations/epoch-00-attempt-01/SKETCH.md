# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and `rationale`.
`operation` is `recommend`, `abstain`, or `escalate`.

## Baseline behavior

This initial strategy does not assign meaning to `rules` or `oracle_tags` yet.
It therefore keeps every supplied breed that has a usable `name` and ranks the remaining catalog by explicit owner preferences.

Rank breeds using these deterministic rules:

- Ordinal mapping: `low = 0`, `moderate = 1`, `high = 2`
- Size mapping: `small = 0`, `medium = 1`, `large = 2`
- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`
- If `wants_affection` is true, add the breed's `affection` ordinal plus `2 - energy`
- If `wants_fluffy` is true, add `2` when `fluffy` is true, otherwise add `0`
- Break ties by breed name, ascending

## Return policy

- If `breeds` is empty or no breed row has a usable `name`, return:
  - `operation: "escalate"`
  - `breed: null`
  - `cited_rules: []`
- Otherwise return:
  - `operation: "recommend"`
  - `breed:` the top-ranked breed name
  - `cited_rules: []`
  - `rationale:` a short deterministic explanation of the score sources

## Input shapes

Profiles contain categorical owner traits plus the explicit preference fields above and an optional `narrative_note`.
Breeds contain:

- `name`
- ordinal `energy`, `shedding`, `grooming`, `sociability`, `vocal`, `affection`
- `size`
- boolean `hypoallergenic`, `good_with_children`, `fluffy`

Rule rows contain:

- `id`
- `trait`
- `trait_op`
- `trait_value`
- `kind`
- `cat_attribute`
- `cat_op`
- `cat_value`

Operators describe predicates: `eq`, comma-separated `in`, `is_true`, `is_false`, and ordinal `gte`/`lte`.
This sketch intentionally does not define a rule-matching effect yet.

`oracle_tags` is a list of controlled strings. This sketch intentionally does not assign meaning to any tag yet.

## Narrative prompt contract

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`.
It must contain a `{note}` placeholder and request one JSON object with a `tags` array.
Until a counterexample defines a narrative policy, it must return `{"tags": []}` for every note.

## Policy boundary

Do not inspect `scenario_id`.
Do not hard-code named fixture behavior.
Do not import modules, access files, or rely on network calls.
If a future promoted clause removes every candidate but does not define empty-set handling, that later clause may escalate; this initial sketch leaves that policy hole closed only by the no-candidate case above.
