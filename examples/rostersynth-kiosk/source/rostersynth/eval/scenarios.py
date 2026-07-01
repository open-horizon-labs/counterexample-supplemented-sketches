from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rostersynth.models import Payload, SuggestionRow


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    payload: Payload
    expected: list[SuggestionRow]
    outcome_kind: str = "fix"
    requires_llm_fallback: bool = False

    @classmethod
    def load(cls, path: Path) -> Scenario:
        raw = json.loads(path.read_text())
        expectations = raw.get("expectations", {}).get("resolver", {}).get("suggestions", [])
        return cls(
            scenario_id=raw["id"],
            title=raw.get("title", raw["id"]),
            payload=Payload.from_dict(raw["inputPayload"]),
            expected=[SuggestionRow.from_dict(x) for x in expectations],
            outcome_kind=raw.get("outcomeKind", "fix"),
            requires_llm_fallback=bool(raw.get("requiresLlmFallback", False)),
        )


def load_manifest(repo_root: Path) -> list[str]:
    manifest_path = repo_root / "scenarios" / "manifest.json"
    data = json.loads(manifest_path.read_text())
    return list(data["scenarioIds"])


def load_scenario(repo_root: Path, scenario_id: str) -> Scenario:
    path = repo_root / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_id}")
    return Scenario.load(path)


def llm_fallback_scenario_ids(repo_root: Path) -> frozenset[str]:
    """Scenario ids tagged ``requiresLlmFallback`` (Oracle A abstains by design)."""
    return frozenset(
        sid
        for sid in load_manifest(repo_root)
        if load_scenario(repo_root, sid).requires_llm_fallback
    )
