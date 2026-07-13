"""FastAPI app: the local review surface + gate runner.

Endpoints back a single-page UI where an SME can inspect a scenario, see the
resolver's proposed recommendation (policy or naive), correct it, promote it
into the golden corpus, and run the gate.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, oracle_b, resolver
from .gate import run_gate
from .models import Operation, OwnerProfile, Recommendation

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SKETCH_PATH = os.path.join(os.path.dirname(__file__), "..", "sketch", "SKETCH.md")

app = FastAPI(title="CatSynth", description="Agentic synthesis loop demo")


def _conn():
    return db.connect()


@app.get("/api/breeds")
def api_breeds():
    conn = _conn()
    try:
        return [b.to_dict() for b in db.get_breeds(conn)]
    finally:
        conn.close()


@app.get("/api/rules")
def api_rules():
    conn = _conn()
    try:
        return db.get_rules(conn)
    finally:
        conn.close()


@app.get("/api/scenarios")
def api_scenarios():
    conn = _conn()
    try:
        corpus_ids = {c["scenario_id"] for c in db.get_corpus(conn)}
        out = []
        for s in db.get_scenarios(conn):
            d = s.to_dict()
            d["promoted"] = s.scenario_id in corpus_ids
            out.append(d)
        return out
    finally:
        conn.close()


@app.get("/api/suggest/{scenario_id}")
def api_suggest(scenario_id: str, mode: str = "policy"):
    conn = _conn()
    try:
        owner = db.get_scenario(conn, scenario_id)
        if owner is None:
            raise HTTPException(404, f"unknown scenario {scenario_id!r}")
        rec = resolver.resolve(conn, owner, mode=mode)
        breed = db.get_breed(conn, rec.breed) if rec.breed else None
        return {
            "scenario": owner.to_dict(),
            "recommendation": rec.to_dict(),
            "breed_detail": breed.to_dict() if breed else None,
        }
    finally:
        conn.close()


@app.get("/api/corpus")
def api_corpus():
    conn = _conn()
    try:
        out = []
        for c in db.get_corpus(conn):
            out.append({
                "id": c["id"], "scenario_id": c["scenario_id"],
                "expected": c["expected"].to_dict(),
                "tempting": c["tempting"].to_dict() if c["tempting"] else None,
                "violated_rule": c["violated_rule"], "sketch_clause": c["sketch_clause"],
                "note": c["note"], "created_at": c["created_at"],
            })
        return out
    finally:
        conn.close()


class RecIn(BaseModel):
    operation: str
    breed: Optional[str] = None
    cited_rules: list[str] = []
    rationale: str = ""


class PromoteIn(BaseModel):
    scenario_id: str
    expected: RecIn
    tempting: Optional[RecIn] = None
    violated_rule: str = ""
    sketch_clause: str = ""
    note: str = ""


def _rec_from_in(r: RecIn) -> Recommendation:
    try:
        op = Operation(r.operation)
    except ValueError:
        raise HTTPException(400, f"invalid operation {r.operation!r}")
    return Recommendation(operation=op, breed=r.breed, cited_rules=r.cited_rules,
                          rationale=r.rationale)


@app.post("/api/corpus")
def api_promote(body: PromoteIn):
    conn = _conn()
    try:
        if db.get_scenario(conn, body.scenario_id) is None:
            raise HTTPException(404, f"unknown scenario {body.scenario_id!r}")
        new_id = db.promote_case(
            conn, body.scenario_id, _rec_from_in(body.expected),
            _rec_from_in(body.tempting) if body.tempting else None,
            body.violated_rule, body.sketch_clause, body.note,
        )
        return {"id": new_id, "status": "promoted"}
    finally:
        conn.close()


@app.delete("/api/corpus/{entry_id}")
def api_delete_corpus(entry_id: int):
    conn = _conn()
    try:
        if not db.delete_corpus_entry(conn, entry_id):
            raise HTTPException(404, f"corpus entry {entry_id} not found")
        return {"id": entry_id, "status": "deleted"}
    finally:
        conn.close()


@app.post("/api/gate/run")
def api_gate_run(mode: str = "policy"):
    conn = _conn()
    try:
        return run_gate(conn, mode=mode)
    finally:
        conn.close()


@app.get("/api/gate/runs")
def api_gate_runs():
    conn = _conn()
    try:
        return db.get_gate_runs(conn)
    finally:
        conn.close()


@app.get("/api/llm")
def api_llm_status():
    """Report models exposed by the configured OpenAI-compatible API."""
    from .openai_compat import OpenAICompatibleClient
    base_url = oracle_b.LLM_BASE_URL
    try:
        models = OpenAICompatibleClient(base_url=base_url, timeout=5).list_models()
        return {"available": True, "base_url": base_url, "models": models,
                "default_model": oracle_b.LLM_MODEL}
    except Exception as exc:
        return {"available": False, "base_url": base_url, "models": [],
                "default_model": oracle_b.LLM_MODEL, "error": str(exc)}


class ProfileIn(BaseModel):
    label: str = "ad-hoc request"
    allergies: str = "none"
    work_hours: str = "normal"
    home_size: str = "house"
    young_children: bool = False
    activity_level: str = "moderate"
    noise_tolerance: str = "high"
    experience: str = "experienced"
    wants_size: Optional[str] = None
    wants_affection: bool = False
    wants_fluffy: bool = False
    narrative_note: Optional[str] = None
    mode: str = "policy"
    oracle_b: str = "mock"          # mock | local
    llm_model: Optional[str] = None


@app.post("/api/test-suggest")
def api_test_suggest(body: ProfileIn):
    """Run the resolver on an ad-hoc profile (not a stored scenario). Oracle B
    can be backed by the mock or an OpenAI-compatible local model."""
    owner = OwnerProfile(
        scenario_id="__adhoc__", label=body.label,
        allergies=body.allergies, work_hours=body.work_hours, home_size=body.home_size,
        young_children=body.young_children, activity_level=body.activity_level,
        noise_tolerance=body.noise_tolerance, experience=body.experience,
        wants_size=body.wants_size or None, wants_affection=body.wants_affection,
        wants_fluffy=body.wants_fluffy, narrative_note=body.narrative_note or None,
    )
    client = oracle_b.make_client(body.oracle_b,
                                  model=body.llm_model or oracle_b.LLM_MODEL)
    conn = _conn()
    try:
        try:
            rec = resolver.resolve(conn, owner, mode=body.mode, llm_client=client)
        except Exception as exc:
            raise HTTPException(502, f"Oracle B ({body.oracle_b}) call failed: {exc}")
        breed = db.get_breed(conn, rec.breed) if rec.breed else None
        return {
            "scenario": owner.to_dict(),
            "recommendation": rec.to_dict(),
            "breed_detail": breed.to_dict() if breed else None,
        }
    finally:
        conn.close()


@app.get("/api/sketch")
def api_sketch():
    try:
        with open(SKETCH_PATH, encoding="utf-8") as fh:
            return {"markdown": fh.read()}
    except OSError:
        return {"markdown": "# Sketch not found"}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
