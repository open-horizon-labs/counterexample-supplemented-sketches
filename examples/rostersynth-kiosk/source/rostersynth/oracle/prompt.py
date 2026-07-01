from __future__ import annotations

import json
from pathlib import Path


def load_sketch(repo_root: Path) -> str:
    path = repo_root / "docs" / "sketch.md"
    if not path.exists():
        raise FileNotFoundError(f"Sketch not found: {path}")
    return path.read_text()


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
