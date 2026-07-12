# CatSynth Sketch (S)

> The sketch is the human's current *strategy*: which operations exist, which
> repair wins when several close the same gap, which fields are policy-bearing,
> which decisions are deterministic code (Oracle A) vs. prompt-mediated
> narrative completion (Oracle B), and which cases force abstention. It is
> deliberately less formal than a full specification. It changes when a promoted
> counterexample reveals missing policy.

## Task

Given an **owner profile** (traits + preferences, and sometimes a free-text
note), produce a **recommendation**: recommend a specific cat breed, abstain, or
escalate.

## Operations (and priority order)

The resolver chooses exactly one operation per scenario. When more than one
repair could close the same visible gap, higher-priority operations win:

1. **ABSTAIN** — if *no* breed survives the hard rules, decline. Never recommend
   a breed that violates a hard rule just to fill the gap. (Highest priority:
   safety/welfare beats preference satisfaction.)
2. **RECOMMEND** — among breeds that survive all hard rules, pick the one that
   best matches the owner's preferences, breaking ties by fewest soft-rule
   (discourage) violations.
3. **ESCALATE** — reserved for out-of-scope inputs (a hole; not yet exercised).

**Priority clause (the load-bearing rule):** *preference match never overrides
a hard rule.* A high-preference breed that violates a hard rule is a **forbidden
repair**, even though it "closes the gap" of finding an attractive cat.

## Policy-bearing fields (what semantic compare checks)

- `operation` — recommend / abstain / escalate
- `breed` — the selected breed name (null unless recommending)
- `cited_rules` — the rule ids the decision respected/invoked

All other fields on a recommendation (`rationale`, `oracle`, `trace`) are
diagnostic and are **not** compared.

## State gap (what replay checks)

The owner starts with no suitable suggestion. Replay accepts a candidate when:

- it RECOMMENDs a real breed that satisfies the owner's stated **preferences**
  (size / affection / fluffy), **or**
- it ABSTAINs *and* no breed in the catalog satisfies the hard rules.

Replay is about closing the state gap ("did we produce a preference-satisfying
suggestion, or correctly decline?"). It does **not** by itself catch a
preference-satisfying breed that violates policy — that is compare's job.

## Holes

- **Oracle A (deterministic code):** load breeds, evaluate the local rule
  tables (hard `forbid` + soft `discourage`), filter, rank by preference match,
  abstain when the survivor set is empty. All hard-rule enforcement lives here.
- **Oracle B (prompt-mediated):** interpret the free-text `narrative_note` into
  *additional soft constraints only*. Oracle B may never relax a hard rule. Its
  output is re-checked by the same gate.
- **Hybrid resolver:** run Oracle A on structured traits first. If a narrative
  note exists, route it to Oracle B to derive extra soft constraints, then let
  Oracle A finalize the ranking. Deterministic policy stays on the reliable path.

## Abstention rule

If the hard-rule filter empties the candidate set, ABSTAIN with the ids of the
rules that eliminated the last candidates. Do not widen the search by dropping a
hard rule.

## Forbidden repairs (promoted)

### FR-1 — allergy override (from counterexample `allergy_lapcat`)

When the owner has allergies (`mild` or `severe`), recommending a
non-hypoallergenic breed is **forbidden**, even if it is the best preference
match (e.g. owner wants a "big fluffy affectionate lap cat" and Persian/Maine
Coon score highest). The tempting repair recommends **Persian** — it closes the
"big/fluffy/affectionate" gap and passes replay — but violates rule
`allergy_requires_hypoallergenic`. The correct repair recommends **Siberian**
(also big/fluffy/affectionate, but hypoallergenic), citing the allergy rule.

*Compare rejects Persian on the `breed` field; replay would have accepted it.*

## Known-code anchors (K)

- Output shape is `catsynth.models.Recommendation` with policy fields
  `{operation, breed, cited_rules}`.
- Rules live in the `rules` SQLite table and are evaluated generically by
  `oracle_a.evaluate_rules`; do not hard-code a second rule engine.
- Levels use the `LEVELS` / `SIZES` ordinal maps in `models.py`.
