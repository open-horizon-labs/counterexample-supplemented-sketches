from __future__ import annotations

import json
import os
from pathlib import Path

from rostersynth.models import Payload, SuggestionRow
from rostersynth.oracle.bedrock import invoke_bedrock
from rostersynth.oracle.cassette import load_cassette
from rostersynth.oracle.prompt import build_user_prompt, load_sketch
from rostersynth.resolver.deterministic import payload_to_prompt_dict


def default_llm_backend() -> str:
    return os.environ.get("ROSTERSYNTH_LLM", "bedrock").strip().lower()


def resolve_llm_only(
    payload: Payload,
    repo_root: Path,
    scenario_id: str,
    *,
    backend: str | None = None,
) -> list[SuggestionRow]:
    backend = (backend or default_llm_backend()).lower()
    if backend == "cassette":
        return load_cassette(repo_root, scenario_id)
    if backend == "bedrock":
        sketch = load_sketch(repo_root)
        user_prompt = build_user_prompt(payload_to_prompt_dict(payload))
        tool_payload = invoke_bedrock(sketch, user_prompt)
        rows = _rows_from_tool_payload(tool_payload)
        if os.environ.get("ROSTERSYNTH_RECORD_CASSETTE") == "1":
            _record_cassette(repo_root, scenario_id, rows)
        return rows
    raise ValueError(f"Unknown LLM backend: {backend}. Use bedrock or cassette.")


def _rows_from_tool_payload(payload: dict) -> list[SuggestionRow]:
    suggestions = payload.get("suggestions", [])
    if not isinstance(suggestions, list):
        raise ValueError("Bedrock tool payload missing suggestions array")
    return [SuggestionRow.from_dict({**item, "generatedBy": "bedrock"}) for item in suggestions]


def _record_cassette(repo_root: Path, scenario_id: str, rows: list[SuggestionRow]) -> None:
    path = repo_root / "cassettes" / f"{scenario_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scenarioId": scenario_id,
                "mode": "llm-only",
                "generatedBy": "bedrock-record",
                "suggestions": [r.to_dict() for r in rows],
            },
            indent=2,
        )
        + "\n"
    )
