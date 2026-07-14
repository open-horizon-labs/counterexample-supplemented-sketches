# CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary with exactly these keys:

- `operation`
- `breed`
- `cited_rules`
- `rationale`

## Policy summary

1. Safety and trust checks happen first.
2. Hard forbid rules filter candidates.
3. If at least one breed remains, rank the survivors.
4. Narrative tags only affect ranking through two controlled meanings.
5. Never branch on `scenario_id` and never hard-code fixture outputs.
6. Behavior must be deterministic for identical inputs.

## Input validation and escalation

Return `escalate` with `breed = null` when:

- `profile.allergies` is missing, blank, unknown, or not one of `none`, `mild`, `severe`
- `breeds` is empty
- any rule that applies to the profile has an unsupported `kind`, `trait_op`, `cat_attribute`, `cat_op`, or ordinal value

The escalation response must cite the malformed rule ID when the rule source is the problem.

## Supported rule model

Rule rows may use:

- `kind`: `forbid` or `discourage`
- `trait_op`: `eq`, `in`, `is_true`, or `is_false`
- `cat_op`: `eq`, `in`, `is_true`, `is_false`, `gte`, `lte`

Supported cat attributes are:

- `size`
- `energy`
- `shedding`
- `grooming`
- `sociability`
- `vocal`
- `affection`
- `hypoallergenic`
- `good_with_children`
- `fluffy`

Ordinal values are encoded as strings from the stable sets:

- levels: `low`, `moderate`, `high`
- sizes: `small`, `medium`, `large`

For `in`, empty values match nothing.

## Hard rules

A hard `forbid` rule removes a breed when:

1. the profile matches the rule trigger, and
2. the breed matches the rule predicate.

Profile triggers must support `eq`, `in`, `is_true`, and `is_false` so rules like "young_children is_true" work.

If hard rules remove every breed, return:

- `operation = abstain`
- `breed = null`
- `cited_rules = the hard-rule IDs that caused removal`

This is a safe no-solution signal, not an escalation.

## Ranking

Score each remaining breed with these owner preferences:

- If `wants_size` is set, prefer closer size matches using the stable size order.
- If `wants_affection` is true, reward higher affection and lower energy.
- If `wants_fluffy` is true, reward fluffy breeds.

Then apply soft penalties:

- every applicable `discourage` rule contributes a one-point penalty for its semantic predicate
- deduplicate soft penalties by semantic predicate, not by rule ID
- the same predicate only counts once even if it appears in multiple structured rules
- narrative tags also deduplicate against structured rules and each other

Break ties by breed name in ascending order.

## Controlled oracle tags

Only two narrative tags are allowed:

- `avoid_needy` maps to `sociability gte high`
- `avoid_high_energy` maps to `energy gte high`

The oracle prompt must ask for JSON with a `tags` array and must contain the literal placeholder `{note}`.

## Output shape

Return:

- `operation`: `recommend`, `abstain`, or `escalate`
- `breed`: a breed-name string or `null`
- `cited_rules`: a list of rule ID strings
- `rationale`: a short explanation string

## Implementation notes

- Treat the supplied `breeds` list as the catalog of record.
- Treat the supplied `rules` list as the policy source of record.
- Do not rely on hidden fixtures.
- Keep the logic simple, explicit, and reproducible.
