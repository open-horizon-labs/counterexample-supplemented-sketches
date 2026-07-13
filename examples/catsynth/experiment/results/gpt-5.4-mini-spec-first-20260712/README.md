# CatSynth closed-world spec-first experiment

If the complete governing policy can be written before implementation starts,
use it. Sketch-CE is for the harder case where that premise is false.

This run gave `gpt-5.4-mini` the immutable
[`complete_spec.md`](complete_spec.md) and empty implementation files. The initial
request contained no examples. After each generated implementation, the harness
ran the complete visible gate and returned the visible failures for repair. It
stopped only when the full visible gate passed. Withheld cases were evaluated
afterward and were never repair input.

## Results

| Measure | Spec-first |
|---|---:|
| **Tokens through visible acceptance** | **611,519** |
| Developer calls | 4 |
| Developer repair calls | 3 |
| Developer tokens | 132,632 |
| Runtime Oracle calls through acceptance | 28 |
| Runtime Oracle tokens through acceptance | 478,887 |
| Specification Oracle calls | 0 |
| Specification Oracle tokens | 0 |
| Post-acceptance evaluation calls | 14 |
| Post-acceptance evaluation tokens | 239,929 |
| Total recorded tokens, including evaluation | 851,448 |
| Visible cases | 20/20 |
| Withheld cases | 21/21 |

The first implementation passed 11 of 21 gate cases including the initial
anchor. The next repair passed 12/21, the next passed 20/21, and the third repair
closed the final scoped-negation failure at 21/21. The separate post-acceptance
evaluation reports 20 visible cases because it excludes the initial anchor.

Tokens through visible acceptance include every model call needed to generate, repair, and run
the visible gate. Developer used 132,632 tokens; prompt-mediated Runtime Oracle checks used
478,887. The immutable complete specification needed no Specification Oracle. The final visible
and withheld-case scoring consumed another 239,929 Runtime Oracle tokens after acceptance. Provider totals
count input plus output; cached input and reasoning are included subsets, not added again.

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

[`results.json`](results.json) contains the complete compact visible and withheld
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
