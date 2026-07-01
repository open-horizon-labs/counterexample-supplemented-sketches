# Fork the technique

Agentic synthesis against counterexample-supplemented sketches transfers when you have: a sketch, structured wire output, replay + golden compare, and a scenario corpus. **RosterSynth** is one reference impl—the roster payload is the example you replace.

## Keep this skeleton

```
gate fail → promote scenario into E → edit sketch / Oracle A / Oracle B → rerun
```

| Path | Role |
|------|------|
| `docs/sketch.md` | Partial program |
| `playbook.py` | Oracle A — agent-maintained |
| `resolver/hybrid.py` | A then B on abstention / replay fail |
| `verifier.py` + `eval/comparer.py` | Replay + compare |
| `scenarios/*.json` | CE-supplemented *E* |
| `cassettes/*.json` | Oracle B for CI |
| `eval/gate.py` | Convergence check |

## Prove wiring (before you swap domains)

```bash
git clone https://github.com/open-horizon-labs/RosterSynth.git && cd RosterSynth
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
bench gate --mode deterministic    # 12/12, 2 excluded
bench gate --mode hybrid --llm cassette   # 14/14
bench gate --mode llm-only --llm cassette # 14/14
```

All green? The harness works. Now change payload schema and scenarios.

## Gate modes

| Mode | When |
|------|------|
| `deterministic` | Oracle A only; skips sketch-declared LLM holes |
| `hybrid` | Production-shaped agent path |
| `llm-only` | Ablation — B + sketch only |

```bash
bench prompt roster.kiosk_double_booking.v1   # see Oracle B prompts (example)
```

## Fork checklist

1. `models.py` + scenarios; keep manifest + gates.
2. New `docs/sketch.md` — ops, holes, abstention rules.
3. Oracle A implements encodable policy; abstain on LLM holes.
4. `requiresLlmFallback: true` on those scenarios.
5. Sync cassettes; copy `.github/workflows/ci.yml`.

## Learn on the roster example

[Session 01 — kiosk](sessions/01-kiosk-double-booking.md) · [add-a-scenario.md](add-a-scenario.md) · `bash scripts/record_session.sh`

**Use this pattern** when policy fits a sketch and gates can falsify bad rows. **Skip** when there's no replay, no golden fields, or nothing to promote into *E*.

Paper: [for-researchers.md](for-researchers.md). Bedrock: [bedrock-setup.md](bedrock-setup.md).
