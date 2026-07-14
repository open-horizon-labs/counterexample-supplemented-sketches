# CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and `rationale`.
`operation` is `recommend`, `abstain`, or `escalate`.

## Core behavior

1. Evaluate hard rules first.
2. Remove any breed that violates an applicable hard rule.
3. If no breed survives, return `abstain` with no breed and cite every applicable hard rule.
4. Otherwise rank surviving breeds deterministically and return `recommend`.

## Ordinal encodings

Use:
- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

## Hard-rule semantics

A rule row matches a profile when its profile-side predicate is true.
Supported profile predicates:
- `eq`
- comma-separated `in`
- `is_true`
- `is_false`

Supported cat predicates:
- `eq`
- comma-separated `in`
- `is_true`
- `is_false`
- ordinal `gte` / `lte`

For matching hard rules, a violating breed is removed before ranking.
If multiple hard rules match the profile, they all apply and all applicable hard rule IDs are cited.

## Soft-rule semantics

Soft rules with kind `discourage` do not remove breeds.
Each distinct applicable discourage predicate contributes one penalty point.
Duplicate soft signals from different surfaces that map to the same semantic predicate count once.

Oracle tags are soft signals and are merged with structured discourage rows by semantic predicate.
Current controlled tag meanings:
- `avoid_needy` -> discourage breeds with `sociability >= high`
- `avoid_high_energy` -> discourage breeds with `energy >= high`

Do not add score from other profile traits unless a promoted clause defines it.
The base preference score uses only the explicit preference fields:
- `wants_size`
- `wants_affection`
- `wants_fluffy`

Base score details:
- If `wants_size` has a value, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add breed affection plus `2 - breed_energy`.
- If `wants_fluffy` is true, add `2` when `fluffy` is true, else `0`.

Apply the complete soft-penalty total after base scoring.
Break ties by breed name.

## Narrative note handling

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`.
The prompt must contain a `{note}` placeholder and return exactly one JSON object with a `tags` array.
Do not invent extra tags or let the prompt rewrite the policy.

## Stability

Do not inspect `scenario_id`.
Do not hard-code behavior for named fixtures.
Follow the supplied breed list rather than assuming a fixed catalog.
