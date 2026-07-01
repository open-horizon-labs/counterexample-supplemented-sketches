# Extracted Paper: RosterSynth Kiosk Counterexample

> Generated from repo-local RosterSynth source snapshots and graph selectors. This is the canonical full example artifact for the clean-room extraction slice; regenerate with `tools/extract_rostersynth_example.py --write --paper`.

## Abstract

This example shows the full RosterSynth process on one counterexample: a kiosk double-tap creates twin 40-hour active bookings, and the tempting append repair closes the hours math while violating duplicate policy. The sketch clause, corpus case, Oracle A implementation, Oracle B prompt/cassette path, replay check, semantic compare, promotion step, negative cassette, full-gate evidence, and verification tests are all linked by graph nodes with source selectors.

## Method Claim

- `examples/rostersynth-kiosk/source/paper/main.tex:14-24` — Sketch plus growing E, dual oracles, replay/compare gates, and counterexample promotion hold agentic coding accountable.
- `examples/rostersynth-kiosk/source/README.md:11-18` — Write sketch, collect examples, promote failures into E, gate over replay and compare.

## Corpus E

- Manifest selector: `examples/rostersynth-kiosk/source/scenarios/manifest.json`
- Scenario count: 14
- Kiosk scenario selector: `examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json`
- Golden expectation: `modify` bookingId `1802`

~~~json
{
  "resolver": {
    "suggestions": [
      {
        "employeeId": "E-1800",
        "issueType": "cancel-duplicate-booking",
        "op": "modify",
        "bookingId": 1802,
        "fields": {
          "status": 4
        },
        "suggestion": "Cancel duplicate booking 1802 (status 1 \u2192 4) on pay window end date."
      }
    ]
  }
}
~~~

## Sketch Clause

Selector: `examples/rostersynth-kiosk/source/docs/sketch.md:20-27`

~~~md
## Op 2 — cancel duplicate

Twins on `windowEnd`, same `(shiftKind, hours)`: cancel **higher `bookingId`**, `status=4`, only if that alone closes delta. Else Op 1.

## Op 2b — LLM hole

`clusterNotes` present → Oracle A **abstains**; Oracle B picks `bookingId`. Tag scenarios `requiresLlmFallback`.
~~~

## Counterexample

Selector: `examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json`
Tempting wrong patch: append -40 hours to close coverageDelta, or cancel lower bookingId 1801 because replay still closes the hours math.

The historical failure is source-backed:

Selector: `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:140-150`

~~~md
### Step 2b — Historical: before Op 2 (FAIL — promotion trigger)

*Not runnable today.* Oracle A had only Op 1 → append −40h. Replay pass; compare fail.

```text
[FAIL] roster.kiosk_double_booking.v1
  - Employee E-1800: expected op modify, got append
  - all imbalanced rosters closed
```

I was posing the fix as “post an adjustment.” The difference is duplicate policy—cancel the twin. Compare caught it; replay wouldn't have.
~~~

## Oracle A: Encodable Policy

### Oracle A deterministic resolver

Selector: `examples/rostersynth-kiosk/source/rostersynth/resolver/deterministic.py:7-9`

~~~python
def resolve_deterministic(payload: Payload) -> list[SuggestionRow]:
    """Oracle A only — deterministic resolver, no LLM."""
    return build_rows(payload)
~~~

### Oracle A build_rows dispatcher

Selector: `examples/rostersynth-kiosk/source/rostersynth/playbook.py:53-72`
Handling: Skips balanced employees, abstains on clusterNotes, tries duplicate cancel before append.

~~~python
def build_rows(payload: Payload) -> list[SuggestionRow]:
    rows: list[SuggestionRow] = []
    for department in payload.departments:
        for emp in department:
            if abs(emp.coverage_delta) < EPSILON:
                continue
            row = _build_for_employee(emp)
            if row is not None:
                rows.append(row)
    return rows


