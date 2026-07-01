from __future__ import annotations

from rostersynth.models import SuggestionRow

HOURS_TOLERANCE = 0.01


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


def _compare_append(
    expected: SuggestionRow, actual: SuggestionRow, notes: list[str]
) -> bool:
    eid = expected.employee_id
    ok = True
    if expected.adjustment is None or actual.adjustment is None:
        notes.append(f"Employee {eid}: adjustment shape missing")
        return False
    exp, act = expected.adjustment, actual.adjustment
    if exp.shift_kind != act.shift_kind:
        notes.append(
            f"Employee {eid}: expected shiftKind {exp.shift_kind}, got {act.shift_kind}"
        )
        ok = False
    if abs(exp.hours - act.hours) > HOURS_TOLERANCE:
        notes.append(
            f"Employee {eid}: expected hours {exp.hours}, got {act.hours}"
        )
        ok = False
    if exp.work_date and exp.work_date != act.work_date:
        notes.append(
            f"Employee {eid}: expected workDate {exp.work_date}, got {act.work_date}"
        )
        ok = False
    return ok


def compare_scenario(
    expected_rows: list[SuggestionRow], actual_rows: list[SuggestionRow]
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not expected_rows:
        return len(actual_rows) == 0, notes

    passed = True
    remaining = list(actual_rows)
    for exp in expected_rows:
        act = next((r for r in remaining if r.employee_id == exp.employee_id), None)
        if act is None:
            notes.append(f"Employee {exp.employee_id}: missing from resolver output")
            passed = False
            continue
        remaining.remove(act)
        row_ok, row_notes = compare_rows(exp, act)
        passed = passed and row_ok
        notes.extend(row_notes)

    for extra in remaining:
        notes.append(f"Employee {extra.employee_id}: unexpected row in resolver output")
        passed = False

    if passed:
        notes.insert(0, "resolver suggestions matched per employee (semantic compare)")
    return passed, notes
