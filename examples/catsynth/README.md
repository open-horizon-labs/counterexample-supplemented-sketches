# CatSynth: runnable supplement and worked example

CatSynth is the concrete supplement to the [paper](../../paper/main.pdf) and its
[top-level method overview](../../README.md). The distributed paper includes the supplement as an
appendix; the same material is also available as a
[standalone CatSynth PDF](../../paper/catsynth-supplement.pdf). Those documents define the method.
CatSynth records the sketch-evolution and deterministic-gate parts of the method: a coding agent
starts from a partial sketch, changes the sketch and implementation for one approved
counterexample at a time, runs the regression gate after every change, and leaves every generated
state behind for inspection. The captured experiment predates the method's explicit requirement
to review the active case and `R` against the current sketch after each repair.

You can use CatSynth four ways:

- run the synthesis driver with Codex App Server or an OpenAI-compatible Chat Completions API;
- audit the [checked-in open-world capture](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/),
  including every generated sketch, code file, prompt, failure, gate result, and token ledger;
- inspect the [bounded 2026-08-02 two-check reruns](experiment/results/two-check-reruns-20260802/),
  which exercise the current approval and sketch-review loop;
- read the same run as a [guided epoch-by-epoch walkthrough](../../paper/catsynth-worked-example.md)
  ([PDF](../../paper/catsynth-supplement.pdf));
- open a local FastAPI and SQLite teaching UI that makes the final artifacts and gate behavior
  visible.

The cat domain and data are synthetic. They were chosen to expose the control loop, not to provide
pet-selection or medical advice.

## The experiment implements one concrete form of the method

The evolved sketch is the durable generation input. Every accepted counterexample in the
captured run changed `SKETCH.md`. The accepted archive records why it changed, and the regression
corpus tests later implementations. The code and prompt are replaceable implementation surfaces.

The current method requires two checks before revealing another candidate:

1. Run the active case and curated regression set `R` through the deterministic gate.
2. Run those cases in simulation and have a capable model or person compare their outputs with
   the current sketch.

The capture records the first check, not a separate post-repair record of the second. Its results
do not measure the complete two-check rule or the cost of sketch review.

In the originating method, a case that countered the sketch was raised to the operator. Only
explicit approval made its corrected output authoritative and allowed it to change policy.
CatSynth freezes the candidate cases and authoritative expected outputs before execution, so the
experiment simulates that approved stream rather than asking the model to approve its own rules.

CatSynth is small enough to use every accepted CE as a regression case. Its accepted archive and
regression corpus are therefore the same set: `R = A`. Larger applications can preserve the full
archive while selecting a smaller regression subset.

The retained implementation arm captured in July 2026 runs this algorithm:

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

An active, approved CE authorizes the minimum general rule required by its corrected output and
approved clause. The rule may be new to the sketch; that is the point of sketch evolution. It
does not authorize unrelated decisions. During initial generation, or when repairing an
implementation defect under an already sufficient sketch, there is no CE authority to fill an
open policy hole. A later CE cannot retroactively authorize that earlier choice.

Every CatSynth Developer call now carries a structured sketch-change contract. It names the exact
active authority, the prior sketch and retained behavior to preserve, stable code and prompt
contracts, and forbidden shortcuts. If those sources conflict or leave the authorized change
ambiguous, Developer must return the files unchanged and ask one precise question. The harness
records the operator's answer and retries; Developer does not choose which authority wins.

## Choose the experiment shape

Use spec-first when the complete governing policy can be written before implementation. Use
Sketch-CE when failures will reveal missing policy after implementation begins. Replay-all and
evolved-sketch rebuild appear below as controls for the open-world experiment; they are not
additional recommended methods.

## Run the synthesis driver yourself

The orchestration lives in ordinary Python rather than inside the model. Both model adapters
implement the same small `ChatClient` interface: list the available models, make a structured chat
call, return token usage, and close the connection.

| Driver component | Responsibility |
|---|---|
| [`experiment/run_experiment.py`](experiment/run_experiment.py) | Provider-selectable core driver. It owns the clean workspace, Developer and Oracle calls, one-failure repair loop, gates, snapshots, final evaluation, and token ledger. Its default mode runs Sketch-CE beside a one-shot-plus-repair comparison. `--spec-first` runs the closed-world path. |
| [`experiment/adaptive_open_world_experiment.py`](experiment/adaptive_open_world_experiment.py) | Wrapper for the published three-path open-world benchmark. It runs the retained Sketch-CE path, captures its promoted cases and sketch checkpoints, then replays that schedule through the two rebuild controls. |
| [`catsynth/codex_app_server.py`](catsynth/codex_app_server.py) | Codex App Server JSON-RPC adapter. Each call gets an isolated ephemeral thread at low effort with tools, environment access, approvals, and model fallback disabled. |
| [`catsynth/openai_compat.py`](catsynth/openai_compat.py) | OpenAI-compatible Chat Completions adapter. It sends strict JSON-schema output requests and normalizes the endpoint's usage fields. |
| [`cli.py`](cli.py) | Local teaching-UI driver. Its `seed`, `gate`, `suggest`, and `serve` commands inspect the finished example; they do not run Developer or edit the repository artifacts. |

