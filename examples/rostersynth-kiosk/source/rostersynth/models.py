from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ShiftBooking:
    booking_id: int
    shift_kind: int
    status: int  # 1=active, 4=cancelled
    hours: float
    work_date: str
    invalid: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ShiftBooking:
        tags_raw = raw.get("tags") or []
        return cls(
            booking_id=int(raw["bookingId"]),
            shift_kind=int(raw["shiftKind"]),
            status=int(raw["status"]),
            hours=float(raw["hours"]),
            work_date=str(raw["workDate"]),
            invalid=bool(raw.get("invalid", False)),
            tags=tuple(str(t) for t in tags_raw),
        )


@dataclass(frozen=True)
class EmployeeRoster:
    employee_id: str
    role_code: str
    dept_id: int
    window_end: str
    prior_window_end: str | None
    badge_hours: float
    scheduled_hours: float
    coverage_delta: float
    bookings: tuple[ShiftBooking, ...] = field(default_factory=tuple)
    cluster_notes: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EmployeeRoster:
        bookings = tuple(ShiftBooking.from_dict(x) for x in raw.get("bookings", []))
        cluster_notes = raw.get("clusterNotes")
        return cls(
            employee_id=str(raw["employeeId"]),
            role_code=str(raw["roleCode"]),
            dept_id=int(raw["deptId"]),
            window_end=str(raw["windowEnd"]),
            prior_window_end=raw.get("priorWindowEnd"),
            badge_hours=float(raw["badgeHours"]),
            scheduled_hours=float(raw["scheduledHours"]),
            coverage_delta=float(raw["coverageDelta"]),
            bookings=bookings,
            cluster_notes=str(cluster_notes) if cluster_notes else None,
        )


@dataclass(frozen=True)
class Payload:
    departments: tuple[tuple[EmployeeRoster, ...], ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Payload:
        departments = tuple(
            tuple(EmployeeRoster.from_dict(e) for e in dept.get("employees", []))
            for dept in raw.get("departments", [])
        )
        return cls(departments=departments)

    def employee_by_id(self, employee_id: str) -> EmployeeRoster | None:
        for dept in self.departments:
            for emp in dept:
                if emp.employee_id == employee_id:
                    return emp
        return None


@dataclass(frozen=True)
class WireAdjustment:
    shift_kind: int
    hours: float
    work_date: str
    status: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "shiftKind": self.shift_kind,
            "hours": self.hours,
            "workDate": self.work_date,
            "status": self.status,
        }


@dataclass(frozen=True)
class WireModify:
    booking_id: int
    fields: dict[str, Any]


@dataclass(frozen=True)
class SuggestionRow:
    employee_id: str
    issue_type: str
    op: str
    suggestion: str
    generated_by: str
    adjustment: WireAdjustment | None = None
    modify: WireModify | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "employeeId": self.employee_id,
            "issueType": self.issue_type,
            "op": self.op,
            "suggestion": self.suggestion,
            "generatedBy": self.generated_by,
        }
        if self.adjustment is not None:
            out["adjustment"] = self.adjustment.to_dict()
        if self.modify is not None:
            out["bookingId"] = self.modify.booking_id
            out["fields"] = self.modify.fields
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SuggestionRow:
        adjustment = None
        if raw.get("op") == "append" and raw.get("adjustment"):
            t = raw["adjustment"]
            adjustment = WireAdjustment(
                shift_kind=int(t["shiftKind"]),
                hours=float(t["hours"]),
                work_date=str(t["workDate"]),
                status=int(t.get("status", 1)),
            )
        modify = None
        if raw.get("op") == "modify":
            modify = WireModify(
                booking_id=int(raw["bookingId"]),
                fields=dict(raw.get("fields", {})),
            )
        return cls(
            employee_id=str(raw["employeeId"]),
            issue_type=str(raw.get("issueType", "")),
            op=str(raw.get("op", "")),
            suggestion=str(raw.get("suggestion", "")),
            generated_by=str(raw.get("generatedBy", "unknown")),
            adjustment=adjustment,
            modify=modify,
        )


# Shift kind codes (WFM policy appendix)
SHIFT_KIND_REGULAR = 10
SHIFT_KIND_OVERTIME_ADJ = 8
SHIFT_KIND_UNDERSCHED_ADJ = 51

ISSUE_HOUR_GAP = "coverage-hour-gap"
ISSUE_CANCEL_DUP = "cancel-duplicate-booking"
