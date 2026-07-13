# CatSynth complete implementation specification

This document is the sole requirements authority for the spec-first arm. It is
an algorithmic specification, not a sketch. Implement it without relying on
fixture identity, worked outputs, or case-specific branches.

## Deliverables

Produce two files:

1. `strategy.py`, containing exactly one public entry point:

   ```python
   recommend(profile, breeds, rules, oracle_tags)
   ```

2. `oracle_prompt.txt`, containing a `{note}` placeholder and instructions that
   make the narrative Oracle return one JSON object with a `tags` array.

The implementation may define private helpers inside `strategy.py`. It may not
import modules, access files or the network, mutate inputs, inspect fixture
identity, or branch on concrete scenario, case, or breed names.

## Output contract

`recommend` returns a dictionary with exactly these policy fields plus a
diagnostic rationale:

- `operation`: `recommend`, `abstain`, or `escalate`
- `breed`: selected breed name for `recommend`, otherwise `null`
- `cited_rules`: sorted, duplicate-free rule IDs
- `rationale`: concise string; not policy-bearing

## Normalization

String comparisons are case-insensitive and ignore leading and trailing
whitespace. Comma-separated values are split, trimmed, normalized, and compared
as a set. Breed names retain their supplied spelling in output but use their
normalized form for deterministic ordering.

The ordinal scales are:

- levels: `low = 0`, `moderate = 1`, `high = 2`
- sizes: `small = 0`, `medium = 1`, `large = 2`

## Input and escalation boundaries

The supplied `breeds` list is the entire catalog for that call. Do not replace
or supplement it from known fixtures.

- If `breeds` is empty, return `escalate`, no breed, and no citations. An absent
  catalog is not evidence that policy rejected every candidate.
- Normalize `profile.allergies`. If it is missing, blank, or outside
  `none`, `mild`, and `severe`, return `escalate`, no breed, and no citations.
- An uninterpretable policy row is fatal only when its profile trigger applies.
  Return `escalate`, no breed, and cite that row's ID. A malformed row whose
  trigger is definitively false has no effect.

## Applicable rules

Rule rows contain:

- `id`
- `trait`, `trait_op`, `trait_value`
- `kind`
- `cat_attribute`, `cat_op`, `cat_value`

First evaluate the profile trigger. Supported `trait_op` values are:

- `eq`: normalized equality
- `in`: normalized membership in a comma-separated set
- `is_true`: the profile value is boolean true
- `is_false`: the profile value is boolean false

Only a row with a true profile trigger is applicable. Once applicable, its
`kind`, breed attribute, operator, and comparison value must be valid.

Supported kinds:

- `forbid`: hard policy
- `discourage`: soft policy

Supported breed predicates:

- `is_true` and `is_false` for boolean attributes
- `eq` and `neq` for comparable values
- `gte` and `lte` for ordinal level or size attributes

Unsupported applicable language must escalate with the responsible rule ID. It
must never be silently skipped.

## Hard policy

Evaluate every applicable `forbid` row against the original supplied catalog.
The outcome and provenance must not depend on input rule order.

- Remove every breed matched by at least one applicable hard predicate.
- Hard policy always outranks preferences, soft rules, and narrative text.
- If at least one breed survives, `cited_rules` contains only applicable hard
  rule IDs that matched at least one breed in the original supplied catalog.
- If no breed survives, return `abstain`, no breed, and cite every applicable
  hard rule ID. Do not relax a hard rule to force a recommendation.

## Soft policy and semantic deduplication

An applicable `discourage` row contributes a one-point ranking penalty to each
matching surviving breed. It never filters, triggers abstention, or appears in
`cited_rules`.

Merge structured soft rows and narrative tags by normalized semantic predicate:

```text
(cat_attribute, cat_op, cat_value)
```

Apply each distinct semantic predicate once, even if it appears in duplicate
rows or is expressed by both structured and narrative inputs. Distinct
predicates compose and each contributes one point.

Narrative tags map to these soft predicates:

- `avoid_needy` → sociability `gte high`
- `avoid_vocal` → vocal `gte high`
- `avoid_high_energy` → energy `gte high`

Unknown tags have no effect. Narrative tags may never waive or weaken hard
policy.

## Base preference score

For every hard-policy survivor, begin at zero and add only:

1. If `wants_size` is supplied and valid:
   `max(0, 2 - abs(breed_size - wanted_size))`
2. If `wants_affection` is true:
   `breed_affection + (2 - breed_energy)`
3. If `wants_fluffy` is true and the breed is fluffy: `2`

Default profile fields such as activity level, noise tolerance, experience,
home size, and work hours do not add preference points. They affect ranking only
through applicable policy rows.

Subtract the deduplicated soft-penalty total. Rank by final adjusted score
descending, then normalized breed name ascending. Apply name ordering only
after every hard and soft adjustment.

## Narrative Oracle

`oracle_prompt.txt` must ask the model to interpret only the substituted owner
note and emit exactly one JSON object:

```json
{"tags": []}
```

The only allowed tags are `avoid_needy`, `avoid_vocal`, and
`avoid_high_energy`.

- `avoid_needy`: the owner asserts frequent travel or long absence and concern
  about a lonely or needy cat.
- `avoid_vocal`: the owner asserts a desire for quiet or an aversion to loud or
  vocal behavior.
- `avoid_high_energy`: the owner asserts a desire for a calm, mellow, low-key,
  or low-energy companion, or rejects high-energy behavior.

Each concern is classified independently, so one note may emit multiple tags.
Negation is scoped to the concern it negates: negated travel must not suppress a
separately asserted desire for quiet or calm. Do not transfer another person's
travel, absence, or preferences to the owner. Generic keyword presence is not
enough when the assertion is negated or attributed to someone else.

For a blank, irrelevant, or unclear note, emit an empty tag list. Return no
markdown, prose, or additional fields.
