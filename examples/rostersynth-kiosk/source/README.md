# Agentic Synthesis against Counterexample-Supplemented Sketches

**Paper:** [Agentic Synthesis against Counterexample-Supplemented Sketches](paper/main.pdf) · Muness Castle & Eric Rubeck

Programming with coding agents under checkable rules: hold a **sketch** (partial program) and a growing **corpus *E*** of observations accountable through gates—not chat history. When validation fails, promote the failure into *E*, edit sketch / code / prompts, rerun until green. Solar-Lezama sketching and CEGIS are lineage; the contribution is the **agentic** loop with dual oracles and replay/compare validation. This repository is a **reference implementation** only; the roster domain is a worked example.

## The idea

You want a **coding agent** (or yourself in Cursor) to implement policy-heavy fixes—post this adjustment, cancel that duplicate, pick the right date—not by free-form chat, but under rules you can **check**.

The method:

1. Write a **sketch**: a partial program that fixes *strategy* (which operations exist) and names what's still open (holes)—in prose and structure, not buried in chat history.
2. Collect **examples** of correct behavior: input payload plus the row the system should emit.
3. When something is wrong, **don't hand-wave**—add a **counterexample** to the set, tighten the sketch, and have the agent change the **code and prompts** that implement the sketch.
4. Run a **gate** over the whole set: pass/fail per case, with replay and golden compare. No green gate, not done.

That loop is **agentic synthesis against counterexample-supplemented sketches**. The sketch is *counterexample-supplemented* because the example set grows every time the gate catches a miss. Solar-Lezama's program sketching and CEGIS ([STTT 2013](https://doi.org/10.1007/s10009-012-0249-7)) are lineage; the contribution is making **agentic coding** accountable to a sketch file plus an expanding corpus—not vibes, not a one-off test.

**Why not just prompt the LLM?** Policy splits: part belongs in code the agent maintains, part in narrative only an LLM should read. The sketch says which is which. **Why not just rules?** Real failures show up as corner cases; counterexamples force the sketch and code to catch up.

---

## How it works

| Piece | Role |
|-------|------|
| **Sketch** | Partial program—the contract the agent edits |
| **Corpus *E*** | Examples; grows when gates fail |
| **Oracle A** | Code the agent writes for encodable holes |
| **Oracle B** | LLM + prompts for sketch-declared narrative holes |
| **Gate** | Replay + compare over all of *E* |

```
  Sketch + examples (E)
         │
    Agent edits sketch, code, prompts
         │
    ┌────┴────┐
    ▼         ▼
 Oracle A   Oracle B
    └────┬────┘
         ▼
   bench gate ──fail──► counterexample → refine → rerun
```

**Worked example (this clone):** synthetic workforce roster—badge hours vs scheduled hours. A kiosk double-booking shows replay passing while compare fails; the [session walkthrough](docs/sessions/01-kiosk-double-booking.md) has commands and output. Repo name `RosterSynth` is only the reference implementation label, not the technique.

---

## Where to go

| You want to… | Start |
|--------------|-------|
| Read the technique | [**paper/main.pdf**](paper/main.pdf) |
| Reproduce the paper's gate table | [docs/for-researchers.md](docs/for-researchers.md) |
| Fork the method to another domain | [docs/for-coders.md](docs/for-coders.md) |
| Example domain vocabulary | [docs/problem-explainer.md](docs/problem-explainer.md) |
| Agent session (kiosk example) | [docs/sessions/01-kiosk-double-booking.md](docs/sessions/01-kiosk-double-booking.md) |

---

## Run the reference implementation

Public clone: [github.com/open-horizon-labs/RosterSynth](https://github.com/open-horizon-labs/RosterSynth) (roster worked example, MIT).

```bash
git clone https://github.com/open-horizon-labs/RosterSynth.git
cd RosterSynth
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
bench gate --mode deterministic              # 12/12
bench gate --mode hybrid --llm cassette      # 14/14
bench gate --mode llm-only --llm cassette    # 14/14
```

No AWS for cassette gates. Optional Bedrock: [docs/bedrock-setup.md](docs/bedrock-setup.md).

---

Muness Castle & Eric Rubeck · MIT License

### Citation

> Castle, M. & Rubeck, E. *Agentic Synthesis against Counterexample-Supplemented Sketches.* 2026.

> Solar-Lezama, A. *Program Sketching.* STTT 15(5–6), 2013.
