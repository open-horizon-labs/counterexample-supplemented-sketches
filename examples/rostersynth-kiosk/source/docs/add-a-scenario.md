# Promote a counterexample into *E*

Gate fails → capture it as a scenario → edit sketch / Oracle A / Oracle B → rerun until green. File layout here is the **roster example** (`scenarios/roster.*.json`).

## 1. Scenario JSON

```json
{
  "id": "roster.my_case.v1",
  "title": "Short title",
  "requiresLlmFallback": false,
  "inputPayload": { "departments": [] },
  "expectations": {
    "resolver": {
      "suggestions": [{
        "employeeId": "E-1",
        "issueType": "coverage-hour-gap",
        "op": "append",
        "adjustment": {
          "shiftKind": 51,
          "hours": -4.0,
          "workDate": "2024-06-01",
          "status": 1
        }
      }]
    }
  }
}
```

`requiresLlmFallback: true` when the sketch declares an LLM hole.

## 2. Manifest

Add id to `scenarios/manifest.json`.

## 3. Cassette (hybrid / llm-only)

```bash
python scripts/sync_cassettes_from_golden.py
# or live:
ROSTERSYNTH_RECORD_CASSETTE=1 bench oracle roster.my_case.v1 --llm bedrock
```

## 4. Gates

```bash
pytest -q
bench gate --mode deterministic
bench gate --mode hybrid --llm cassette
bench gate --mode llm-only --llm cassette
```

Good enough: **12/12 + 14/14 + 14/14** (default deterministic exclusions). The failing line says replay vs compare vs Oracle B.

## 5. Sketch

Policy change? Edit `docs/sketch.md` before re-syncing cassettes. Sketch lag is the usual agent miss—code matches golden, compare still red.

## Checklist

- [ ] Golden passes verifier + comparer through resolver
- [ ] Cassette if B modes need it
- [ ] `requiresLlmFallback` matches abstention
