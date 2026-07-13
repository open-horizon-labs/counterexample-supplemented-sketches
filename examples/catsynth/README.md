# CatSynth

CatSynth is the executable example for *Agentic Synthesis against
Counterexample-Supplemented Sketches*. It has two connected parts:

- an agentic experiment that starts from a sketch and empty implementation, reveals one
  counterexample at a time, and archives every generated sketch, code file, prompt, and gate;
- a local FastAPI and SQLite teaching UI that makes the finished method artifacts visible.

The data is synthetic and chosen to expose the control loop. It is not pet-selection or medical
advice.

## The experiment implements one concrete form of the method

The durable output is the evolved sketch. Every accepted counterexample in the captured run
changed `SKETCH.md`. The code and prompt changed under that sketch, but they are replaceable
implementation surfaces.

In the originating method, a case that countered the sketch was raised to the operator. Only
explicit approval made its corrected output authoritative and allowed it to change policy.
CatSynth freezes the candidate cases and authoritative expected outputs before execution, so the
experiment simulates that approved stream rather than asking the model to approve its own rules.

CatSynth is small enough to use every accepted CE as a regression case. Its accepted archive and
regression corpus are therefore the same set: `R = A`. Larger applications can preserve the full
archive while selecting a smaller regression subset.

The retained implementation arm runs this algorithm:

```text
generate sketch + code + prompt from the initial sketch
run the initial acceptance gate
while the initial gate fails:
    send that one failure and the current files to Developer
    regenerate sketch + code + prompt
    rerun the initial gate

for each proposed counterexample, in reveal order:
    run it against the current implementation
    reject it as coverage if it already passes
    propose it as a CE only if it fails and exposes missing policy
    apply the frozen operator decision; only an approved case becomes a CE
    active_failure = the newly promoted counterexample
    while the full gate fails:
        send active_failure and the current files to Developer
        require a revised sketch plus repaired code and prompt
        run the initial anchor plus every promoted counterexample
        active_failure = one failed regression, if any
```

Developer returns all three evolving files:

- `SKETCH.md` — the current strategy and policy;
- `strategy.py` — deterministic implementation;
- `oracle_prompt.txt` — prompt-mediated narrative implementation.

Developer receives exactly one active failure during an iterative repair. It does not receive
the archive, regression corpus, or unrevealed cases as prompt context. The gate evaluates the
active case and CatSynth's regression corpus after every revision.

The distinction matters: counterexamples teach the sketch; regression cases test generated code.
CatSynth happens to retain every accepted CE in the gate, but the method does not require an
ever-growing example prompt or a regression test for every archived case.

## Closed world versus open world

If the complete governing policy can be written before implementation, use spec-first. The
captured `gpt-5.4-mini` spec-first run reached 20/20 visible and passed 21/21 withheld cases with 4
Developer calls and 611,519 model tokens through visible acceptance: 132,632 for Developer and
478,887 for Runtime Oracle checks.

Use Sketch-CE when that complete specification is not available because policy is still being
discovered. Replay-all and evolved-sketch rebuild are experimental controls for that open-world
case, not separate headline methods.

- [Closed-world spec-first generations and results](experiment/results/gpt-5.4-mini-spec-first-20260712/README.md)
- [Open-world Sketch-CE comparison](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/README.md)

## Reproduce a new run

Run the adaptive three-path comparison with the Codex App Server backend:

```bash
uv run --with-requirements requirements.txt \
python experiment/adaptive_open_world_experiment.py \
  --model gpt-5.4-mini \
  --max-repairs 12
```

The adapter uses low effort, no summary, no tools, a read-only environment, no model fallback,
and one ephemeral thread for each Oracle or Developer call.

Use an OpenAI-compatible endpoint by selecting the other backend:

```bash
CATSYNTH_LLM_API_KEY=local \
python3 experiment/run_experiment.py \
  --provider openai-compatible \
  --base-url http://127.0.0.1:8080/v1 \
  --model your-served-model
```

The endpoint must provide model listing, Chat Completions, JSON-schema structured output, and
token usage.

## Read the captured run

The published run is
[`experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/`](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/).

The pool contained 14 candidate cases with frozen authoritative expected outputs. The harness
treated them as a simulated operator-approved stream. Eight failed and were promoted; six
already passed and were recorded as coverage without a Developer call. The same eight-case
discovery stream was then evaluated through replay-all and evolved-sketch rebuild controls.

