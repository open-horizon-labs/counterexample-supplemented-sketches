"""Live Bedrock integration — uses Recon local-dev AWS profile `review`."""

from __future__ import annotations

from pathlib import Path

import pytest

from rostersynth.eval.scenarios import load_scenario
from rostersynth.oracle.bedrock import bedrock_credentials_ok, invoke_bedrock
from rostersynth.oracle.prompt import load_sketch
from rostersynth.resolver.llm import resolve_llm_only

REPO = Path(__file__).resolve().parents[1]


def _bedrock_available() -> bool:
    import os

    if os.environ.get("ROSTERSYNTH_SKIP_BEDROCK") == "1":
        return False
    return bedrock_credentials_ok()


@pytest.mark.skipif(not _bedrock_available(), reason="AWS SSO profile not available (aws sso login --profile review)")
def test_bedrock_tool_invoke_smoke():
    sketch = load_sketch(REPO)
    payload = invoke_bedrock(
        sketch,
        'Apply sketch to empty roster: {"departments": []}. Return suggestions: [].',
    )
    assert "suggestions" in payload


@pytest.mark.skipif(not _bedrock_available(), reason="AWS SSO profile not available (aws sso login --profile review)")
def test_bedrock_oracle_kiosk_scenario():
    scenario = load_scenario(REPO, "roster.kiosk_double_booking.v1")
    rows = resolve_llm_only(
        scenario.payload, REPO, scenario.scenario_id, backend="bedrock"
    )
    assert len(rows) == 1
    assert rows[0].employee_id == "E-1800"
    assert rows[0].op in ("append", "modify")