The core driver performs the same bounded sequence for each accepted counterexample:

1. Copy the initial sketch and empty implementation files into a fresh run directory.
2. Ask Developer for complete replacements for `SKETCH.md`, `strategy.py`, and
   `oracle_prompt.txt`.
3. Validate the response contract and generated Python before writing the files.
4. Run the active case and every current regression.
5. If the gate fails, return one failed case with the current files to Developer and repeat.
6. Snapshot the complete files, active failure, gate result, model record, diffs, and usage for
   that generation.
7. Reveal the next candidate only after the gate passes. Run withheld evaluation only after
   visible acceptance; withheld failures never return to Developer.

The current method adds sketch review of the active case and `R` after step 5 and requires both
the gate and that review to pass before step 7. The published capture did not record that added
review, so its historical artifacts remain unchanged.

When a candidate exposes missing policy, the Specification Oracle may propose rule wording. The
checked-in case supplies the frozen corrected output and sketch clause that simulate operator
approval. The model cannot make its own proposal authoritative.

Run these commands from `examples/catsynth`. `uv` installs the pinned Python dependencies into the
command environment.

Without `uv`, create a virtual environment once, install `requirements.txt`, and run the same
Python commands without the `uv run --with-requirements requirements.txt` prefix:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Codex App Server

This requires an installed and authenticated `codex` command whose App Server exposes the model
you select:

```bash
uv run --with-requirements requirements.txt \
  python experiment/run_experiment.py \
  --provider codex-app-server \
  --model gpt-5.4-mini \
  --max-repairs 12
```

With no experiment-mode flag, `run_experiment.py` runs the one-counterexample-at-a-time Sketch-CE
path and a one-shot-plus-repair arm that receives the checked-in case corpus. Both start from the
same baseline. Add `--spec-first` to run the complete immutable specification instead.

### OpenAI or another OpenAI-compatible endpoint

Point the same driver at an endpoint that implements the API contract below. For OpenAI itself,
use its API base URL and a model ID returned by that endpoint:

```bash
CATSYNTH_LLM_API_KEY="$OPENAI_API_KEY" \
uv run --with-requirements requirements.txt \
  python experiment/run_experiment.py \
  --provider openai-compatible \
  --base-url https://api.openai.com/v1 \
  --model YOUR_MODEL_ID \
  --max-repairs 12
```

For a local compatible server, change `--base-url` and set `CATSYNTH_LLM_API_KEY` to the value it
expects. The selected model must accept this adapter's Chat Completions request: `max_tokens`,
`temperature: 0`, and strict `response_format: json_schema`. The endpoint must also implement
`GET /models` and report `prompt_tokens`, `completion_tokens`, and `total_tokens`. The driver
checks that the selected model appears in `GET /models` before starting.

The OpenAI-compatible adapter can run the portable paired harness and its spec-first and
one-shot-only modes. The published three-path wrapper currently constructs the Codex App Server
adapter directly, so it does not accept `--provider`. The portable paired harness demonstrates
the same iterative mechanism, but it does not reproduce the published three-path protocol.

### Re-run the published three-path benchmark

The captured benchmark used 173 model calls and 3,251,645 total model tokens across its three
paths, including post-acceptance evaluation. A new run can vary, but it is not a cheap smoke test.

```bash
uv run --with-requirements requirements.txt \
  python experiment/adaptive_open_world_experiment.py \
  --model gpt-5.4-mini \
  --max-repairs 12
```

Each command prints its new directory under `experiment/artifacts/`. A raw run contains
`report.json`, a readable `REPORT.md`, the final workspace for each path, and a generation
directory for every Developer call. Each generation preserves the complete sketch, strategy,
prompt, active failure, corpus state, gate result, request and response record, diffs, and usage.

## How the captured open-world benchmark works

Here, *benchmark* means a frozen, reproducible comparison inside this synthetic example. It is not
a general model or methodology ranking.

The checked-in benchmark is
[`experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/`](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/).
It used Codex App Server with `gpt-5.4-mini` at low effort. Tools, environment access, summaries,
personality, and model fallback were disabled.

