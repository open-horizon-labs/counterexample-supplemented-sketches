from __future__ import annotations

from rostersynth.models import EmployeeRoster, Payload, SuggestionRow, WireAdjustment, WireModify

EPSILON = 1e-9


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


def _modify_delta(emp: EmployeeRoster, booking_id: int, fields: dict) -> float:
    original = next((b for b in emp.bookings if b.booking_id == booking_id), None)
    if original is None or original.invalid:
        return 0.0
    if original.work_date > emp.window_end:
        return 0.0
    old_status = original.status
    new_status = int(fields.get("status", old_status))
    if old_status == 1 and new_status != 1:
        return original.hours
    if old_status != 1 and new_status == 1:
        return -original.hours
    return 0.0


def verify_rows(payload: Payload, rows: list[SuggestionRow]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    passed = True
    for department in payload.departments:
        for emp in department:
            if abs(emp.coverage_delta) < EPSILON:
                continue
            after = effective_delta(emp, rows)
            if abs(after) >= EPSILON:
                notes.append(
                    f"Employee {emp.employee_id}: coverageDelta {emp.coverage_delta} "
                    f"not closed (effective {after})"
                )
                passed = False
            emp_rows = [r for r in rows if r.employee_id == emp.employee_id]
            if not emp_rows:
                notes.append(f"Employee {emp.employee_id}: missing remediation row")
                passed = False
    if passed:
        notes.insert(0, "all imbalanced rosters closed")
    return passed, notes
