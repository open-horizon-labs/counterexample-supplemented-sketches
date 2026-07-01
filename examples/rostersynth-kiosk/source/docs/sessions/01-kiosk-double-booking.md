# Session 01: Kiosk double-booking

Paper Sect. 10 · roster **example** · `roster.kiosk_double_booking.v1`

Run top to bottom for **command → output → what happened → next**. Or replay everything:

```bash
source .venv/bin/activate
bash scripts/record_session.sh | tee docs/sessions/01-kiosk-transcript.txt
```

Bedrock (optional): [../bedrock-setup.md](../bedrock-setup.md)

## Story

CNA **E-1800** double-tapped the kiosk. Badge **40h**, scheduled **80h**, Δ **−40**. Twin 40h bookings on window end **2024-05-14** — ids **1801** and **1802**.

Policy: cancel **1802** (`modify`, `status → 4`). Append −40h closes the hours math; compare still fails because duplicate policy wants a cancel, not paper over it.

## Setup

```bash
cd RosterSynth
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

All commands below assume `bench` is on your PATH via the venv.

---

## Command transcript (in order)

Each step: **command → output → what happened → what we did next**.

### Step 0 — Confirm the counterexample in corpus E

**Command:**

```bash
python3 -c "
import json
s = json.load(open('scenarios/roster.kiosk_double_booking.v1.json'))
e = s['expectations']['resolver']['suggestions'][0]
print('title:', s['title'])
print('golden op:', e['op'], 'bookingId:', e['bookingId'])
"
```

**Output:**

```text
title: Kiosk double-tap: cancel higher duplicate booking
golden op: modify bookingId: 1802
```

**What happened:** Observation + golden are already in `scenarios/` and the manifest. This is the target Oracle A and Oracle B must hit.

**Next:** See what we send Oracle B (sketch + user appendix + payload).

---

### Step 1 — Dump Oracle B prompts (what we gave the LLM)

Oracle B = **system** (`docs/sketch.md`) + **user** (`oracle/prompt.py` appendix + JSON payload) + forced tool `emit_roster_suggestions`.

**Command:**

```bash
bench prompt roster.kiosk_double_booking.v1 --part user | head -40
# full system + user:
bench prompt roster.kiosk_double_booking.v1
```

**Output (truncated):**

```text
=== USER (oracle/prompt.py build_user_prompt) ===
Apply the roster sketch to each imbalanced employee. Emit one suggestion per employee via the tool.

