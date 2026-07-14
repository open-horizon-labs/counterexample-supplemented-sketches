# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary with exactly these keys:

- `operation`
- `breed`
- `cited_rules`
- `rationale`

`operation` must be one of `recommend`, `abstain`, or `escalate`.

## Initial behavior

The initial strategy uses only the owner's explicit positive preferences. No policy removes candidates yet, so rule rows and oracle tags are reserved inputs rather than active decision mechanisms.

### Input shapes

- Profiles contain categorical owner traits plus:
  - `wants_size`
  - `wants_affection`
  - `wants_fluffy`
  - `narrative_note`
- Breeds contain:
  - `name`
  - ordinal `energy`, `shedding`, `grooming`, `sociability`, `vocal`, `affection`
  - ordinal `size`
  - boolean `hypoallergenic`, `good_with_children`, `fluffy`
  - plus `summary` and `wiki_url`
- Rule rows contain:
  - `id`, `trait`, `trait_op`, `trait_value`, `kind`, `cat_attribute`, `cat_op`, `cat_value`
- `oracle_tags` is a list of controlled strings.

### Ordinal encoding

Use these deterministic mappings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

### Scoring

Rank breeds by the sum of these preference signals:

- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's ordinal `affection` value plus `2 - energy`; lower energy is the deterministic calmness proxy.
- If `wants_fluffy` is true, add `2` when `fluffy` is true and `0` otherwise.
- Break ties by breed name.

### Policy boundaries

- Do not invent semantics for `rules` or `oracle_tags` before the sketch or an active counterexample defines them.
- Do not inspect `scenario_id`.
- Do not hard-code named fixture outputs.
- Do not branch on case labels or unrevealed scenario identifiers.

### Empty catalogs

If the supplied breed list is empty, return `escalate` with no breed.

## Oracle contract

Keep narrative interpretation in `oracle_prompt.txt`.

That prompt must:

- contain a `{note}` placeholder
- request one JSON object with a `tags` array
- stay within the tag meanings defined by the current sketch or supplied counterexamples
- return `{"tags": []}` for every note until a counterexample defines a narrative policy
