# Agent sessions (roster examples)

Each session is one **counterexample promotion** in the technique: gate fail → edit sketch / Oracle A / Oracle B → gates pass. Roster domain only—the method is in the [paper](../paper/main.pdf).

| Session | Scenario | Promotion |
|---------|----------|-----------|
| [01 — Kiosk](01-kiosk-double-booking.md) | `roster.kiosk_double_booking.v1` | Op 2 sketch + Oracle A; Oracle B prompts + cassette |

```bash
bash scripts/record_session.sh
bench prompt roster.kiosk_double_booking.v1
```

Add to *E*: [../add-a-scenario.md](../add-a-scenario.md).