DECISION ORDER per employee with coverageDelta ≠ 0:
...
1) Op 2 — cancel-duplicate-booking (modify): ... Default tie-break: HIGHER bookingId.
2) Op 1 — coverage-hour-gap (append): otherwise post one adjustment ...
...
PAYLOAD:
{
  "departments": [
    {
      "employees": [
        { "employeeId": "E-1800", "badgeHours": 40.0, "scheduledHours": 80.0, ... }
```

**What happened:** For kiosk, decision step **1** (Op 2) runs before step **2** (append). Twins on window end; cancel **1802** closes Δ.

**Next:** In the *promotion story*, Oracle A only knew Op 1 first—that failed compare. Current repo already has Op 2; Step 2 shows today's passing Oracle A, Step 2b shows the historical failure output.

---

### Step 2 — Oracle A after Op 2 (current repo — should PASS)

We added Op 2 to `docs/sketch.md` and `_try_cancel_duplicate()` in `playbook.py`.

**Command:**

```bash
bench gate --mode deterministic --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
r = next(x for x in d['scenarios'] if x['scenarioId'] == 'roster.kiosk_double_booking.v1')
print('passed:', r['passed'])
for n in r['compareNotes'] + r['verifyNotes']:
    print(' ', n)
"
```

**Output:**

```text
passed: True
  resolver suggestions matched per employee (semantic compare)
  Employee E-1800: pass
  all imbalanced rosters closed
```

**Full gate line:**

```bash
bench gate --mode deterministic
# ...
# Gate (deterministic, excluding requiresLlmFallback): PASSED (12/12, 2 excluded)
```

**What happened:** Oracle A emits `modify` on **1802**. Replay and compare both pass.

**Next:** Hybrid should use Oracle A here—no LLM fallback.

---

### Step 2b — Historical: before Op 2 (FAIL — promotion trigger)

*Not runnable today.* Oracle A had only Op 1 → append −40h. Replay pass; compare fail.

```text
[FAIL] roster.kiosk_double_booking.v1
  - Employee E-1800: expected op modify, got append
  - all imbalanced rosters closed
```

I was posing the fix as “post an adjustment.” The difference is duplicate policy—cancel the twin. Compare caught it; replay wouldn't have.

---

### Step 3 — Hybrid on kiosk (Oracle A wins — no fallback)

**Command:**

```bash
bench gate --mode hybrid --llm cassette --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
r = next(x for x in d['scenarios'] if x['scenarioId'] == 'roster.kiosk_double_booking.v1')
print('hybrid passed:', r['passed'])
"
bench gate --mode hybrid --llm cassette
```

**Output:**

```text
hybrid passed: True
...
Gate (hybrid, llm=cassette): PASSED (14/14)
```

**What happened:** Hybrid tried Oracle A first; row was replay-valid, so cassette Oracle B was never called for E-1800.

**Next:** Prove Oracle B separately with `llm-only` and the wrong/correct cassette demo.

---

### Step 4 — Oracle B with correct cassette (should PASS)

**Command:**

```bash
bench oracle roster.kiosk_double_booking.v1 --llm cassette
```

**Output:**

```json
{
  "suggestions": [{
    "employeeId": "E-1800",
    "op": "modify",
    "bookingId": 1802,
    "fields": { "status": 4 },
    "generatedBy": "cassette-from-golden"
  }]
}
```

**What happened:** Frozen cassette matches golden. CI uses this file—no AWS.

**Next:** Swap in the **wrong** cassette to show compare catching bad B output while replay still passes.

---

### Step 5 — Oracle B wrong cassette (FAIL on purpose)

**Commands:**

```bash
cp cassettes/roster.kiosk_double_booking.v1.json cassettes/roster.kiosk_double_booking.v1.json.bak
cp cassettes/roster.kiosk_double_booking.v1.wrong.json cassettes/roster.kiosk_double_booking.v1.json

bench gate --mode llm-only --llm cassette
```

**Output:**

```text
[FAIL] roster.kiosk_double_booking.v1
  - Employee E-1800: expected bookingId 1802, got 1801
  - all imbalanced rosters closed
...
Gate (llm-only, llm=cassette): FAILED (13/14)
```

**What happened:** Wrong file cancels **1801** (lower id). Replay still green; compare red. Sketch/code were already right—**B output** was wrong.

**Next:** Restore correct cassette.

---

### Step 6 — Restore correct cassette (should PASS)

**Commands:**

```bash
mv cassettes/roster.kiosk_double_booking.v1.json.bak cassettes/roster.kiosk_double_booking.v1.json

bench gate --mode llm-only --llm cassette --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
r = next(x for x in d['scenarios'] if x['scenarioId'] == 'roster.kiosk_double_booking.v1')
print('passed:', r['passed'])
for n in r['compareNotes'] + r['verifyNotes']:
    print(' ', n)
"
```

**Output:**

```text
passed: True
  resolver suggestions matched per employee (semantic compare)
  Employee E-1800: pass
  all imbalanced rosters closed
```

**What happened:** `llm-only` gate green again for kiosk.

**Next:** Record or sync cassette after sketch/prompt edits (production path).

**Record from live Bedrock (needs SSO):**

```bash
ROSTERSYNTH_RECORD_CASSETTE=1 bench oracle roster.kiosk_double_booking.v1 --llm bedrock
```

**Or sync CI cassette from golden:**

```bash
python scripts/sync_cassettes_from_golden.py
```

---

### Step 7 — Full corpus gates (CI shape)

**Commands (in order):**

```bash
bench gate --mode deterministic
bench gate --mode hybrid --llm cassette
bench gate --mode llm-only --llm cassette
```

**Output:**

```text
Gate (deterministic, excluding requiresLlmFallback): PASSED (12/12, 2 excluded)
Gate (hybrid, llm=cassette): PASSED (14/14)
Gate (llm-only, llm=cassette): PASSED (14/14)
```

**What happened:** Kiosk is one of 14 scenarios; deterministic skips two `clusterNotes` LLM-only cases.

---

### Step 8 — Live Bedrock (optional)

**Command:**

```bash
aws sso login --profile review   # if needed
bench oracle roster.kiosk_double_booking.v1 --llm bedrock
```

**Output (example):**

```json
{
  "suggestions": [{
    "employeeId": "E-1800",
    "op": "modify",
    "bookingId": 1802,
    "fields": { "status": 4 },
    "generatedBy": "bedrock"
  }]
}
```

**What happened:** Same sketch + user prompt as Step 1; live model agrees with golden. If this diverges from cassette, update prompt/sketch and re-record.

---

## Prompt reference (quick)

| Block | Source |
|-------|--------|
| System | Full `docs/sketch.md` — Op 2 excerpt: cancel **higher** `bookingId` when one cancel closes Δ |
| User appendix | `rostersynth/oracle/prompt.py` — DECISION ORDER (Op 2 before Op 1) |
| Tool | `emit_roster_suggestions` in `rostersynth/oracle/bedrock.py` |

---

## Artifacts

| File | Role |
|------|------|
| `scenarios/roster.kiosk_double_booking.v1.json` | Observation + golden |
| `docs/sketch.md` | Oracle B system; Oracle A policy |
| `rostersynth/oracle/prompt.py` | Oracle B user appendix |
| `rostersynth/playbook.py` | Oracle A (`_try_cancel_duplicate`) |
| `cassettes/roster.kiosk_double_booking.v1.wrong.json` | Wrong B (Step 5 demo) |
| `cassettes/roster.kiosk_double_booking.v1.json` | CI cassette |
| `scripts/record_session.sh` | Steps 0–8 automated |
| `tests/test_rostersynth.py` | Regression |

---

## Do not collapse

| Distinction | Fails differently |
|-------------|-------------------|
| Replay vs compare | Append closed Δ; compare wanted `modify` |
| Oracle A vs Oracle B | Kiosk fixed in A; B must still pass `llm-only` |
| Sketch vs user appendix | Partial program vs operational decision order |
| Historical Step 2b vs Step 2 | Before/after Op 2 promotion—not the same command today |
