# CatSynth Worked Example

> A second worked example for this repository, alongside
> [`../rostersynth-kiosk/`](../rostersynth-kiosk/). Where RosterSynth demonstrates
> the method through a CLI + JSON scenarios in a workforce-roster domain, CatSynth
> is a **runnable web UI** over a more relatable domain (recommending a cat breed).
> Both illustrate the same loop from the paper; the domain is only a worked example.

A small, runnable illustration of the loop from **"Agentic Synthesis against
Counterexample-Supplemented Sketches"** ([`../../paper/main.pdf`](../../paper/main.pdf)).
It swaps the paper's enterprise harness (Docker / Lambda / SQS / Bedrock) for a
**local SQLite database and a local web UI**, so you can watch the loop without any
cloud infrastructure.

## The domain

Recommend a cat breed for an owner profile. The loop is trying to build a
**golden dataset** for cat suggestions:

- **Wikipedia** is the source for cat *facts* — each breed's summary text and
  page URL are fetched once and cached into SQLite (offline afterwards).
- **Local rule tables** hold the rulesets for owner traits that don't mix with
  certain cat types (e.g. *allergies → forbid non-hypoallergenic breeds*,
  *long work hours → forbid highly social breeds*, *apartment → forbid
  high-energy breeds*).

## How the paper's pieces map here

| Paper artifact | In CatSynth |
| --- | --- |
| **Sketch S** | [`sketch/SKETCH.md`](sketch/SKETCH.md) — operations, priority order, holes, forbidden repairs |
| **Corpus E** | `golden_corpus` table — promoted counterexamples (expected output + tempting repair + violated rule) |
| **Anchors K** | `catsynth/models.py` — the `Recommendation` output shape; the generic rule evaluator |
| **Oracle A** | `catsynth/oracle_a.py` — deterministic hard-rule filter + preference ranking + abstention |
| **Oracle B** | `catsynth/oracle_b.py` — prompt-mediated narrative interpretation (pluggable LLM; deterministic mock default) |
| **Hybrid resolver** | `catsynth/resolver.py` — Oracle A first, narrative note routed to Oracle B for *soft* constraints only |
| **Gate G** | `catsynth/gate.py` — **replay** (state repair) + **semantic compare** (policy-bearing fields) |

## The worked counterexample (FR-1)

An owner wants a *"big, fluffy, affectionate lap cat"* and has allergies.

- **Tempting repair** (naive resolver): recommend **Persian** — it closes the
  "big/fluffy/affectionate" gap, so **replay accepts** it.
- **Policy** says non-hypoallergenic breeds are forbidden for allergic owners,
  so **semantic compare rejects** Persian on the `breed` field.
- **Correct repair** (policy resolver): recommend **Siberian** — also big,
  fluffy, and affectionate, but hypoallergenic.

This is the paper's core lesson in one case: *a state-valid repair can still be
a policy violation.* Replay and compare fail differently and both are needed.

## Quick start

```bash
pip install -r requirements.txt

python cli.py seed            # create + seed SQLite, cache Wikipedia facts
python cli.py gate            # policy mode -> PASS 3/3
python cli.py gate --mode naive   # tempting resolver -> FAIL (compare rejects Persian)

python cli.py serve           # open http://127.0.0.1:8000
```

Seed offline (no network) with `python cli.py seed --no-wiki`.

### Using local Ollama for Oracle B

The **Playground** tab can route the narrative note to a local
[Ollama](https://ollama.com) model instead of the mock. It auto-detects a
running server and lists installed models. Defaults are configurable:

```bash
# defaults: http://localhost:11434 and qwen2.5-coder:14b
set CATSYNTH_OLLAMA_HOST=http://localhost:11434
set CATSYNTH_OLLAMA_MODEL=qwen2.5-coder:14b
```

The **gate stays model-free**: it always uses the deterministic mock so results
are reproducible. Ollama is opt-in from the Playground only.

## The local UI

- **Review** — pick a scenario, see the owner profile and the resolver's
  proposed recommendation (toggle **policy** vs **naive**), plus the
  Wikipedia-sourced breed facts and full trace. Correct the output and
  **promote** it into the golden corpus.
- **Playground** — send an ad-hoc "fake request": build any owner profile,
  add a free-text note, and see what comes back. Oracle B can be backed by the
  deterministic **mock** or your **local Ollama** model. The card shows the
  Oracle B backend, the tags it produced, the derived soft rules, and the raw
  completion.
- **Gate** — run the gate in either mode and read the per-case replay/compare
  table (mirrors Table 2 in the paper), with a provenance log of past runs.
- **Corpus (E)** — the promoted counterexamples.
- **Rules** — the owner-trait ruleset tables (hard `forbid` / soft `discourage`).
- **Sketch (S)** — the rendered strategy document.

## Tests

```bash
python -m pytest -q
```

The tests are model-free (Oracle B uses the deterministic mock) and assert that
policy mode is E-correct while the naive resolver is caught by semantic compare
on the allergy counterexample.

## Extending the loop (another domain)

1. Replace the breed catalog + Wikipedia titles in `catsynth/seed.py`.
2. Rewrite the rule rows (the local policy tables).
3. Adjust the `Recommendation` policy fields and the replay predicate in
   `catsynth/gate.py`.
4. Update `sketch/SKETCH.md` and promote your own counterexamples.
