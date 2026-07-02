from pathlib import Path

from rostersynth.eval.comparer import compare_rows
from rostersynth.eval.gate import run_gate
from rostersynth.eval.scenarios import load_manifest, load_scenario, llm_fallback_scenario_ids
from rostersynth.models import SuggestionRow, WireAdjustment
from rostersynth.playbook import build_rows
from rostersynth.resolver.deterministic import resolve_deterministic
from rostersynth.resolver.hybrid import _row_closes_delta, resolve_hybrid
from rostersynth.resolver.llm import resolve_llm_only

REPO = Path(__file__).resolve().parents[1]
CLUSTER_CE = "roster.cluster_notes_duplicate.v1"
TRIPLET_CE = "roster.cluster_notes_triplet.v1"
LLM_CE_IDS = llm_fallback_scenario_ids(REPO)
MANIFEST_COUNT = len(load_manifest(REPO))
TRACTABLE_COUNT = MANIFEST_COUNT - len(LLM_CE_IDS)


def test_llm_fallback_tags():
    assert LLM_CE_IDS == frozenset({CLUSTER_CE, TRIPLET_CE})


def test_deterministic_gate_excludes_llm_fallback_by_default():
    passed, results = run_gate(REPO, "deterministic", exclude_llm_fallback=True)
    assert passed, results
    excluded = [r for r in results if r.get("excluded")]
    assert len(excluded) == len(LLM_CE_IDS)
    assert {r["scenarioId"] for r in excluded} == set(LLM_CE_IDS)
    run = [r for r in results if not r.get("excluded")]
    assert len(run) == TRACTABLE_COUNT
    assert all(r["passed"] for r in run)


def test_deterministic_gate_full_corpus_fails_on_llm_ce_only():
    passed, results = run_gate(REPO, "deterministic", exclude_llm_fallback=False)
    assert not passed
    failures = [r for r in results if not r["passed"]]
    assert {r["scenarioId"] for r in failures} == set(LLM_CE_IDS)
    assert len(results) == MANIFEST_COUNT


def test_hybrid_cassette_gate_passes_all():
    passed, results = run_gate(REPO, "hybrid", llm_backend="cassette")
    assert passed, results
    assert len(results) == MANIFEST_COUNT


def test_llm_only_cassette_gate_passes_all():
    passed, results = run_gate(REPO, "llm-only", llm_backend="cassette")
    assert passed, results
    assert len(results) == MANIFEST_COUNT


def test_hybrid_skips_llm_when_deterministic_closes_new_period():
    scenario = load_scenario(REPO, "roster.new_period.undersched.v1")
    rows = resolve_hybrid(
        scenario.payload, REPO, scenario.scenario_id, llm_backend="cassette"
    )
    assert len(rows) == 1
    assert rows[0].generated_by == "deterministic"
    assert rows[0].adjustment is not None
    assert rows[0].adjustment.work_date == "2024-06-25"


def test_cluster_notes_deterministic_abstains():
    for sid in LLM_CE_IDS:
        scenario = load_scenario(REPO, sid)
        assert resolve_deterministic(scenario.payload) == []


def test_cluster_notes_hybrid_uses_llm_fallback():
    scenario = load_scenario(REPO, CLUSTER_CE)
    rows = resolve_hybrid(
        scenario.payload, REPO, scenario.scenario_id, llm_backend="cassette"
    )
    assert rows[0].generated_by == "hybrid_llm_cassette"
    assert rows[0].modify is not None
    assert rows[0].modify.booking_id == 1901


def test_cluster_notes_triplet_hybrid_cancels_middle_orphan():
    scenario = load_scenario(REPO, TRIPLET_CE)
    rows = resolve_hybrid(
        scenario.payload, REPO, scenario.scenario_id, llm_backend="cassette"
    )
    assert rows[0].generated_by == "hybrid_llm_cassette"
    assert rows[0].modify is not None
    assert rows[0].modify.booking_id == 2102


def test_new_period_work_date():
    scenario = load_scenario(REPO, "roster.new_period.undersched.v1")
    row = build_rows(scenario.payload)[0]
    assert row.adjustment is not None
    assert row.adjustment.work_date == "2024-06-25"


def test_kiosk_cancel_higher_booking():
    scenario = load_scenario(REPO, "roster.kiosk_double_booking.v1")
    row = build_rows(scenario.payload)[0]
    assert row.op == "modify"
    assert row.modify is not None
    assert row.modify.booking_id == 1802


def test_comparer_catches_work_date_mismatch():
    expected = SuggestionRow(
        employee_id="E-1",
        issue_type="coverage-hour-gap",
        op="append",
        suggestion="",
        generated_by="golden",
        adjustment=WireAdjustment(shift_kind=51, hours=-1.0, work_date="2024-06-25"),
    )
    actual = SuggestionRow(
        employee_id="E-1",
        issue_type="coverage-hour-gap",
        op="append",
        suggestion="",
        generated_by="llm",
        adjustment=WireAdjustment(shift_kind=51, hours=-1.0, work_date="2024-06-24"),
    )
    ok, notes = compare_rows(expected, actual)
    assert not ok
    assert any("workDate" in n for n in notes)


def test_cassette_llm_resolves_kiosk():
    scenario = load_scenario(REPO, "roster.kiosk_double_booking.v1")
    rows = resolve_llm_only(
        scenario.payload, REPO, scenario.scenario_id, backend="cassette"
    )
    assert rows[0].modify is not None
    assert rows[0].modify.booking_id == 1802


def test_row_closes_delta_rejects_wrong_append():
    scenario = load_scenario(REPO, "roster.kiosk_double_booking.v1")
    emp = scenario.payload.departments[0][0]
    bad = SuggestionRow(
        employee_id=emp.employee_id,
        issue_type="coverage-hour-gap",
        op="append",
        suggestion="wrong",
        generated_by="deterministic",
        adjustment=WireAdjustment(shift_kind=51, hours=-20.0, work_date=emp.window_end),
    )
    assert not _row_closes_delta(emp, bad)


def test_kiosk_hybrid_uses_deterministic_without_fallback():
    scenario = load_scenario(REPO, "roster.kiosk_double_booking.v1")
    rows = resolve_hybrid(
        scenario.payload, REPO, scenario.scenario_id, llm_backend="cassette"
    )
    assert rows[0].generated_by == "deterministic"
    assert rows[0].modify is not None
    assert rows[0].modify.booking_id == 1802


def test_bench_prompt_includes_decision_order_and_payload():
    from io import StringIO
    import contextlib

    from rostersynth.cli import main

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["prompt", "roster.kiosk_double_booking.v1", "--part", "user"]) == 0
    out = buf.getvalue()
    assert "DECISION ORDER" in out
    assert "E-1800" in out
    assert "Op 2" in out
