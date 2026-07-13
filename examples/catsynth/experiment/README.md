# CatSynth experiments

CatSynth tests two different situations, not a pile of interchangeable prompting
techniques.

## If the specification is complete, use it

The closed-world experiment starts with an immutable complete specification and
empty implementation files. GPT-5.4-mini initially passed 11/21 gate cases. Three
repair calls brought the full gate to 21/21. Post-acceptance evaluation passed
20/20 visible cases and 21/21 hidden cases.

| Measure | Spec-first |
|---|---:|
| **Tokens through visible acceptance** | **611,519** |
| Developer calls | 4 |
| Developer tokens | 132,632 |
| Runtime Oracle tokens through acceptance | 478,887 |
| Specification Oracle tokens | 0 |
| Post-acceptance evaluation tokens | 239,929 |
| Total recorded tokens, including evaluation | 851,448 |
| Visible evaluation | 20/20 |
| Hidden evaluation | 21/21 |

[Read every spec-first generation and the complete results.](results/gpt-5.4-mini-spec-first-20260712/README.md)

That is the preferred approach when the complete policy is truly available.

## If policy is discovered over time, use Sketch-CE

The open-world experiment freezes 14 proposed cases, then evaluates them in
order against the retained implementation. Eight fail and become promoted
counterexamples. Six already pass and are recorded as coverage without a
Developer call.

Sketch-CE gets the current sketch, code, prompt, and one active failure. After
each repair, the gate sees the initial anchor and all promoted cases.

Two controls help explain what retained implementation state contributes:

- **Replay all** rebuilds from the initial sketch and every promoted CE known at
  the current epoch.
- **Evolved-sketch rebuild** rebuilds from the current Sketch-CE sketch. It never
  receives the full CE corpus. If its gate fails, it receives the visible
  failure packets from that gate with the current generated files.

All three paths use the same GPT-5.4-mini model and low-effort inference controls.

| Measure | Replay all | Evolved-sketch rebuild | Sketch-CE |
|---|---:|---:|---:|
| **Tokens through visible acceptance** | **891,880** | **828,628** | **1,021,822** |
| Developer calls | 15 | 16 | 9 |
| Developer tokens | 400,081 | 371,050 | 217,576 |
| Runtime Oracle tokens through acceptance | 491,799 | 457,578 | 657,478 |
| Specification Oracle tokens | 0 | 0 | 146,768 |
| Post-acceptance evaluation tokens | 169,954 | 169,679 | 169,682 |
| Total recorded tokens, including evaluation | 1,061,834 | 998,307 | 1,191,504 |
| Extra repairs | 6 | 7 | 0 |
| Prior regressions on first attempt | 2 | 7 | 0 |
| Artifact churn lines | 2,394 | 2,326 | 719 |
| Final strategy LOC | 224 | 228 | 298 |
| Final decision nodes | 77 | 70 | 110 |
| Final changed lines from baseline | 259 | 286 | 333 |
| Visible promoted cases | 8/8 | 8/8 | 8/8 |
| Hidden cases | 15/21 | 19/21 | 18/21 |

Tokens through acceptance are the sum of Developer calls that edit the artifacts, Runtime Oracle
calls that execute prompt-mediated policy during probes and gates, and Specification Oracle calls
that propose rules from promoted failures. Post-acceptance evaluation is reported separately.

The candidate cases came from outside the system. Sketch-CE paid to classify them and propose
rules for the failures. Replay-all and evolved-sketch rebuild inherited the resulting promotion
schedule, so their totals omit candidate classification and rule proposal. The totals are real
consumption with different boundaries, not comparable end-to-end prices. Retained Sketch-CE used
less Developer work and produced less churn. Evolved-sketch rebuild had the best hidden score.
Sketch-CE's final strategy was larger and had more decision nodes than either rebuild, so the
experiment does not establish better final maintainability.

[Read every open-world generation and the complete results.](results/gpt-5.4-mini-adaptive-open-world-v2-20260712/README.md)

## What is checked in

Each generated state contains:

- the complete `SKETCH.md`;
- the complete `strategy.py`;
- the complete `oracle_prompt.txt`;
- compact metadata containing active failures, corpus IDs, expected and actual
  gate results, Developer usage, and file diffs.

The result directories also contain every discovery outcome, final visible and
hidden results, token ledgers, quality metrics, and inference settings.

Raw JSON-RPC transport transcripts remain local. They repeated the same source
files and results several times without making the causal history easier to
inspect. [`publish_experiment.py`](publish_experiment.py) creates the compact
repository record from a raw run.

## Reproduce

From `examples/catsynth`:

```bash
# Closed world
uv run --with-requirements requirements.txt \
  python experiment/run_experiment.py \
  --provider codex-app-server \
  --model gpt-5.4-mini \
  --spec-first \
  --max-repairs 12

# Open world
uv run --with-requirements requirements.txt \
  python experiment/adaptive_open_world_experiment.py \
  --model gpt-5.4-mini \
  --max-repairs 12
```

## Claim boundary

These are two runs with one model and synthetic policy. The spec-first run starts
with rules that the open-world run must infer from externally supplied failures,
so the absolute token totals answer different questions. The open-world controls
inherit the promotion schedule without paying to evaluate the candidate cases or
propose sketch changes for the failures. The results demonstrate the mechanism
and the observed trade-offs; they are not a benchmark or a universal ranking.
