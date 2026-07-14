# Initial CatSynth sketch

Implement a deterministic cat recommendation strategy with this public entry
point:

```python
recommend(profile, breeds, rules, oracle_tags)
```

Return a dictionary containing `operation`, `breed`, `cited_rules`, and
`rationale`. `operation` is `recommend`, `abstain`, or `escalate`.

First apply hard policy rules from `rules` as filters over the supplied
`breeds` list. A rule is active when its profile-side predicate matches the
profile. Active forbid rules remove any breed whose cat-side predicate matches
that rule. If no breeds remain after active forbid rules are applied, return
`abstain` with `breed = null` and cite every active forbid rule ID. Do not
relax hard rules to force a recommendation.

Use the supplied catalog as-is. Do not assume a full breed universe, and do not
hard-code named fixtures. Never inspect `scenario_id`.

Ranking is deterministic and uses only the supplied profile preferences and
controlled oracle tags.

Ordinal encodings:

- `low = 0`, `moderate = 1`, `high = 2`
- `small = 0`, `medium = 1`, `large = 2`

Base score for each surviving breed:

- If `wants_size` is set, add `max(0, 2 - abs(breed_size - wanted_size))`.
- If `wants_affection` is true, add the breed's `affection` value plus
  `2 - energy` as a calmness proxy.
- If `wants_fluffy` is true, add `2` when the breed's `fluffy` field is true
  and `0` otherwise.
- If oracle tags include `avoid_needy`, add `2 - sociability` as a soft bonus.
  This tag means the owner's note suggests the cat should be less demanding
  during absences.
- Break ties by breed name.

`oracle_tags` is a list of controlled soft tags emitted by the prompt. The only
meaning currently defined is `avoid_needy`, which is produced from notes about
frequent travel, long absences, or a lonely cat. The prompt must return JSON
with a `tags` array and must not invent other tags.

Stable input shapes:

- Profiles contain categorical owner traits plus the three explicit preference
  fields above and an optional `narrative_note`.
- Breeds contain `name`; ordinal `energy`, `shedding`, `grooming`,
  `sociability`, `vocal`, and `affection`; `size`; and boolean
  `hypoallergenic`, `good_with_children`, and `fluffy`.
- Rule rows contain `id`, `trait`, `trait_op`, `trait_value`, `kind`,
  `cat_attribute`, `cat_op`, and `cat_value`. Operators describe predicates:
  `eq`, comma-separated `in`, `is_true`, `is_false`, and ordinal `gte`/`lte`.
  For `gte` and `lte`, compare using the ordinal encodings above.

If a later promoted clause introduces new hard-policy behavior, keep that in the
same filtering stage. If it still leaves no candidates, abstain instead of
falling back to a default breed.

Keep prompt-mediated narrative interpretation in `oracle_prompt.txt`. It must
contain a `{note}` placeholder and request JSON with a `tags` array. Until a
counterexample defines another soft tag, the oracle should emit either
`{"tags": ["avoid_needy"]}` for travel/absence/loneliness notes or
`{"tags": []}` otherwise.