def _build_for_employee(emp: EmployeeRoster) -> SuggestionRow | None:
    # Oracle A abstains when WFM left cluster disambiguation notes — not rule-encodable.
    if emp.cluster_notes:
        return None

    cancel = _try_cancel_duplicate(emp)
    if cancel is not None:
        return cancel
~~~

### Cancel duplicate implementation

Selector: `examples/rostersynth-kiosk/source/rostersynth/playbook.py:109-137`
Handling: Groups active windowEnd bookings by (shiftKind, hours), picks max bookingId, and only emits modify if deactivation closes coverageDelta.

~~~python
def _try_cancel_duplicate(emp: EmployeeRoster) -> SuggestionRow | None:
    active = [
        b
        for b in emp.bookings
        if not b.invalid and b.status == 1 and b.work_date == emp.window_end
    ]
    if len(active) < 2:
        return None
    groups: dict[tuple[int, float], list] = {}
    for booking in active:
        key = (booking.shift_kind, booking.hours)
        groups.setdefault(key, []).append(booking)
    targets: list[int] = []
    for lines in groups.values():
        if len(lines) >= 2:
            pk = max(b.booking_id for b in lines)
            if _cancel_closes_delta(emp, pk):
                targets.append(pk)
    if not targets:
        return None
    pk = targets[0]
    return SuggestionRow(
        employee_id=emp.employee_id,
        issue_type=ISSUE_CANCEL_DUP,
        op="modify",
        suggestion=f"Cancel duplicate booking {pk} (status 1 → 4) on pay window end date.",
        generated_by="deterministic",
        modify=WireModify(booking_id=pk, fields={"status": 4}),
    )
~~~

## Replay and Compare

### Replay effective delta

Selector: `examples/rostersynth-kiosk/source/rostersynth/verifier.py:8-18`
Check: Rows must close each imbalanced employee's coverageDelta.

~~~python
def effective_delta(emp: EmployeeRoster, rows: list[SuggestionRow]) -> float:
    delta = emp.coverage_delta
    emp_rows = [r for r in rows if r.employee_id == emp.employee_id]
    for row in emp_rows:
        if row.op == "append" and row.adjustment is not None:
            adj = row.adjustment
            if adj.status == 1 and adj.work_date <= emp.window_end:
                delta -= adj.hours
        elif row.op == "modify" and row.modify is not None:
            delta += _modify_delta(emp, row.modify.booking_id, row.modify.fields)
    return delta
~~~

### Semantic compare for modify rows

Selector: `examples/rostersynth-kiosk/source/rostersynth/eval/comparer.py:8-55`
Check: Golden compare catches wrong op, wrong bookingId, and wrong fields.status.

~~~python
def compare_rows(expected: SuggestionRow, actual: SuggestionRow) -> tuple[bool, list[str]]:
    notes: list[str] = []
    ok = True
    eid = expected.employee_id

    if expected.op != actual.op:
        notes.append(f"Employee {eid}: expected op {expected.op}, got {actual.op}")
        ok = False

    if expected.issue_type and actual.issue_type and expected.issue_type != actual.issue_type:
        notes.append(
            f"Employee {eid}: expected issueType {expected.issue_type}, "
            f"got {actual.issue_type}"
        )
        ok = False

    if expected.op == "modify":
        ok = _compare_modify(expected, actual, notes) and ok
    elif expected.op == "append":
        ok = _compare_append(expected, actual, notes) and ok

    if ok:
        notes.append(f"Employee {eid}: pass")
    return ok, notes


def _compare_modify(
    expected: SuggestionRow, actual: SuggestionRow, notes: list[str]
) -> bool:
    eid = expected.employee_id
    ok = True
    if expected.modify is None or actual.modify is None:
        notes.append(f"Employee {eid}: modify shape missing")
        return False
    if expected.modify.booking_id != actual.modify.booking_id:
        notes.append(
            f"Employee {eid}: expected bookingId {expected.modify.booking_id}, "
            f"got {actual.modify.booking_id}"
        )
        ok = False
    for key, exp_val in expected.modify.fields.items():
        act_val = actual.modify.fields.get(key)
        if act_val != exp_val:
            notes.append(
                f"Employee {eid}: expected fields.{key}={exp_val}, got {act_val}"
            )
            ok = False
    return ok
