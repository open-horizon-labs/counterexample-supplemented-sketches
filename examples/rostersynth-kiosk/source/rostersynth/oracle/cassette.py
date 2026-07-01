from __future__ import annotations

import json
from pathlib import Path

from rostersynth.models import SuggestionRow


def load_cassette(repo_root: Path, scenario_id: str) -> list[SuggestionRow]:
    cassette_path = repo_root / "cassettes" / f"{scenario_id}.json"
    if not cassette_path.exists():
        raise FileNotFoundError(
            f"No cassette for {scenario_id}. Run with ROSTERSYNTH_LLM=bedrock "
            f"and ROSTERSYNTH_RECORD_CASSETTE=1, or add cassettes/{scenario_id}.json"
        )
    raw = json.loads(cassette_path.read_text())
    return [SuggestionRow.from_dict(x) for x in raw["suggestions"]]
