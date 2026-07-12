"""Hybrid resolver: Oracle A on structured traits first; route the narrative
note to Oracle B for extra soft constraints, then let Oracle A finalize.

Deterministic policy (all hard rules) always stays on the reliable path.
Oracle B can only add soft constraints, never relax a hard rule.
"""

from __future__ import annotations

from typing import Optional

from . import db, oracle_a, oracle_b
from .models import OwnerProfile, Recommendation
from .oracle_b import LLMClient, MockLLM


def resolve(conn, owner: OwnerProfile, mode: str = "policy",
            llm_client: Optional[LLMClient] = None) -> Recommendation:
    breeds = db.get_breeds(conn)
    rules = db.get_rules(conn)

    if mode == "naive":
        return oracle_a.resolve(owner, breeds, rules, mode="naive")

    client = llm_client or MockLLM()
    extra_soft, b_trace = oracle_b.derive_soft_constraints(owner, client)
    oracle_label = "B->A" if b_trace.get("used") and extra_soft else "A"

    rec = oracle_a.resolve(owner, breeds, rules, extra_soft=extra_soft,
                           mode="policy", oracle_label=oracle_label)
    rec.trace["oracle_b"] = b_trace
    return rec
