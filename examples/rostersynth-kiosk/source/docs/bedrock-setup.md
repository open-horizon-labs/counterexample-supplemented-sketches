# Bedrock (optional)

CI gates use **cassettes only**—no AWS. This page is for live Oracle B or recording cassettes after sketch/prompt edits on the roster example.

One smoke oracle run tells you if SSO + model ARN work before you record the corpus:

```bash
bench oracle roster.kiosk_double_booking.v1 --llm bedrock
```

Expect `modify` on `bookingId` **1802**. Wrong op or empty tool → fix credentials/ARN/prompt first.

## Setup

```bash
pip install -e ".[dev]"
aws sso login --profile review
cp .env.example .env && set -a && source .env && set +a
```

| Variable | Purpose |
|----------|---------|
| `AWS_PROFILE` / `ROSTERSYNTH_AWS_PROFILE` | SSO profile (`review`) |
| `ROSTERSYNTH_BEDROCK_MODEL_ID` | Inference profile ARN |
| `ROSTERSYNTH_LLM` | `bedrock` or `cassette` |

SSO profile template: Orion dev account `609525944595`, region `us-east-1` — see `.env.example`.

## Record cassettes

```bash
python scripts/sync_cassettes_from_golden.py
ROSTERSYNTH_RECORD_CASSETTE=1 bench oracle roster.kiosk_double_booking.v1 --llm bedrock
./scripts/record_bedrock_cassettes.sh
```

## Offline gates

```bash
bench gate --mode deterministic   # 12/12
bench gate --mode hybrid --llm cassette   # 14/14
bench gate --mode llm-only --llm cassette # 14/14
```

| Symptom | Fix |
|---------|-----|
| No credentials | `aws sso login --profile review` |
| Cassette gate fail | `python scripts/sync_cassettes_from_golden.py` |

Implementation: `rostersynth/oracle/bedrock.py` — Converse, sketch as system, payload as user, forced tool `emit_roster_suggestions`.