Before execution, the harness froze the order of 14 candidate cases and their corrected outputs,
reviewer policies, and sketch clauses. The retained Sketch-CE implementation evaluated them in
that order. Eight failed and became accepted counterexamples; six passed and were recorded as
coverage without a Developer call. The harness then replayed the same eight promotions through
two controls:

- **Replay-all** rebuilt from the initial sketch and the complete accepted-example history at
  each epoch.
- **Evolved-sketch rebuild** rebuilt from the current reviewed sketch without receiving the
  accepted-example archive in its first call. A later repair call received visible gate failures
  only when the rebuild failed.
- **Sketch-CE with retained code** evolved the sketch for one active counterexample at a time and
  kept the generated code and prompt between epochs.

The controls isolate what the evolved sketch carries and what preserving implementation state
contributes. CatSynth uses every accepted CE as a regression in this run, so `R = A`.

## Historical deterministic-only benchmark

This July 2026 table predates separate sketch review and approval on every repair. Its withheld
scores are not results for the current CESS method. The table remains for reproducibility and for
its measured calls, tokens, repairs, and churn. The current withheld result is the
protocol-correct rerun below.

| Measure | Replay-all | Evolved-sketch rebuild | Sketch-CE (retained code) |
|---|---:|---:|---:|
| **All recorded model tokens, including evaluation** | **1,061,834** | **998,307** | **1,191,504** |
| Tokens through visible acceptance | 891,880 | 828,628 | 1,021,822 |
| Post-acceptance evaluation tokens | 169,954 | 169,679 | 169,682 |
| Developer calls | 15 | 16 | 9 |
| Developer tokens | 400,081 | 371,050 | 217,576 |
| Runtime Oracle tokens through acceptance | 491,799 | 457,578 | 657,478 |
| Specification Oracle tokens | 0 | 0 | 146,768 |
| Rebuilds | 9 | 9 | 1 |
| Extra repair attempts | 6 | 7 | 0 |
| Prior regressions on first attempt | 2 | 7 | 0 |
| Artifact churn lines | 2,394 | 2,326 | 719 |
| Accepted CE evaluation | 8/8 | 8/8 | 8/8 |
| Withheld evaluation | 15/21 | 19/21 | 18/21 |
| Final strategy LOC | 224 | 228 | 298 |
| Final decision nodes | 77 | 70 | 110 |
| Final changed lines from baseline | 259 | 286 | 333 |

The first row is the broadest recorded total. It includes Developer, Runtime Oracle,
Specification Oracle, and post-acceptance evaluation calls. Provider totals count input plus
output; cached input and reasoning are subsets, not additional tokens.

The paths do not pay for the same work. Sketch-CE paid to evaluate the external candidate stream
and ask the Specification Oracle for proposed rules when a candidate failed. Both controls
inherited the resulting promotion schedule, and evolved-sketch rebuild also inherited the sketch
checkpoints. Their totals omit discovery work. The table reports real usage, but it is not an
end-to-end price comparison.

This capture provides three historical diagnostics:

- **Its withheld pattern motivated the two-check rerun; it is not the current headline.**
  Evolved-sketch rebuild passed 19/21 withheld cases, compared with 15/21 for Replay-all. Because
  this capture lacked required sketch review and approval, those scores cannot support a claim
  about the current two-check method.
- **Retaining code reduced Developer work and cumulative churn.** Sketch-CE with retained code
  used 9 Developer calls, 217,576 Developer tokens, and 719 lines of cumulative artifact churn.
  It needed no extra repairs and regressed no earlier case on a first attempt.
- **The retained path did not win every measure.** Its reported all-model total was largest, and
  it was the only path whose accounting included discovery. Its final strategy also had the most
  lines and decision nodes. The run shows continuity and lower rework, not better final
  maintainability.

One model, one reveal order, and one frozen suite cannot establish a general advantage. Read the
[guided walkthrough](../../paper/catsynth-worked-example.md)
([PDF](../../paper/catsynth-supplement.pdf)) for the epoch-by-epoch story, or audit the
[checked-in capture](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/). The
[results JSON](experiment/results/gpt-5.4-mini-adaptive-open-world-v2-20260712/results.json)
contains the machine-readable aggregate.

## Protocol-correct two-check result

On 2026-08-02, the mini arm was completed with both acceptance checks, manual approval of every
sketch change, adjudication of non-pass review verdicts, and an explicit authority-and-
preservation contract in every Developer prompt.

| Evaluation | Replay-all | Evolved-sketch rebuild | Sketch-CE (retained code) |
|---|---:|---:|---:|
| Visible accepted cases | 8/8 | 8/8 | 8/8 |
| Withheld cases | 14/21 | 17/21 | 16/21 |

