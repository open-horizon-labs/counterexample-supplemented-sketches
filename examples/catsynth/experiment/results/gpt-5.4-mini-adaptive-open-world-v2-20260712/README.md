# CatSynth adaptive open-world experiment

This run asks what happens as policy is discovered over time, rather than handing
a model a complete specification up front.

It is not an argument against spec-first development. When the complete policy is
known, the separate [closed-world spec-first run](../gpt-5.4-mini-spec-first-20260712/README.md)
is the appropriate baseline and performed better. This experiment studies the
case where that complete specification is not available yet.

The candidate pool was frozen before the run. CatSynth evaluated each candidate
against the retained Sketch-CE implementation in order. A passing candidate was
recorded as coverage and never sent to Developer. A failing candidate was
promoted, sent to Developer with the current sketch, code, and prompt, and then
added to the full regression gate.

Eight of 14 candidates failed and were promoted. Six already passed and were
rejected as coverage.

## The three paths

- **Sketch-CE** retained its sketch, code, and prompt. Each promoted failure
  produced the next generation.
- **Replay all** rebuilt from the initial sketch and every promoted
  counterexample known at that epoch.
- **Evolved-sketch rebuild** rebuilt from the Sketch-CE sketch checkpoint at
  that epoch. If the full gate failed, it received the visible failures with the
  current files and repeated the gate. It never received the full
  counterexample corpus.

All three paths used `gpt-5.4-mini` at low effort with tools, environment access,
and provider fallback disabled.

## Results

| Measure | Replay all | Evolved-sketch rebuild | Sketch-CE |
|---|---:|---:|---:|
| Developer calls | 15 | 16 | 9 |
| Developer tokens | 400,081 | 371,050 | 217,576 |
| All model tokens in arm | 1,061,834 | 998,307 | 1,191,504 |
| Extra repair attempts | 6 | 7 | 0 |
| Rebuilds | 9 | 9 | 1 |
| First-attempt prior regressions | 2 | 7 | 0 |
| Artifact churn lines | 2,394 | 2,326 | 719 |
| Visible promoted cases | 8/8 | 8/8 | 8/8 |
| Hidden cases | 15/21 | 19/21 | 18/21 |

Retaining the implementation cut Developer tokens by 45.6% relative to replay
all and 41.4% relative to rebuilding from the evolved sketch. It cut artifact
churn by about 70% relative to either rebuild path and produced no extra repair
turns or first-attempt regressions.

That does not make Sketch-CE cheapest by every measure. It used the most total
model tokens because this arm paid for candidate probes, Specification-Oracle
promotion, and additional cumulative gates. The rebuild controls inherited the
stream that Sketch-CE discovered, so their totals are not independent
end-to-end discovery costs.

Evolved-sketch rebuild had the best hidden score. All three paths missed two
hidden multi-tag cases because no promoted case had yet defined the
`avoid_vocal` narrative policy. Those failures are examples of what the next
open-world counterexample could add.

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
contains the eight promoted cases. [`results.json`](results.json) contains the
complete compact visible and hidden outcomes, token ledgers, quality metrics,
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
