# For researchers

**Paper:** [Agentic Synthesis against Counterexample-Supplemented Sketches](../paper/main.pdf)  
**Repo:** reference implementation; roster domain = worked example.

## tl;dr

Read the paper, then run three cassette gates. **12/12 / 14/14 / 14/14** means Sect. 8's table matches your machine. If a line fails, stdout names scenario + field—that's the counterexample signal.

## The claim (one paragraph)

Program with agents **inside** a constraint environment: sketch file + CE-supplemented *E* + `bench gate` over replay and compare. The agent (or you) edits sketch, Oracle A code, and Oracle B prompts until gates pass. Dual oracles and hybrid escalation are wiring inside that loop. Solar-Lezama is lineage, not the headline.

## Paper outline

| § | Topic |
|---|--------|
| 1 | Introduction (+ relation to algorithmic CEGIS) |
| 2 | Constraint environment |
| 3–4 | Sketch & semantics (worked example) |
| 5–6 | Resolution & CEGIS-shaped agent loop |
| 7 | Validation |
| 8 | Experience — gate table |
| 9 | vs unconstrained agents & automated CEGIS (Z3) |
| 10 | Kiosk counterexample promotion (example) |
| 11 | Conclusions |

## Reproduce Sect. 8

```bash
pip install -e ".[dev]"
pytest -q
bench gate --mode deterministic
bench gate --mode hybrid --llm cassette
bench gate --mode llm-only --llm cassette
```

No AWS. Term map: [cegis-mapping.md](cegis-mapping.md). Fork: [for-coders.md](for-coders.md). Example session: [sessions/01-kiosk-double-booking.md](sessions/01-kiosk-double-booking.md).
