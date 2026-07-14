# CatSynth promoted sketch

Implement `recommend(profile, breeds, rules, oracle_tags)` as a deterministic policy engine.

Return a dictionary with exactly:
- `operation`: `recommend`, `abstain`, or `escalate`
- `breed`: a breed name string or `null`
- `cited_rules`: a list of rule ID strings
- `rationale`: a short explanation string

## Core behavior

1. Validate safety inputs first.
   - If `profile["allergies"]` is missing, null, blank, or not one of `none`, `mild`, `severe`, return `escalate` with no breed.

2. Apply hard rules before ranking.
   - A rule with `kind == "forbid"` removes a breed when:
     - the profile side matches the rule trigger, and
     - the breed side matches the cat predicate.
   - If no breed survives hard rules, return `abstain` with no breed and cite every applicable hard rule ID.
   - Hard rules compose; do not relax them to force a recommendation.

3. Rank surviving breeds deterministically.
   - Ordinal values:
     - `low = 0`, `moderate = 1`, `high = 2`
     - `small = 0`, `medium = 1`, `large = 2`
   - Base preference score uses only the explicit preference fields:
     - `wants_size`: `max(0, 2 - abs(breed_size - wanted_size))`
     - `wants_affection == true`: `breed_affection + (2 - breed_energy)`
     - `wants_fluffy == true`: add `2` if `breed.fluffy` is true, else `0`
   - Break ties by breed name.

4. Apply soft discouragement rules.
   - A rule with `kind == "discourage"` does not remove a breed.
   - Each distinct applicable discourage predicate subtracts 1 point.
   - Distinctness is by semantic predicate: `(cat_attribute, cat_op, cat_value)`.
   - Merge structured discourage rules and narrative tags by that semantic predicate so the same concern is counted once.
   - Do not give default profile traits extra score unless a promoted rule or tag explicitly defines them.

## Narrative tags

`oracle_tags` is the output of `oracle_prompt.txt` and contains controlled soft tags only.

Promoted tag meanings:
- `avoid_needy`: subtract 1 for breeds with `sociability >= high`
- `avoid_high_energy`: subtract 1 for breeds with `energy >= high`

Tags never filter candidates and never override hard rules.

## Prompt contract

`oracle_prompt.txt` must:
- include a `{note}` placeholder
- request exactly one JSON object with a `tags` array
- use only the controlled tags defined above
- return `{"tags": []}` when the note does not clearly match a controlled meaning

## Stability rules

- Do not inspect `scenario_id`.
- Do not hard-code named fixture outputs.
- Do not import modules, access files, or use network calls.
- Follow the supplied breed list rather than any external catalog.
- Keep the implementation deterministic.
