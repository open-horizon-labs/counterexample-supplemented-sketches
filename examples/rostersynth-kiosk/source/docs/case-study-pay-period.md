# CE promotion: pay-period workDate (roster example)

`bench gate` on `roster.new_period.undersched.v1`: replay **pass**, compare **fail**. Both oracles could post −5h and close delta; golden wanted `workDate` on **window end**, not latest booking date.

I was treating “delta closed” as done. Compare encodes pay-window policy; replay didn't.

## Observation

| Field | Value |
|-------|-------|
| windowEnd | 2024-06-25 |
| priorWindowEnd | 2024-06-24 |
| Latest active booking | 2024-06-24 |
| coverageDelta | −5 |

## What we changed

1. Golden `workDate` → 2024-06-25.
2. Scenario into *E*.
3. Op 1 rule in sketch + `resolve_append_work_date()` in Oracle A.
4. Oracle B cassette aligned.

```bash
bench gate --mode deterministic
bench gate --mode hybrid --llm cassette
bench gate --mode llm-only --llm cassette
```

LLM-only holes (`cluster_notes_*`) are separate — [sketch.md](sketch.md) Op 2b, paper Sect. 10.