| Measure | Replay all | Evolved-sketch rebuild | Sketch-CE |
|---|---:|---:|---:|
| **Tokens through visible acceptance** | **891,880** | **828,628** | **1,021,822** |
| Developer calls | 15 | 16 | 9 |
| Developer tokens | 400,081 | 371,050 | 217,576 |
| Runtime Oracle tokens through acceptance | 491,799 | 457,578 | 657,478 |
| Specification Oracle tokens | 0 | 0 | 146,768 |
| Post-acceptance evaluation tokens | 169,954 | 169,679 | 169,682 |
| Total recorded tokens, including evaluation | 1,061,834 | 998,307 | 1,191,504 |
| Extra repair attempts | 6 | 7 | 0 |
| Artifact churn lines | 2,394 | 2,326 | 719 |
| Final strategy LOC | 224 | 228 | 298 |
| Final decision nodes | 77 | 70 | 110 |
| Final changed lines from baseline | 259 | 286 | 333 |
| Visible accepted CEs | 8/8 | 8/8 | 8/8 |
| Withheld cases | 15/21 | 19/21 | 18/21 |

Every generation directory contains the complete `SKETCH.md`, `strategy.py`, and
`oracle_prompt.txt`, plus compact failure, gate, usage, and diff metadata. The repository does
not include repeated transport transcripts.

Tokens through acceptance include every Developer, Runtime Oracle, and Specification Oracle call
before the visible gate passed. Post-acceptance visible and withheld evaluation is separate; the
withheld cases are never repair input. Cached
input and reasoning are included subsets of the provider's input/output total, not extra tokens.

The candidate cases were external inputs. Sketch-CE paid to classify them and propose general
sketch revisions; the controls inherited the resulting promotion schedule. Their totals therefore
have different boundaries and are not clean end-to-end prices.

Replay-all and evolved-sketch rebuild test two different forms of memory. Replay-all receives the
initial sketch plus every accepted example and must infer the policy again. Evolved-sketch rebuild
receives only the reviewed synthesis of those examples. In this run, evolved-sketch rebuild used
fewer tokens through acceptance, had fewer final decision nodes, and passed 19/21 withheld cases
pass rate versus 15/21 for replay-all. It also required more repair turns and cumulative churn.
This is one run, but it supports the hypothesis that an evolved policy synthesis can generalize
better than repeatedly replaying the raw example history.

Retaining state used less Developer work, incurred less cumulative churn, and had no extra repairs
or prior regressions. Its final strategy was the largest and most branch-heavy, so that result
shows less rework, not better final maintainability. Read the [experiment overview](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/README.md)
for the design, results, and claim boundary.

## What the accepted counterexamples add

### CE1: filter hard policy before ranking

The initial implementation recommends Persian to an owner with mild allergies. The accepted
case requires Siberian and cites `allergy_requires_hypoallergenic`. Developer updates the sketch
and generic rule evaluator so applicable hard `forbid` rows remove candidates before preference
ranking.

### CE2: compose hard rules and abstain

The next profile activates five hard rules and leaves no surviving breed. The current strategy
still recommends Balinese and cites only the earlier allergy rule. Developer extends the sketch
and code to evaluate the additional generic operators, compose all applicable hard rules, and
return `abstain` with every applicable rule ID.

### CE3: teach the prompt one controlled tag

The next profile contains travel and loneliness only in a narrative note. The current prompt
returns no tags. CE3 compares only `oracle_tags`: Developer teaches the prompt to emit exactly
`avoid_needy` and records that classification in the sketch. The tag's deterministic effect
remains an explicit policy hole. The full gate passes 4/4.

### CE4: make the tag affect ranking without inventing policy

After CE3, the prompt emits `avoid_needy`, but the strategy still recommends Balinese. CE4 is a
new counterexample: the tag applies a one-point soft penalty to highly social breeds, and base
preference scoring must continue to use only the explicit `wants_*` fields. Developer removes
unauthorized scoring from default activity/noise traits, implements the penalty, and returns
Persian. The complete gate passes 5/5.

### CE6: compose distinct soft rules

The implementation handled one discourage rule but not the combined ranking effect of several
different soft predicates. CE6 makes all applicable soft adjustments contribute before the
final tie-break.

