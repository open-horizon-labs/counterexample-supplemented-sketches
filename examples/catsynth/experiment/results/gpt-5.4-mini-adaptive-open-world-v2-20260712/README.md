# CatSynth adaptive open-world experiment

This run asks what happens as policy is discovered over time, rather than handing
a model a complete specification up front.

It is not an argument against spec-first development. When the complete policy is
known, the separate [closed-world spec-first run](../gpt-5.4-mini-spec-first-20260712/README.md)
is the appropriate baseline and performed better. This experiment studies the
case where that complete specification is not available yet.

The candidate pool and authoritative expected outputs were frozen before the
run and treated as a simulated operator-approved stream. That frozen input is a
reproducible stand-in for the live method's explicit approval step; it does not
give the model authority to approve policy. CatSynth evaluated each candidate
against the retained Sketch-CE implementation in order. A passing candidate was
recorded as coverage and never sent to Developer. A failing candidate was
accepted only when it exposed missing policy. Developer revised the sketch with
the code and prompt. Because this run is small, every accepted CE was also added
to the regression gate (`R = A`).

Eight of 14 candidates failed and became accepted CEs in the simulated approval
stream. Six already passed and were recorded as coverage.

## The three paths

- **Sketch-CE** evolved the sketch for every accepted CE while retaining code
  and prompt between repairs.
- **Replay all** rebuilt from the initial sketch and every promoted
  counterexample known at that epoch.
- **Evolved-sketch rebuild** discarded code and prompt, then rebuilt from the
  current Sketch-CE sketch checkpoint alone. Its first Developer call received
  no counterexample corpus. If the gate failed, later repair calls received the
  visible failures with the current files.

All three paths used `gpt-5.4-mini` at low effort with tools, environment access,
and provider fallback disabled.

## Results

| Measure | Replay all | Evolved-sketch rebuild | Sketch-CE |
|---|---:|---:|---:|
| **Tokens through visible acceptance** | **891,880** | **828,628** | **1,021,822** |
| Developer calls | 15 | 16 | 9 |
| Developer tokens | 400,081 | 371,050 | 217,576 |
| Runtime Oracle calls through acceptance | 29 | 27 | 39 |
| Runtime Oracle tokens through acceptance | 491,799 | 457,578 | 657,478 |
| Specification Oracle calls | 0 | 0 | 8 |
| Specification Oracle tokens | 0 | 0 | 146,768 |
| Post-acceptance evaluation calls | 10 | 10 | 10 |
| Post-acceptance evaluation tokens | 169,954 | 169,679 | 169,682 |
| Total recorded tokens, including evaluation | 1,061,834 | 998,307 | 1,191,504 |
| Extra repair attempts | 6 | 7 | 0 |
| Rebuilds | 9 | 9 | 1 |
| First-attempt prior regressions | 2 | 7 | 0 |
| Artifact churn lines | 2,394 | 2,326 | 719 |
| Final strategy LOC | 224 | 228 | 298 |
| Final decision nodes | 77 | 70 | 110 |
| Final changed lines from baseline | 259 | 286 | 333 |
| Visible accepted CEs | 8/8 | 8/8 | 8/8 |
| Withheld cases | 15/21 | 19/21 | 18/21 |

Retaining the implementation cut Developer tokens by 45.6% relative to replay
all and 41.4% relative to rebuilding from the evolved sketch. It cut artifact
churn by about 70% relative to either rebuild path and produced no extra repair
turns or first-attempt regressions.

Tokens through visible acceptance are the sum of the Developer, Runtime Oracle, and Specification
Oracle rows. Developer calls generate or repair `SKETCH.md`, `strategy.py`, and
`oracle_prompt.txt`. Runtime Oracle calls execute Oracle B while testing the implementation.
Specification Oracle calls propose a general sketch rule for each promoted failure. The captured
run archives each returned sketch for post-hoc review; it does not simulate a second live approval
click after generation. The ledger
counts provider-reported input plus output; cached input and reasoning are included subsets, not
added again. The final visible and withheld evaluation happens after acceptance and is separated;
withheld cases are never repair input.

The 14 candidate cases were external inputs. Sketch-CE classified each against its current
implementation, then used the Specification Oracle for the eight failures. The controls received
the resulting promotion schedule and did not pay for candidate classification or rule proposal.
The recorded totals are therefore real but asymmetric: they answer what each captured path
consumed, not what three independent end-to-end systems would cost.

Replay-all and evolved-sketch rebuild test two forms of memory. Replay-all receives raw accepted
examples with the initial sketch. Evolved-sketch rebuild receives the accumulated, reviewed
policy synthesis without the example archive. In this run, the evolved sketch used fewer tokens
through acceptance, ended with fewer decision nodes, and passed 19/21 withheld cases
versus 15/21 for replay-all. It also required more repair turns and cumulative churn. One run
cannot establish that evolved sketches generally outperform raw example replay, but it shows why
the sketch is a durable method artifact rather than temporary prompt scaffolding.

All three paths missed two withheld multi-tag cases because no accepted CE had yet added the
`avoid_vocal` narrative policy to the sketch. The retained Sketch-CE path also missed one
normalized severe-allergy variant. These are candidates for the next operator-reviewed
double-loop revision.

Sketch-CE's lower cumulative churn and lack of repair regressions show that it rewrote less while
the policy evolved. They do not establish better final maintainability: its final strategy was
298 lines with 110 decision nodes, versus 224/77 for replay-all and 228/70 for evolved-sketch
rebuild. This run supports a continuity and rework claim, not a final code-quality claim.

The retained path is one implementation strategy. The evolved-sketch rebuild is the clean-room
check the method was designed to support: discard generated code, regenerate from the current
sketch, and use the regression corpus to detect what the rewrite lost.

## Read the generations

Each directory under [`arms/`](arms/) is one post-call state. It contains:

- `SKETCH.md` — the complete strategy after the call;
- `strategy.py` — the complete deterministic implementation;
- `oracle_prompt.txt` — the complete prompt-mediated implementation;
- `metadata.json` — the active failure, cumulative corpus IDs, compact gate
  outcomes, Developer token usage, and diffs from the prior state.

The Sketch-CE path has nine states: the initial generation plus one generation
for each of eight promoted counterexamples. Replay all has 15 states because six
epochs needed another repair. Evolved-sketch rebuild has 16 states because seven
epochs needed another repair.

[`discovery/`](discovery/) records the observed result for all 14 proposed cases,
including the six coverage rejections. [`promoted-corpus.json`](promoted-corpus.json)
contains the eight accepted CEs. The captured run also uses those eight as its regression corpus;
larger systems may select a smaller discriminating subset. [`results.json`](results.json) contains the
complete compact visible and withheld outcomes, token ledgers, quality metrics,
and protocol settings.

The raw Codex App Server wire transcripts are intentionally not checked in.
They duplicated the same code and outcomes several times and did not help a
reader understand how the implementation evolved.

## Reproduce

From `examples/catsynth`:

```bash
uv run --with-requirements requirements.txt \
  python experiment/adaptive_open_world_experiment.py \
  --model gpt-5.4-mini \
  --max-repairs 12
```

The raw run can be projected into this reviewable form with
[`publish_experiment.py`](../../publish_experiment.py).

## Claim boundary

This is one run with one model and one candidate order. It demonstrates the
mechanism and gives inspectable evidence for this run. It does not establish
that retained Sketch-CE always costs less, generalizes better, or produces more
correct code than rebuilding.
