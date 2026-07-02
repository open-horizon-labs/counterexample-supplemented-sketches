# Solar-Lezama → reference implementation

Lineage map for the **roster worked example**. Headline technique: agentic synthesis against counterexample-supplemented sketches.

**Do not collapse** [marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (automated Z3 synthesis) with this repo (agentic harness). Same loop grammar; different synthesizer.

| CEGIS / sketching | [marcelwa/CEGIS](https://github.com/marcelwa/CEGIS) (Z3) | This repo (worked example) |
|-------------------|----------------------------------------------------------|----------------------------|
| Sketch | SMT impl / input / helper vars + constraints | `docs/sketch.md` |
| CE-supplemented `E` | Counterexamples accumulated in solver | `scenarios/*.json` + gate promotions (agent-authored) |
| Synthesizer | `findImplementation()` — automatic SMT search | Agent edits Oracle A: `playbook.py` |
| LLM synthesizer | — (not in classic CEGIS) | Agent edits Oracle B: `prompt.py`, cassettes |
| Hybrid | — | `resolver/hybrid.py` |
| Counterexample | `findCounterExample()` — automatic SMT search | Gate notes → promote scenario (agent step) |
| Validation | Correctness / behavior SMT constraints | `bench gate` → replay + compare |
| Convergence | No more CE or impl found | All gates pass on *E* |
| Agent environment | — | `bench gate`, `bench oracle`, `bench prompt` |

Paper: Sect. 1.1 (three-way table), Sect. 6 (CEGIS-shaped agent loop), Sect. 9 (vs automated CEGIS).

[for-researchers.md](for-researchers.md)