### CE7: deduplicate one concern across two surfaces

A structured discourage row and the narrative tag `avoid_high_energy` can express the same
policy. CE7 requires one semantic penalty rather than counting the concern twice.

### CE10: escalate when safety data is unknown

An allergy value outside `none`, `mild`, or `severe` is not equivalent to no allergy. CE10 makes
the strategy ask for clarification instead of guessing.

### CE12: expose malformed applicable policy

An applicable policy row with an unsupported operator cannot be ignored. CE12 requires
`escalate` and cites the malformed rule so a reviewer can repair the policy source.

## Run the teaching UI

```bash
python3 cli.py seed --no-wiki
python3 cli.py serve
```

Open <http://127.0.0.1:8000>.

The browser exposes:

- **Review** — compare policy and naive recommendations for a scenario;
- **CEs (A = R)** — inspect approved outputs, tempting outputs, and sketch links;
- **Rules** — inspect hard `forbid` and soft `discourage` rows;
- **Sketch** — read the finished human-facing strategy;
- **Gate** — run replay and semantic compare separately;
- **Playground** — exercise the runtime Oracle B through the deterministic mock or a selectable
  OpenAI-compatible endpoint.

The browser is an inspection surface, not the synthesis harness. Its Review action records a
local operator decision in SQLite so the gate behavior can be explored; it does not call
Developer or revise repository files. The captured experiment is the evidence that each accepted
CE changed the sketch and implementation.

The UI's focal allergy case makes the two gate predicates visible. A preference-only resolver
chooses Persian. Replay accepts the visible size, affection, and fluffiness match. Semantic
compare rejects the choice because the approved output is Siberian with the hard allergy rule
cited.

The SQLite database is only a runtime projection. Delete `catsynth.db` and rerun
`python3 cli.py seed --no-wiki` to reconstruct it from `catsynth/seed.py`.

## Repository map

| Method artifact | File |
|---|---|
| Initial sketch | [`experiment/initial_sketch.md`](experiment/initial_sketch.md) |
| Counterexample reveal schedule | [`experiment/cases.json`](experiment/cases.json) |
| Simulated operator decisions | Frozen expected outputs and promotion criteria in [`experiment/cases.json`](experiment/cases.json) |
| Accepted CE archive | [`promoted-corpus.json`](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/promoted-corpus.json) |
| Regression corpus (`R = A` in this run) | [`promoted-corpus.json`](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/promoted-corpus.json) |
| Sketch-CE loop | [`experiment/run_experiment.py`](experiment/run_experiment.py) |
| Adaptive three-path comparison | [`experiment/adaptive_open_world_experiment.py`](experiment/adaptive_open_world_experiment.py) |
| Published generations and results | [`experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/`](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/) |
| Clean-room baseline | [`experiment/baseline/`](experiment/baseline/) |
| Codex App Server transport | [`catsynth/codex_app_server.py`](catsynth/codex_app_server.py) |
| OpenAI-compatible transport | [`catsynth/openai_compat.py`](catsynth/openai_compat.py) |
| Reference deterministic policy | [`catsynth/oracle_a.py`](catsynth/oracle_a.py) |
| Runtime narrative Oracle | [`catsynth/oracle_b.py`](catsynth/oracle_b.py) |
| App replay and semantic compare | [`catsynth/gate.py`](catsynth/gate.py) |
| Synthetic fixtures and UI corpus | [`catsynth/seed.py`](catsynth/seed.py) |
| Browser app | [`catsynth/app.py`](catsynth/app.py) and [`catsynth/static/`](catsynth/static/) |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The orchestration tests assert the method, not just the final outputs. They check that a failed
initial generation is repaired before CE1, a passing proposal is rejected as coverage, each
Developer repair receives one active failure rather than the full corpus, snapshots contain the
complete evolving files, and the gate includes the initial anchor plus every promoted case.
That final assertion describes CatSynth's `R = A` experiment design, not a requirement that every
system retain every archived CE as a regression test.

The app tests use the deterministic runtime Oracle so they remain model-free.

## Claim boundary

A green gate covers the checked regression corpus under the current fixtures and evaluators. The 21 hidden
cases add withheld variants to this one experiment, but they do not turn the result into a
universal claim. Incorrect fixtures, incorrect expected outputs, checker bugs, unseen policy,
different models, and different reveal orders remain outside the evidence.
