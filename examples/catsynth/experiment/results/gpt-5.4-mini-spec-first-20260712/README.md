# CatSynth closed-world spec-first experiment

If the complete governing policy can be written before implementation starts,
use it. Sketch-CE is for the harder case where that premise is false.

This run gave `gpt-5.4-mini` the immutable
[`complete_spec.md`](complete_spec.md) and empty implementation files. The initial
request contained no examples. After each generated implementation, the harness
ran the complete visible gate and returned the visible failures for repair. It
stopped only when the full visible gate passed. Hidden cases were evaluated
afterward and were never repair input.

## Results

| Measure | Spec-first |
|---|---:|
| Developer calls | 4 |
| Developer repair calls | 3 |
| Developer tokens | 132,632 |
| All model tokens | 851,448 |
| Visible cases | 20/20 |
| Hidden cases | 21/21 |

The first implementation passed 11 of 21 gate cases including the initial
anchor. The next repair passed 12/21, the next passed 20/21, and the third repair
closed the final scoped-negation failure at 21/21. The separate post-acceptance
evaluation reports 20 visible cases because it excludes the initial anchor.

This is the expected headline: when the complete specification is actually
available, spec-first is the simpler frame and performed better here. It used
fewer Developer calls and tokens than any open-world path and passed every
hidden case.

That result depends on the premise. The complete spec already contains the
rules that the open-world experiment must discover through failures. It would
be misleading to treat the token difference as proof that spec-first solves
unknown policy more efficiently; it starts with the unknown policy supplied.

## Read the generations

[`generations/`](generations/) contains the initial implementation and all three
repairs. Every directory contains the complete `strategy.py`, `oracle_prompt.txt`,
and `SKETCH.md`, plus `metadata.json` with visible failures, gate outcomes, token
usage, and diffs.

[`results.json`](results.json) contains the complete compact visible and hidden
outcomes, quality metrics, token ledger, and inference controls.

## Reproduce

From `examples/catsynth`:

```bash
uv run --with-requirements requirements.txt \
  python experiment/run_experiment.py \
  --provider codex-app-server \
  --model gpt-5.4-mini \
  --spec-first \
  --max-repairs 12
```

## Claim boundary

This is one run with one model and one complete synthetic specification. It
shows what happened when the closed-world premise held for CatSynth. It does not
show that real open-world policy can always be made complete before coding.
