# CESS Working Forms

Use only the forms needed by the current repository. Preserve repository-local conventions when equivalent artifacts already exist.

## Artifact Register

```markdown
| CESS role | Repository path or system | Owner | Notes |
|---|---|---|---|
| Sketch `S` | | | |
| Anchors `K` | | | |
| Projection `P` | | | |
| CE archive `A` | | | |
| Regression set `R` | | | |
| Deterministic gate `G` | | | |
| Simulator | | | |
| Sketch reviewer | | | |
| Policy authority | | | |
```

## Sketch Skeleton

```markdown
# Sketch

## Aim and scope
[Behavior the projection must produce and boundaries it must respect.]

## Stable interfaces and anchors
[Inputs, outputs, protocols, types, and repository constraints.]

## Strategy and policy order
[General rules, precedence, invariants, and prohibited outcomes.]

## Explicit holes
[Questions or behavior intentionally left open.]

## Simulation surface
[How a reviewer can exercise and observe the compiled projection.]

## Validation obligations
[What can be checked deterministically and what requires judgment against this sketch.]
```

## Counterexample Proposal and Decision

```markdown
### CE: [stable id]

- Status: proposed | approved | rejected
- Input and simulation context:
- Projection output:
- Corrected output or behavior:
- Classification: implementation defect | missing sketch rule | mistaken sketch rule | ambiguous sketch rule
- Existing violated clause, if any:
- Proposed generalized sketch change:
- Adjacent behavior not authorized by this decision:
- Tempting wrong repair:
- Why the wrong repair is plausible:
- Deterministic assertion to add, or why none is expressible:
- Sketch review still required:
- Proposed by:
- Approved or rejected by:
- Decision rationale:
- Sketch revision reference:
- Projection revision reference:
```

Do not approve a CE whose proposed rule merely names the fixture. Require a rule that can govern
nearby unseen cases, but do not invent outcomes for neighboring conditions that the approval did
not settle. Record those as holes or ask the policy authority.

## Sketch Change Approval

```markdown
### Sketch change: [proposal id]

- Active approved CE, or `none`:
- Approved input/output fields and clause:
- Proposed general rule:
- Why that rule is required by the CE:
- Earlier rules and anchors preserved:
- Adjacent choices left open:
- Decision: approve | reject
- Decision rationale:
- Approver:
```

Absence from the previous sketch is not a rejection reason when the active approved CE entails
the rule. If `Active approved CE` is `none`, the proposal may clarify or reorganize the sketch but
must not settle an open policy question. A CE approved later does not retroactively authorize an
earlier proposal.

## Developer Change Contract

Attach this contract to every Developer request, including the first compilation:

```markdown
- Prior policy authority: current sketch
- Exact active change authority: approved CE and clause | approved corpus | authorized clarification | none
- Approved outputs and checked fields covered by that authority:
- Current rules that must be preserved:
- Explicit holes that must remain open:
- Retained CE behavior that must not regress:
- Stable projection and prompt contracts:
- Forbidden shortcuts:
- Conflict protocol: leave all files unchanged and ask the policy authority one precise question
```

The Developer may not pick a winner when these sources conflict. Record the question and the
authorized answer, then retry with that answer as the only added authority.

## Sketch Review

Give the judge the current sketch, one case, and the projection's observed output and trace. Ask it to return:

```markdown
- Verdict: pass | fail | needs-authority
- Applicable sketch clauses:
- Behavior required by those clauses:
- Difference between required and observed behavior:
- Failure class: projection defect | possible sketch gap | none
- Corrected output or behavior, if authorized:
- Proposed generalized rule, if the sketch has a gap:
- Confidence and unresolved ambiguity:
```

Do not give the judge future cases or the full CE archive merely to recover policy missing from the sketch.

If the reviewer makes a calculation or classification error, an authorized adjudicator may
correct that verdict from the sketch and case evidence. Record the correction. Adjudication
decides only whether the observed output follows the current sketch; it does not approve a new
policy rule.

## Sketch Review Adjudication

```markdown
- Case:
- Original verdict and rationale:
- Sketch clauses and case evidence:
- Adjudicated verdict: pass | fail | needs-authority
- Why the original judgment was wrong or unresolved:
- Policy change approved by this adjudication: none
- Adjudicator:
```

## Two-Check Matrix

```markdown
| Case | Active/R | Deterministic gate | Sketch review | Tempting repair rejected | Result |
|---|---|---|---|---|---|
| | | pass/fail/gap | pass/fail/needs-authority | yes/no | pass/fail/open |
```

A case passes only when both the deterministic gate and review against the current sketch pass. Resolve an encoding gap or explicitly obtain authority for why deterministic encoding is impossible; never convert a gap into a silent pass.

## Cycle Report

```markdown
## CESS Cycle [id]

- Active case:
- Classification:
- Authority decision:
- Sketch change:
- Projection change:
- Deterministic regression:
- Sketch-review obligation:
- Active-case result:
- Regression-set result:
- Tempting repair result:
- Next active failure:
- Bounded acceptance claim:
```

## Fresh-Projection Check

```markdown
- Inputs supplied to generator: sketch `S` and anchors `K`
- CE archive supplied as prompt context: no
- Projection surfaces discarded and rebuilt:
- Deterministic corpus result:
- Sketch-review corpus result:
- Policy recoverable only from archived examples:
- Sketch strengthening required:
```
