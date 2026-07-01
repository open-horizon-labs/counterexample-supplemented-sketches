# Roster example — vocabulary only

One employee, one pay window. Badge says **40h**; WFM rollup says **80h**. Fix WFM—not the badge.

This page is **only** the concrete example domain in the reference impl. The technique: [paper](../paper/main.pdf).

## Terms

| Term | Meaning |
|------|---------|
| Badge hours | Timeclock total (ground truth) |
| Scheduled hours | WFM rollup |
| Coverage delta | `badgeHours − scheduledHours` |
| Window end | Last day of pay period under review |
| Bookings | WFM shift lines |
| Suggestion | Append adjustment or cancel booking |

## What a scenario asks

Does the proposed change close the gap **and** pass replay **and** compare?

## Delta

| Δ | Reading | Typical fix |
|---|---------|-------------|
| Negative | Over-scheduled vs badge | Underschedule adj |
| Positive | Under-scheduled vs badge | Overtime adj |
| Zero | Balanced | None |

## Sketch ops (this example)

- **Op 1** — append sized to delta when no duplicate cancel closes it.
- **Op 2** — cancel duplicate twin on window end.

[Kiosk session](sessions/01-kiosk-double-booking.md): replay lets append close the math; compare catches wrong `op`. That's why the technique uses both checks.

[for-researchers.md](for-researchers.md) · [for-coders.md](for-coders.md)