The evolved sketch beat raw replay by three withheld cases. Retaining the implementation did not
beat clean regeneration from the reviewed sketch in this sample. These scores replace the old
19/21-versus-15/21 headline for claims about the current two-check method; they do not replace
the historical run's measured token and churn totals.

## The closed-world control

The separate spec-first run gave Developer the complete immutable specification and empty files.
The first generation passed 11/21 gate cases. Three repair calls reached 21/21. Post-acceptance
evaluation passed 20/20 visible cases and 21/21 withheld cases. The path used 611,519 model tokens
through acceptance and 851,448 including evaluation.

That is the better path when the complete governing policy really is available. Inspect the
[spec-first generations and results](experiment/results/gpt-5.4-mini-spec-first-20260712/README.md).

## Inspect every generated state

The checked-in benchmark preserves every complete `SKETCH.md`, `strategy.py`, and
`oracle_prompt.txt`, plus compact active-failure, gate, usage, and diff metadata. Raw transport
transcripts are omitted from the published copy because they repeat the same source files and
results. [`experiment/publish_experiment.py`](experiment/publish_experiment.py) produces this
compact record from a raw run.

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
uv run --with-requirements requirements.txt python cli.py seed --no-wiki
uv run --with-requirements requirements.txt python cli.py serve
```

Open <http://127.0.0.1:8000>.

The browser exposes:

- **Review** — compare policy and naive recommendations for a scenario;
- **CEs (A = R)** — inspect approved outputs, tempting outputs, and sketch links;
- **Rules** — inspect hard `forbid` and soft `discourage` rows;
- **Sketch** — read the finished human-facing strategy;
- **Gate** — run replay and approved-output compare separately;
- **Playground** — exercise runtime Oracle B through the deterministic mock or an
  environment-configured OpenAI-compatible endpoint.

The browser is an inspection surface, not the synthesis harness. Its Review action records a
local operator decision in SQLite so the gate behavior can be explored; it does not call
Developer or revise repository files. The captured experiment is the evidence that each accepted
CE changed the sketch and implementation.

The Playground defaults to the deterministic mock. To use an API for runtime Oracle B, set
`CATSYNTH_LLM_BASE_URL`, `CATSYNTH_LLM_MODEL`, and `CATSYNTH_LLM_API_KEY` before starting the
server. This changes Playground inference only; it does not turn the UI into the synthesis
driver.

The UI's focal allergy case makes the two gate predicates visible. A preference-only resolver
chooses Persian. Replay accepts the visible size, affection, and fluffiness match.
Approved-output compare rejects the choice because the approved output is Siberian with the hard
allergy rule cited. The captured screenshot and historical UI data may still use the original
label “semantic compare.”

The SQLite database is only a runtime projection. Delete `catsynth.db` and rerun
`uv run --with-requirements requirements.txt python cli.py seed --no-wiki` to reconstruct it from
`catsynth/seed.py`.

## Repository map

| Method artifact | File |
|---|---|
| Initial sketch | [`experiment/initial_sketch.md`](experiment/initial_sketch.md) |
| Frozen candidate pool and reveal order | [`experiment/adaptive_candidate_manifest.json`](experiment/adaptive_candidate_manifest.json) |
| Simulated operator references | Frozen expected outputs, reviewer policies, and sketch clauses in [`experiment/cases.json`](experiment/cases.json) |
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
| App replay and approved-output compare | [`catsynth/gate.py`](catsynth/gate.py) |
| Synthetic fixtures and UI corpus | [`catsynth/seed.py`](catsynth/seed.py) |
| Teaching-UI command driver | [`cli.py`](cli.py) |
| Browser app | [`catsynth/app.py`](catsynth/app.py) and [`catsynth/static/`](catsynth/static/) |

## Tests

```bash
uv run --with-requirements requirements.txt \
  python -m unittest discover -s tests -v
```

The orchestration tests assert the method, not just the final outputs. They check that a failed
initial generation is repaired before CE1, a passing proposal is rejected as coverage, each
Developer repair receives one active failure rather than the full corpus, snapshots contain the
complete evolving files, and the gate includes the initial anchor plus every promoted case.
That final assertion describes CatSynth's `R = A` experiment design, not a requirement that every
system retain every archived CE as a regression test.

The app tests use the deterministic runtime Oracle so they remain model-free.

## Claim boundary

A green gate covers the checked regression corpus under the current fixtures and evaluators. The
21 withheld cases add variants to this one captured experiment; they do not turn the result into
a universal claim. Incorrect fixtures, incorrect expected outputs, checker bugs, unseen policy,
different models, and different reveal orders remain outside the evidence. The capture also does
not evaluate the current method's separate sketch-review requirement.
