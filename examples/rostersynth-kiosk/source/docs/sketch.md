# Example sketch (roster domain)

The sketch is the contract. The agent edits this file when gates fail. Oracle A implements encodable clauses in `playbook.py`; Oracle B reads the same prose plus payload (`clusterNotes`, tags).

## Ground truth

- `badgeHours` observed; never edited.
- `coverageDelta = badgeHours - scheduledHours`.

## Op 1 — append

Adjustment sized to `coverageDelta` when no duplicate cancel closes it.

**Work date hole:**

1. Latest active booking in `[priorWindowEnd, windowEnd)` → use `windowEnd`.
2. Else max active `workDate`.
3. Else `windowEnd`.

## Op 2 — cancel duplicate

Twins on `windowEnd`, same `(shiftKind, hours)`: cancel **higher `bookingId`**, `status=4`, only if that alone closes delta. Else Op 1.

## Op 2b — LLM hole

`clusterNotes` present → Oracle A **abstains**; Oracle B picks `bookingId`. Tag scenarios `requiresLlmFallback`.

## Who fills what

| Oracle | Where |
|--------|--------|
| A | `playbook.py` |
| B | This sketch + `prompt.py` + Bedrock/cassette |

## What “pass” means

- **Replay** — delta closes.
- **Compare** — golden `op`, `workDate`, `bookingId`, … Replay alone misses wrong `op` with closed delta.
