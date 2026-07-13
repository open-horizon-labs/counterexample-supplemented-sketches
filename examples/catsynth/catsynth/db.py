"""SQLite persistence layer.

Tables:
  breeds         - cat facts (Wikipedia-sourced summary + curated attributes)
  rules          - owner-trait rulesets (the local policy tables)
  scenarios      - owner profiles (input scenarios x)
  golden_corpus  - promoted counterexamples E (expected output + tempting repair)
  gate_runs      - provenance log of gate executions
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from . import DB_PATH
from .models import Breed, OwnerProfile, Recommendation


SCHEMA = """
CREATE TABLE IF NOT EXISTS breeds (
    name                TEXT PRIMARY KEY,
    size                TEXT NOT NULL,
    energy              TEXT NOT NULL,
    shedding            TEXT NOT NULL,
    grooming            TEXT NOT NULL,
    sociability         TEXT NOT NULL,
    vocal               TEXT NOT NULL,
    affection           TEXT NOT NULL,
    hypoallergenic      INTEGER NOT NULL,
    good_with_children  INTEGER NOT NULL,
    fluffy              INTEGER NOT NULL,
    summary             TEXT DEFAULT '',
    wiki_url            TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rules (
    id            TEXT PRIMARY KEY,
    trait         TEXT NOT NULL,
    trait_op      TEXT NOT NULL,
    trait_value   TEXT DEFAULT '',
    kind          TEXT NOT NULL,          -- forbid | discourage
    cat_attribute TEXT NOT NULL,
    cat_op        TEXT NOT NULL,
    cat_value     TEXT DEFAULT '',
    reason        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    profile_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS golden_corpus (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id    TEXT NOT NULL,
    expected_json  TEXT NOT NULL,
    tempting_json  TEXT DEFAULT '',
    violated_rule  TEXT DEFAULT '',
    sketch_clause  TEXT DEFAULT '',
    note           TEXT DEFAULT '',
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS gate_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT DEFAULT (datetime('now')),
    resolver_mode TEXT NOT NULL,
    passed       INTEGER NOT NULL,
    summary_json TEXT NOT NULL
);
"""


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# --- breeds -----------------------------------------------------------------

def upsert_breed(conn: sqlite3.Connection, b: Breed) -> None:
    conn.execute(
        """INSERT INTO breeds
           (name,size,energy,shedding,grooming,sociability,vocal,affection,
            hypoallergenic,good_with_children,fluffy,summary,wiki_url)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET
             size=excluded.size, energy=excluded.energy, shedding=excluded.shedding,
             grooming=excluded.grooming, sociability=excluded.sociability,
             vocal=excluded.vocal, affection=excluded.affection,
             hypoallergenic=excluded.hypoallergenic,
             good_with_children=excluded.good_with_children, fluffy=excluded.fluffy,
             summary=excluded.summary, wiki_url=excluded.wiki_url""",
        (b.name, b.size, b.energy, b.shedding, b.grooming, b.sociability, b.vocal,
         b.affection, int(b.hypoallergenic), int(b.good_with_children), int(b.fluffy),
         b.summary, b.wiki_url),
    )
    conn.commit()


def set_breed_wiki(conn: sqlite3.Connection, name: str, summary: str, url: str) -> None:
    conn.execute("UPDATE breeds SET summary=?, wiki_url=? WHERE name=?", (summary, url, name))
    conn.commit()


def _row_to_breed(r: sqlite3.Row) -> Breed:
    return Breed(
        name=r["name"], size=r["size"], energy=r["energy"], shedding=r["shedding"],
        grooming=r["grooming"], sociability=r["sociability"], vocal=r["vocal"],
        affection=r["affection"], hypoallergenic=bool(r["hypoallergenic"]),
        good_with_children=bool(r["good_with_children"]), fluffy=bool(r["fluffy"]),
        summary=r["summary"], wiki_url=r["wiki_url"],
    )


def get_breeds(conn: sqlite3.Connection) -> list[Breed]:
    return [_row_to_breed(r) for r in conn.execute("SELECT * FROM breeds ORDER BY name")]


def get_breed(conn: sqlite3.Connection, name: str) -> Optional[Breed]:
    r = conn.execute("SELECT * FROM breeds WHERE name=?", (name,)).fetchone()
    return _row_to_breed(r) if r else None


# --- rules ------------------------------------------------------------------

def upsert_rule(conn: sqlite3.Connection, rule: dict) -> None:
    conn.execute(
        """INSERT INTO rules (id,trait,trait_op,trait_value,kind,cat_attribute,cat_op,cat_value,reason)
           VALUES (:id,:trait,:trait_op,:trait_value,:kind,:cat_attribute,:cat_op,:cat_value,:reason)
           ON CONFLICT(id) DO UPDATE SET
             trait=excluded.trait, trait_op=excluded.trait_op, trait_value=excluded.trait_value,
             kind=excluded.kind, cat_attribute=excluded.cat_attribute, cat_op=excluded.cat_op,
             cat_value=excluded.cat_value, reason=excluded.reason""",
        rule,
    )
    conn.commit()


def get_rules(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM rules ORDER BY id")]


# --- scenarios --------------------------------------------------------------

def upsert_scenario(conn: sqlite3.Connection, p: OwnerProfile) -> None:
    conn.execute(
        """INSERT INTO scenarios (scenario_id,label,profile_json)
           VALUES (?,?,?)
           ON CONFLICT(scenario_id) DO UPDATE SET
             label=excluded.label, profile_json=excluded.profile_json""",
        (p.scenario_id, p.label, json.dumps(p.to_dict())),
    )
    conn.commit()


def get_scenarios(conn: sqlite3.Connection) -> list[OwnerProfile]:
    out = []
    for r in conn.execute("SELECT profile_json FROM scenarios ORDER BY scenario_id"):
        out.append(OwnerProfile(**json.loads(r["profile_json"])))
    return out


def get_scenario(conn: sqlite3.Connection, scenario_id: str) -> Optional[OwnerProfile]:
    r = conn.execute("SELECT profile_json FROM scenarios WHERE scenario_id=?", (scenario_id,)).fetchone()
    return OwnerProfile(**json.loads(r["profile_json"])) if r else None


# --- golden corpus ----------------------------------------------------------

def promote_case(conn: sqlite3.Connection, scenario_id: str, expected: Recommendation,
                 tempting: Optional[Recommendation], violated_rule: str,
                 sketch_clause: str, note: str) -> int:
    cur = conn.execute(
        """INSERT INTO golden_corpus
           (scenario_id,expected_json,tempting_json,violated_rule,sketch_clause,note)
           VALUES (?,?,?,?,?,?)""",
        (scenario_id, json.dumps(expected.to_dict()),
         json.dumps(tempting.to_dict()) if tempting else "",
         violated_rule, sketch_clause, note),
    )
    conn.commit()
    return cur.lastrowid


def get_corpus(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM golden_corpus ORDER BY id"):
        out.append({
            "id": r["id"],
            "scenario_id": r["scenario_id"],
            "expected": Recommendation.from_dict(json.loads(r["expected_json"])),
            "tempting": Recommendation.from_dict(json.loads(r["tempting_json"])) if r["tempting_json"] else None,
            "violated_rule": r["violated_rule"],
            "sketch_clause": r["sketch_clause"],
            "note": r["note"],
            "created_at": r["created_at"],
        })
    return out


def corpus_has_scenario(conn: sqlite3.Connection, scenario_id: str) -> bool:
    r = conn.execute("SELECT 1 FROM golden_corpus WHERE scenario_id=?", (scenario_id,)).fetchone()
    return r is not None


def delete_corpus_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    """Remove one promoted counterexample by id. Returns True if a row was deleted."""
    cur = conn.execute("DELETE FROM golden_corpus WHERE id=?", (entry_id,))
    conn.commit()
    return cur.rowcount > 0


# --- gate runs --------------------------------------------------------------

def log_gate_run(conn: sqlite3.Connection, resolver_mode: str, passed: bool, summary: dict) -> int:
    cur = conn.execute(
        "INSERT INTO gate_runs (resolver_mode,passed,summary_json) VALUES (?,?,?)",
        (resolver_mode, int(passed), json.dumps(summary)),
    )
    conn.commit()
    return cur.lastrowid


def get_gate_runs(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM gate_runs ORDER BY id DESC LIMIT ?", (limit,)):
        out.append({
            "id": r["id"], "created_at": r["created_at"],
            "resolver_mode": r["resolver_mode"], "passed": bool(r["passed"]),
            "summary": json.loads(r["summary_json"]),
        })
    return out
