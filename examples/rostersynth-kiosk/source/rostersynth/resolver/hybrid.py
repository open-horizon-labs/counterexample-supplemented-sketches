from __future__ import annotations

from pathlib import Path

from rostersynth.models import Payload, SuggestionRow
from rostersynth.playbook import build_rows
from rostersynth.resolver.deterministic import imbalanced_employees
from rostersynth.resolver.llm import default_llm_backend, resolve_llm_only
from rostersynth.verifier import effective_delta

EPSILON = 1e-9


def _row_closes_delta(emp, row: SuggestionRow) -> bool:
    return abs(effective_delta(emp, [row])) < EPSILON


def resolve_hybrid(
    payload: Payload,
    repo_root: Path,
    scenario_id: str,
    *,
    llm_backend: str | None = None,
) -> list[SuggestionRow]:
    """Production-style hybrid: deterministic first, Oracle B fallback per employee.

    Fallback uses Bedrock live or JSON cassettes (``--llm bedrock|cassette``).
    Verifier replay decides fallback — not golden compare.
    """
    backend = (llm_backend or default_llm_backend()).lower()
    playbook_rows = build_rows(payload)
    playbook_by_emp = {r.employee_id: r for r in playbook_rows}

    needs_llm = False
    for emp in imbalanced_employees(payload):
        row = playbook_by_emp.get(emp.employee_id)
        if row is None or not _row_closes_delta(emp, row):
            needs_llm = True
            break

    if not needs_llm:
        return playbook_rows

    llm_rows = resolve_llm_only(payload, repo_root, scenario_id, backend=backend)
    llm_by_emp = {r.employee_id: r for r in llm_rows}

    merged: list[SuggestionRow] = []
    for emp in imbalanced_employees(payload):
        det = playbook_by_emp.get(emp.employee_id)
        if det is not None and _row_closes_delta(emp, det):
            merged.append(det)
            continue
        llm_row = llm_by_emp.get(emp.employee_id)
        if llm_row is None:
            raise ValueError(
                f"Hybrid fallback: Oracle B missing row for {emp.employee_id}"
            )
        merged.append(
            SuggestionRow(
                employee_id=llm_row.employee_id,
                issue_type=llm_row.issue_type,
                op=llm_row.op,
                suggestion=llm_row.suggestion,
                generated_by=f"hybrid_llm_{backend}",
                adjustment=llm_row.adjustment,
                modify=llm_row.modify,
            )
        )
    return merged
