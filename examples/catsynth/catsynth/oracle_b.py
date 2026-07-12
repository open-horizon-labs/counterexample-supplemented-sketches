"""Oracle B: prompt-mediated completion for the narrative hole.

Oracle B interprets an owner's free-text `narrative_note` into *additional soft
constraints only*. It may never relax a hard rule. The LLM is behind a small
pluggable interface; the default is a deterministic mock so the gate stays
model-free. A real client can be swapped in without touching the resolver.
"""

from __future__ import annotations

import os
from typing import Protocol

from .models import OwnerProfile

OLLAMA_HOST = os.environ.get("CATSYNTH_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("CATSYNTH_OLLAMA_MODEL", "qwen2.5-coder:14b")

# The controlled vocabulary Oracle B is allowed to emit. Each tag maps to one
# soft (discourage) pseudo-rule merged into Oracle A's ranking. These are
# already gated by the presence of a narrative note (see
# derive_soft_constraints), so unlike the DB rules they carry no owner-trait
# trigger: they are applied directly and only name the cat attribute to penalize.
TAG_TO_SOFT_RULE = {
    "avoid_needy": {
        "id": "nb_avoid_needy", "kind": "discourage",
        "cat_attribute": "sociability", "cat_op": "gte", "cat_value": "high",
        "reason": "Narrative note: owner is frequently away; highly social breeds discouraged.",
    },
    "avoid_vocal": {
        "id": "nb_avoid_vocal", "kind": "discourage",
        "cat_attribute": "vocal", "cat_op": "gte", "cat_value": "high",
        "reason": "Narrative note: owner wants a quiet home; very vocal breeds discouraged.",
    },
    "avoid_high_energy": {
        "id": "nb_avoid_high_energy", "kind": "discourage",
        "cat_attribute": "energy", "cat_op": "gte", "cat_value": "high",
        "reason": "Narrative note: owner wants a low-key cat; high-energy breeds discouraged.",
    },
}

PROMPT_TEMPLATE = """You map an owner's free-text note to zero or more soft
constraint tags for a cat recommendation. Allowed tags (comma-separated, no
other text):
- avoid_needy: the owner is often away / worried about a lonely cat
- avoid_vocal: the owner wants a quiet home / dislikes noise
- avoid_high_energy: the owner wants a calm, low-key cat

You may not forbid anything; only emit soft tags. If none apply, output NONE.

Owner note: "{note}"
Tags:"""


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


class MockLLM:
    """Deterministic stand-in: keyword rules that emulate the model's mapping.

    Keeps the gate reproducible and CI model-free. Swap for a real client with
    the same `complete(prompt) -> str` signature to use an actual model.
    """

    name = "mock"

    def complete(self, prompt: str) -> str:
        note = prompt.lower()
        tags = []
        if any(k in note for k in ("travel", "away", "gone", "lonely", "alone", "miserable")):
            tags.append("avoid_needy")
        if any(k in note for k in ("quiet", "noise", "loud", "noisy")):
            tags.append("avoid_vocal")
        if any(k in note for k in ("calm", "low-key", "low key", "relax", "mellow", "laid-back")):
            tags.append("avoid_high_energy")
        return ",".join(tags) if tags else "NONE"


class OllamaLLM:
    """Prompt-mediated completion backed by a local Ollama server.

    Uses the same `complete(prompt) -> str` contract as MockLLM, so it drops
    straight into the resolver. The gate still defaults to MockLLM to stay
    deterministic; Ollama is opt-in (e.g. from the Playground).
    """

    def __init__(self, model: str = OLLAMA_MODEL, host: str = OLLAMA_HOST, timeout: int = 60):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.name = f"ollama:{model}"

    def complete(self, prompt: str) -> str:
        import requests
        resp = requests.post(
            f"{self.host}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0}},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip()


def make_client(name: str = "mock", model: str = OLLAMA_MODEL) -> LLMClient:
    """Select an Oracle B backend by name ('mock' or 'ollama')."""
    if name == "ollama":
        return OllamaLLM(model=model)
    return MockLLM()


def _extract_tags(raw: str) -> list[str]:
    """Robustly pull known tags out of a completion (handles prose from real
    models, not just clean comma lists)."""
    low = raw.lower()
    return [tag for tag in TAG_TO_SOFT_RULE if tag in low]


def derive_soft_constraints(owner: OwnerProfile, client: LLMClient):
    """Return (list_of_soft_rule_dicts, trace). Empty if no narrative note."""
    if not owner.narrative_note:
        return [], {"used": False}
    prompt = PROMPT_TEMPLATE.format(note=owner.narrative_note)
    raw = (client.complete(prompt) or "").strip()
    tags = _extract_tags(raw)
    soft_rules = [TAG_TO_SOFT_RULE[t] for t in tags]
    return soft_rules, {
        "used": True,
        "backend": getattr(client, "name", client.__class__.__name__),
        "raw_completion": raw,
        "tags": tags,
        "derived_rule_ids": [r["id"] for r in soft_rules],
    }
