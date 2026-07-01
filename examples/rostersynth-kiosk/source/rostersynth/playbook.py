from __future__ import annotations

from rostersynth.models import (
    ISSUE_CANCEL_DUP,
    ISSUE_HOUR_GAP,
    SHIFT_KIND_OVERTIME_ADJ,
    SHIFT_KIND_UNDERSCHED_ADJ,
    EmployeeRoster,
    Payload,
    SuggestionRow,
    WireAdjustment,
    WireModify,
)

EPSILON = 1e-9


def latest_active_work_date(emp: EmployeeRoster) -> str | None:
    best: str | None = None
    for booking in emp.bookings:
        if booking.invalid or booking.status != 1:
            continue
        if best is None or booking.work_date > best:
            best = booking.work_date
    return best


def resolve_append_work_date(emp: EmployeeRoster) -> str:
    """Work-date hole filler for coverage adjustment appends."""
    latest = latest_active_work_date(emp)
    if latest is None:
        return emp.window_end
    prior = emp.prior_window_end
    if prior and latest >= prior and latest < emp.window_end:
        return emp.window_end
    return latest


def format_create(emp: EmployeeRoster, shift_kind: int, hours: float, work_date: str) -> str:
    kind_name = {
        SHIFT_KIND_OVERTIME_ADJ: "Overtime adjustment",
        SHIFT_KIND_UNDERSCHED_ADJ: "Underschedule adjustment",
    }.get(shift_kind, f"ShiftKind {shift_kind}")
    direction = "over-scheduled" if emp.coverage_delta < 0 else "under-scheduled"
    return (
        f"Post {kind_name} for {hours} hours for {emp.role_code} "
        f"({emp.employee_id}, dept {emp.dept_id}, work date {work_date}) — "
        f"roster is {direction} vs badge by {abs(emp.coverage_delta)} hours "
        f"(coverageDelta {emp.coverage_delta})."
    )


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

    if emp.coverage_delta < 0:
        shift_kind = SHIFT_KIND_UNDERSCHED_ADJ
        hours = emp.coverage_delta
    else:
        shift_kind = SHIFT_KIND_OVERTIME_ADJ
        hours = emp.coverage_delta

    work_date = resolve_append_work_date(emp)
    adjustment = WireAdjustment(shift_kind=shift_kind, hours=hours, work_date=work_date)
    return SuggestionRow(
        employee_id=emp.employee_id,
        issue_type=ISSUE_HOUR_GAP,
        op="append",
        suggestion=format_create(emp, shift_kind, hours, work_date),
        generated_by="deterministic",
        adjustment=adjustment,
    )


def _deactivate_booking_delta(emp: EmployeeRoster, booking_id: int) -> float:
    original = next((b for b in emp.bookings if b.booking_id == booking_id), None)
    if original is None or original.invalid:
        return 0.0
    if original.work_date > emp.window_end:
        return 0.0
    if original.status == 1:
        return original.hours
    return 0.0


def _cancel_closes_delta(emp: EmployeeRoster, booking_id: int) -> bool:
    delta = _deactivate_booking_delta(emp, booking_id)
    return abs(emp.coverage_delta + delta) < EPSILON


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