~~~

## Oracle B: Prompt and Cassette

### Oracle B prompt decision order

Selector: `examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py:14-40`
Handling: Puts Op 2 before Op 1 and states the higher-bookingId tie-break plus required modify shape.

~~~json
def build_user_prompt(payload: dict) -> str:
    appendix = """
SHIFT KIND CODES (use exactly these on append adjustments):
- 8  = overtime adjustment (coverageDelta > 0)
- 51 = underschedule adjustment (coverageDelta < 0)
- 10 = regular scheduled shift (bookings only — never use 10 on append adjustments)

DECISION ORDER per employee with coverageDelta ≠ 0:
0) If clusterNotes is present, read it together with booking tags to disambiguate duplicate
   clusters (e.g. which DUPLICATE-tagged line to cancel). clusterNotes overrides the default
   higher-bookingId tie-break when they conflict.
1) Op 2 — cancel-duplicate-booking (modify): duplicate active bookings on windowEnd with
   same (shiftKind, hours) AND cancelling the chosen duplicate fully closes coverageDelta.
   Default tie-break: HIGHER bookingId. When clusterNotes or tags name a specific booking,
   cancel that bookingId. Emit: op=modify, bookingId=<id>, fields={"status": 4} (required).
2) Op 1 — coverage-hour-gap (append): otherwise post one adjustment with hours=coverageDelta,
   shiftKind 51 if delta negative, shiftKind 8 if delta positive.
   Apply work-date rules from the sketch for workDate.

Modify rows MUST include fields.status=4. Append rows MUST include adjustment object.
"""
    return (
        "Apply the roster sketch to each imbalanced employee. Emit one suggestion per employee "
        "via the tool.\n\n"
        f"{appendix}\n\n"
        f"PAYLOAD:\n{json.dumps(payload, indent=2)}"
    )
~~~

### Correct kiosk cassette

Selector: `examples/rostersynth-kiosk/source/cassettes/roster.kiosk_double_booking.v1.json`

~~~json
{
  "scenarioId": "roster.kiosk_double_booking.v1",
  "mode": "llm-only",
  "generatedBy": "sync-from-golden",
  "suggestions": [
    {
      "employeeId": "E-1800",
      "issueType": "cancel-duplicate-booking",
      "op": "modify",
      "bookingId": 1802,
      "fields": {
        "status": 4
      },
      "suggestion": "Cancel duplicate booking 1802 (status 1 \u2192 4) on pay window end date.",
      "generatedBy": "cassette-from-golden"
    }
  ]
}
~~~

### Wrong kiosk cassette

Selector: `examples/rostersynth-kiosk/source/cassettes/roster.kiosk_double_booking.v1.wrong.json`

~~~json
{
  "scenarioId": "roster.kiosk_double_booking.v1",
  "mode": "llm-only",
  "notes": "WRONG cassette for session replay — cancels lower bookingId",
  "suggestions": [
    {
      "employeeId": "E-1800",
      "issueType": "cancel-duplicate-booking",
      "op": "modify",
      "generatedBy": "bedrock",
      "bookingId": 1801,
      "fields": { "status": 4 },
      "suggestion": "Cancel duplicate booking 1801 (status 1 → 4) on pay window end date."
    }
  ]
}
~~~

## Full Session Path

- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:36-58` — Golden op is modify bookingId 1802.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:63-96` — Prompt gives Op 2 priority over append and shows kiosk payload.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:100-135` — Deterministic gate passes; compare and replay both green.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:140-150` — Append closed delta but compare failed: expected modify, got append.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:154-176` — Hybrid passes; Oracle A wins so no LLM fallback for kiosk.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:182-205` — Cassette emits bookingId 1802.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:210-232` — Wrong bookingId 1801 still closes replay but compare fails.
- `examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:281-299` — Deterministic 12/12 plus 2 excluded; hybrid and llm-only cassette 14/14.

## Query: How Is This Counterexample Handled?

~~~text
Counterexample: Kiosk double-tap should cancel higher duplicate booking
Source: examples/rostersynth-kiosk/source/scenarios/roster.kiosk_double_booking.v1.json
Tempting patch: append -40 hours to close coverageDelta, or cancel lower bookingId 1801 because replay still closes the hours math
Path:
- Sketch clause: examples/rostersynth-kiosk/source/docs/sketch.md:20-27 — Twins on windowEnd with same shiftKind and hours cancel the higher bookingId when that alone closes delta; clusterNotes route to Oracle B.
- Corpus/session observation: examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:36-58 — Golden op is modify bookingId 1802.
- Promotion trigger: examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:140-150 — Append closed delta but compare failed: expected modify, got append.
- Oracle A: examples/rostersynth-kiosk/source/rostersynth/playbook.py:109-137 — Groups active windowEnd bookings by (shiftKind, hours), picks max bookingId, and only emits modify if deactivation closes coverageDelta.
- Replay: examples/rostersynth-kiosk/source/rostersynth/verifier.py:8-18 — Rows must close each imbalanced employee's coverageDelta.
- Compare: examples/rostersynth-kiosk/source/rostersynth/eval/comparer.py:8-55 — Golden compare catches wrong op, wrong bookingId, and wrong fields.status.
- Oracle B prompt: examples/rostersynth-kiosk/source/rostersynth/oracle/prompt.py:14-40 — Puts Op 2 before Op 1 and states the higher-bookingId tie-break plus required modify shape.
- Negative check: examples/rostersynth-kiosk/source/docs/sessions/01-kiosk-double-booking.md:210-232 — Wrong bookingId 1801 still closes replay but compare fails.
Verified by:
- examples/rostersynth-kiosk/source/tests/test_rostersynth.py:99-105: Oracle A must emit modify bookingId 1802.
- examples/rostersynth-kiosk/source/tests/test_rostersynth.py:129-135: Oracle B cassette must emit modify bookingId 1802.
- examples/rostersynth-kiosk/source/tests/test_rostersynth.py:152-159: Hybrid must keep deterministic row and not require fallback.
- examples/rostersynth-kiosk/source/tests/test_rostersynth.py:24-52: Deterministic excludes LLM fallbacks; hybrid and llm-only cassette pass manifest count.
~~~

## Verification Selectors

- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:99-105` — Oracle A must emit modify bookingId 1802.
- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:129-135` — Oracle B cassette must emit modify bookingId 1802.
- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:152-159` — Hybrid must keep deterministic row and not require fallback.
- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:138-149` — Replay rejects an append with the wrong magnitude.
- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:162-175` — Prompt includes DECISION ORDER, kiosk employee, and Op 2.
- `examples/rostersynth-kiosk/source/tests/test_rostersynth.py:24-52` — Deterministic excludes LLM fallbacks; hybrid and llm-only cassette pass manifest count.

## Bounded Claim

This extracted example supports the claim that the kiosk counterexample is inspectable end to end from sketch clause to corpus case, promotion trigger, Oracle A implementation, Oracle B prompt/cassette path, replay/compare checks, negative check, and tests. It does not by itself prove the full method across every domain; the full-corpus gate node only establishes the referenced RosterSynth corpus evidence.

## Regenerate

~~~bash
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --write --paper
python3 sketch-counterexample-agent/tools/extract_rostersynth_example.py --ce roster.kiosk_double_booking.v1
python3 -m unittest discover -s sketch-counterexample-agent/examples/rostersynth-kiosk/tests
~~~
