"""Domain types = known-code anchors (K).

These dataclasses are the output shape the agent must preserve. The gate,
the oracles, the API, and the UI all speak in terms of `Recommendation`.
The *policy-bearing* fields (see `policy_fields`) are the ones semantic
compare checks; everything else in a recommendation is diagnostic trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Operation(str, Enum):
    """The operations the strategy may choose among.

    RECOMMEND: name a concrete breed for the owner.
    ABSTAIN:   deliberately decline because no breed satisfies the hard rules.
    ESCALATE:  hand off to a human because the case is out of policy scope.
    """

    RECOMMEND = "recommend"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"


# Ordinal scales let rules compare "high energy" style attributes numerically.
LEVELS = {"low": 0, "moderate": 1, "high": 2}
SIZES = {"small": 0, "medium": 1, "large": 2}


@dataclass
class Breed:
    """A cat breed. Structured attributes are curated locally; `summary` and
    `wiki_url` carry the Wikipedia-sourced fact text for provenance."""

    name: str
    size: str            # small | medium | large
    energy: str          # low | moderate | high
    shedding: str        # low | moderate | high
    grooming: str        # low | moderate | high
    sociability: str     # low | moderate | high (how much it needs company)
    vocal: str           # low | moderate | high
    affection: str       # low | moderate | high (lap-cat tendency)
    hypoallergenic: bool
    good_with_children: bool
    fluffy: bool
    summary: str = ""
    wiki_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OwnerProfile:
    """The input scenario x: structured traits + soft preferences + an optional
    free-text narrative note that only Oracle B can interpret."""

    scenario_id: str
    label: str
    # Traits (drive the hard/soft rules).
    allergies: str = "none"          # none | mild | severe
    work_hours: str = "normal"       # home | normal | long
    home_size: str = "house"         # apartment | house
    young_children: bool = False
    activity_level: str = "moderate" # low | moderate | high
    noise_tolerance: str = "high"    # low | high
    experience: str = "experienced"  # novice | experienced
    # Preferences (drive the state gap that replay checks).
    wants_size: Optional[str] = None       # small | medium | large
    wants_affection: bool = False          # wants an affectionate / lap cat
    wants_fluffy: bool = False
    # Narrative hole for Oracle B.
    narrative_note: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Recommendation:
    """The output shape (both the expected y and the candidate r).

    Policy-bearing fields: operation, breed, cited_rules. Everything else is
    diagnostic and is ignored by semantic compare.
    """

    operation: Operation
    breed: Optional[str] = None
    cited_rules: list[str] = field(default_factory=list)
    rationale: str = ""
    oracle: str = ""                 # which surface produced it (A, B->A, naive)
    trace: dict = field(default_factory=dict)

    def policy_fields(self) -> dict:
        """The subset semantic compare enforces."""
        return {
            "operation": self.operation.value
            if isinstance(self.operation, Operation)
            else str(self.operation),
            "breed": self.breed,
            "cited_rules": sorted(self.cited_rules),
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["operation"] = self.operation.value if isinstance(self.operation, Operation) else self.operation
        return d

    @staticmethod
    def from_dict(d: dict) -> "Recommendation":
        return Recommendation(
            operation=Operation(d["operation"]),
            breed=d.get("breed"),
            cited_rules=list(d.get("cited_rules") or []),
            rationale=d.get("rationale", ""),
            oracle=d.get("oracle", ""),
            trace=d.get("trace") or {},
        )
