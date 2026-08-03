# CatSynth two-check reruns, 2026-08-02

These exploratory runs exercised the current CESS harness: deterministic replay and
approved-output comparison, separate review of simulated outputs against the sketch, explicit
approval of every sketch change, and recorded adjudication when the sketch reviewer made a
calculation or classification error.

The mini continuation completed the full three-path benchmark after the harness began placing the
exact change authority and preservation requirements in every Developer prompt. The Spark run
remains a bounded failure record, not a model ranking.

| Model | Progress | Terminal condition | Sketch decisions | Adjudicated sketch reviews |
|---|---|---|---:|---:|
| `gpt-5.4-mini` | Full three-path visible and withheld evaluation completed by continuation. | Complete: replay 14/21, evolved-sketch 17/21, retained Sketch-CE 16/21 withheld; all passed 8/8 visible. | Recorded in raw continuation artifacts | Recorded in raw continuation artifacts |
| `gpt-5.3-codex-spark` | Iterative evolution reached CE-012. Rebuild controls were not reached. | CE-012 remained open after 24 repairs. | 9 approve, 17 reject | 7 pass, 1 fail, 1 needs-authority |

The initial mini wrapper stopped at replay-all epoch 5 because its 24-repair safety bound was
mistaken for experiment completion. The continuation removed that arbitrary stopping condition,
added the always-present Developer change contract, completed replay epoch 8 and all evolved-
sketch epochs, and then evaluated all three final workspaces. Spark retained the incremental
clauses through CE-011, but its final CE-012 proposals omitted required parts of the approved
malformed-rule policy: trigger-first applicability, `operation=escalate`, `breed=null`, and
citation of every invalid applicable row.

### Completed mini evaluation

| Evaluation | Replay-all | Evolved-sketch rebuild | Sketch-CE (retained code) |
|---|---:|---:|---:|
| Visible accepted cases | 8/8 | 8/8 | 8/8 |
| Withheld cases | 14/21 | 17/21 | 16/21 |

The evolved sketch preserved the directional advantage over replay, but the margin is three
cases under the current protocol, not the historical four-case 19/21-versus-15/21 result.
Retaining code finished between the two controls.

## What the clarification changed

The original capture asked Developer to repair code, prompt, and sketch, but it did not give
Developer a per-call statement of what the sketch was allowed to change or what it had to keep.
It also did not review each proposed sketch change before the next gate. That means the old record
can show whether generated code passed its deterministic checks; it cannot show how many
unsupported policy choices would have entered the sketch if someone had approved the draft.

The corrected harness gives Developer four things on every call: the current sketch as prior
authority, the exact CE/corpus/clarification that may change it, the rules and holes that must
survive, and a conflict rule. If those sources disagree or do not settle a choice, Developer must
return unchanged files and ask one question. The approver then judges the proposed sketch change
before validation proceeds.

That changed observable CatSynth behavior:

| Proposal or behavior | Old deterministic-only capture | Two-check run |
|---|---|---|
| Empty catalog before CE11 | An early output choice could make the later empty-catalog case look like coverage rather than a new CE. | Drafts that assigned `escalate` before CE11 were rejected. CE11 later authorized `escalate` for absent input, while CE2 continued to authorize `abstain` for a non-empty catalog exhausted by hard rules. |
| `avoid_needy` after CE3 | The record did not make a proposal-time distinction between learning the tag and deciding its ranking effect. | Drafts had to leave the tag's deterministic meaning open after CE3. CE4 alone authorized the one-point high-sociability penalty. |
| Existing sketch anchors | A passing deterministic implementation could accompany a rewrite that quietly dropped stable shapes or open-hole language. | We rejected rewrites that dropped the initial input-shape anchors or replaced an unresolved hole with a new operation. |
| Reviewer mistakes | The old protocol had no independent sketch review to expose them. | The reviewer repeatedly miscomputed CatSynth scores and hard-rule composition. Adjudication kept correct outputs from being turned into needless sketch changes, while retaining real failures such as a missing CE1 citation and a missing `avoid_needy` tag. |

This is not evidence that the new harness makes Developer aligned. It is evidence that the method
moves policy drift from an invisible side effect of a passing repair into a visible proposal that
can be accepted, rejected, or clarified.

Muness Castle delegated sketch-change approval to Codex for these runs. A proposal was approved
when it stated the minimum general rule entailed by the active approved CE while preserving prior
rules and open holes. A rule was not treated as invented merely because it was absent from the
old sketch. Proposals were rejected when they erased prior clauses, omitted part of the active
CE, or settled adjacent behavior the CE did not decide. During initial generation no CE was
active, so existing holes remained authoritative.

The approval and adjudication counts are workflow events, not quality scores. Multiple rejected
drafts can concern the same policy clause. A sketch-review adjudication corrects a review verdict;
it does not approve policy.

The raw run directories remain local under `experiment/artifacts/` because they contain hundreds
of megabytes of transport and generation records. This compact record preserves the terminal
conditions and interpretation needed to reproduce or compare later runs.

Run the same bounded harness from `examples/catsynth`:

```bash
uv run --with-requirements requirements.txt \
  python experiment/adaptive_open_world_experiment.py \
  --model MODEL_ID \
  --max-repairs 24
```
