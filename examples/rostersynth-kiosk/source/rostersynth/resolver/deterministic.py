from __future__ import annotations

from rostersynth.models import Payload, SuggestionRow
from rostersynth.playbook import build_rows


def resolve_deterministic(payload: Payload) -> list[SuggestionRow]:
    """Oracle A only — deterministic resolver, no LLM."""
    return build_rows(payload)


def payload_to_prompt_dict(payload: Payload) -> dict:
    departments = []
    for dept_group in payload.departments:
        employees = []
        for emp in dept_group:
            employees.append(
                {
                    "employeeId": emp.employee_id,
                    "roleCode": emp.role_code,
                    "deptId": emp.dept_id,
                    "windowEnd": emp.window_end,
                    "priorWindowEnd": emp.prior_window_end,
                    "badgeHours": emp.badge_hours,
                    "scheduledHours": emp.scheduled_hours,
                    "coverageDelta": emp.coverage_delta,
                    "bookings": [
                        {
                            "bookingId": b.booking_id,
                            "shiftKind": b.shift_kind,
                            "status": b.status,
                            "hours": b.hours,
                            "workDate": b.work_date,
                            **({"tags": list(b.tags)} if b.tags else {}),
                        }
                        for b in emp.bookings
                    ],
                    **(
                        {"clusterNotes": emp.cluster_notes}
                        if emp.cluster_notes
                        else {}
                    ),
                }
            )
        if employees:
            departments.append({"deptId": employees[0]["deptId"], "employees": employees})
    return {"departments": departments}


def imbalanced_employees(payload: Payload):
    for department in payload.departments:
        for emp in department:
            if abs(emp.coverage_delta) >= 1e-9:
                yield emp
