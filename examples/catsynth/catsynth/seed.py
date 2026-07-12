"""Seed the SQLite database.

- Cat facts: structured attributes are curated here; the free-text `summary`
  and `wiki_url` are fetched once from Wikipedia's REST summary API and cached
  into SQLite so the demo runs fully offline afterward.
- Rules: the owner-trait rulesets (local policy tables).
- Scenarios: owner profiles (input scenarios x).
- Golden corpus: promoted counterexamples (including the FR-1 allergy case).
"""

from __future__ import annotations

import sys
import time

from . import db
from .models import Breed, OwnerProfile, Operation, Recommendation

WIKI_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_QUERY_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "CatSynth/0.1 (agentic-synthesis sample; contact: local demo)"

# name -> Wikipedia page title
WIKI_TITLES = {
    "Persian": "Persian cat",
    "Maine Coon": "Maine Coon",
    "Siberian": "Siberian cat",
    "Ragdoll": "Ragdoll",
    "Siamese": "Siamese cat",
    "Balinese": "Balinese cat",
    "Sphynx": "Sphynx cat",
    "Russian Blue": "Russian Blue",
    "British Shorthair": "British Shorthair",
    "Bengal": "Bengal cat",
    "Abyssinian": "Abyssinian cat",
    "Devon Rex": "Devon Rex",
}

# Curated structured attributes. Values use the ordinal scales from models.py.
BREEDS = [
    #        name              size      energy      shedding    grooming    sociability vocal       affection   hypo   kids   fluffy
    Breed("Persian",           "large",  "low",      "high",     "high",     "moderate", "low",      "high",     False, True,  True),
    Breed("Maine Coon",        "large",  "moderate", "high",     "high",     "high",     "moderate", "high",     False, True,  True),
    Breed("Siberian",          "large",  "moderate", "moderate", "moderate", "moderate", "low",      "high",     True,  True,  True),
    Breed("Ragdoll",           "large",  "low",      "moderate", "moderate", "high",     "low",      "high",     False, True,  True),
    Breed("Siamese",           "medium", "high",     "low",      "low",      "high",     "high",     "high",     False, True,  False),
    Breed("Balinese",          "medium", "moderate", "low",      "moderate", "high",     "moderate", "high",     True,  True,  True),
    Breed("Sphynx",            "medium", "high",     "low",      "high",     "high",     "moderate", "high",     False, True,  False),
    Breed("Russian Blue",      "medium", "moderate", "low",      "low",      "moderate", "low",      "moderate", True,  False, False),
    Breed("British Shorthair", "large",  "low",      "moderate", "low",      "low",      "low",      "moderate", False, True,  False),
    Breed("Bengal",            "medium", "high",     "low",      "low",      "high",     "high",     "moderate", False, True,  False),
    Breed("Abyssinian",        "medium", "high",     "low",      "low",      "high",     "moderate", "moderate", False, True,  False),
    Breed("Devon Rex",         "small",  "high",     "low",      "low",      "high",     "moderate", "high",     True,  True,  False),
]

# Owner-trait rulesets. kind=forbid is a HARD rule (removes the breed);
# kind=discourage is SOFT (penalizes the breed in ranking).
RULES = [
    {"id": "allergy_requires_hypoallergenic", "trait": "allergies", "trait_op": "in",
     "trait_value": "mild,severe", "kind": "forbid", "cat_attribute": "hypoallergenic",
     "cat_op": "is_false", "cat_value": "",
     "reason": "Owner has allergies: non-hypoallergenic breeds are forbidden."},
    {"id": "severe_allergy_low_shedding", "trait": "allergies", "trait_op": "eq",
     "trait_value": "severe", "kind": "forbid", "cat_attribute": "shedding",
     "cat_op": "gte", "cat_value": "moderate",
     "reason": "Severe allergies: breeds that shed moderately or more are forbidden."},
    {"id": "apartment_no_high_energy", "trait": "home_size", "trait_op": "eq",
     "trait_value": "apartment", "kind": "forbid", "cat_attribute": "energy",
     "cat_op": "gte", "cat_value": "high",
     "reason": "Apartment: high-energy breeds need more space than an apartment offers."},
    {"id": "long_hours_no_high_sociability", "trait": "work_hours", "trait_op": "eq",
     "trait_value": "long", "kind": "forbid", "cat_attribute": "sociability",
     "cat_op": "gte", "cat_value": "high",
     "reason": "Long work hours: highly social breeds suffer during long absences."},
    {"id": "children_require_good_with_children", "trait": "young_children", "trait_op": "is_true",
     "trait_value": "", "kind": "forbid", "cat_attribute": "good_with_children",
     "cat_op": "is_false", "cat_value": "",
     "reason": "Young children present: breeds not good with children are forbidden."},
    {"id": "apartment_discourage_large", "trait": "home_size", "trait_op": "eq",
     "trait_value": "apartment", "kind": "discourage", "cat_attribute": "size",
     "cat_op": "gte", "cat_value": "large",
     "reason": "Apartment: large breeds are discouraged."},
    {"id": "low_noise_discourage_vocal", "trait": "noise_tolerance", "trait_op": "eq",
     "trait_value": "low", "kind": "discourage", "cat_attribute": "vocal",
     "cat_op": "gte", "cat_value": "high",
     "reason": "Low noise tolerance: very vocal breeds are discouraged."},
    {"id": "low_activity_discourage_high_energy", "trait": "activity_level", "trait_op": "eq",
     "trait_value": "low", "kind": "discourage", "cat_attribute": "energy",
     "cat_op": "gte", "cat_value": "high",
     "reason": "Low owner activity: high-energy breeds are discouraged."},
    {"id": "novice_discourage_high_energy", "trait": "experience", "trait_op": "eq",
     "trait_value": "novice", "kind": "discourage", "cat_attribute": "energy",
     "cat_op": "gte", "cat_value": "high",
     "reason": "Novice owner: demanding high-energy breeds are discouraged."},
]

SCENARIOS = [
    OwnerProfile(
        scenario_id="allergy_lapcat",
        label="Allergic owner wants a big fluffy affectionate lap cat",
        allergies="mild", wants_size="large", wants_affection=True, wants_fluffy=True,
    ),
    OwnerProfile(
        scenario_id="novice_quiet",
        label="First-time owner, quiet home, wants a calm affectionate cat",
        experience="novice", noise_tolerance="low", activity_level="low",
        wants_affection=True, wants_fluffy=True,
    ),
    OwnerProfile(
        scenario_id="over_constrained",
        label="Severe allergies + apartment + long hours + young children",
        allergies="severe", home_size="apartment", work_hours="long",
        young_children=True, wants_affection=True,
    ),
    OwnerProfile(
        scenario_id="apartment_busy",
        label="Apartment dweller with long work hours, wants an affectionate cat",
        home_size="apartment", work_hours="long", wants_affection=True,
    ),
    OwnerProfile(
        scenario_id="narrative_travel",
        label="Owner travels often; details only in a free-text note",
        wants_affection=True,
        narrative_note=("I travel for work every few weeks and my last cat seemed "
                        "miserable and lonely whenever I was gone for days."),
    ),
]


def _fetch_rest(title: str):
    import requests
    url = WIKI_SUMMARY_API + requests.utils.quote(title.replace(" ", "_"))
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    extract = data.get("extract", "") or ""
    page_url = (data.get("content_urls", {}).get("desktop", {}).get("page")
                or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
    return extract, page_url


def _fetch_query(title: str):
    """Fallback: the classic MediaWiki action API (separate endpoint from REST)."""
    import requests
    resp = requests.get(
        WIKI_QUERY_API,
        params={"action": "query", "prop": "extracts", "exintro": 1,
                "explaintext": 1, "redirects": 1, "format": "json", "titles": title},
        headers={"User-Agent": USER_AGENT}, timeout=15,
    )
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract", "") or ""
        if extract:
            return extract, f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    return "", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"


def fetch_wiki(title: str):
    """Return (extract, url) from Wikipedia, trying REST then the action API."""
    fallback_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
    for fetcher in (_fetch_rest, _fetch_query):
        try:
            extract, page_url = fetcher(title)
            if extract:
                return extract, page_url
        except Exception as exc:
            print(f"  ! {fetcher.__name__} failed for {title!r}: {exc}", file=sys.stderr)
    return "", fallback_url


def seed_all(conn, fetch_wiki_facts: bool = True, refresh_wiki: bool = False) -> None:
    db.init_db(conn)

    print("Seeding breeds...")
    for b in BREEDS:
        existing = db.get_breed(conn, b.name)
        # Preserve any already-cached wiki text unless refreshing.
        if existing and existing.summary and not refresh_wiki:
            b.summary, b.wiki_url = existing.summary, existing.wiki_url
        db.upsert_breed(conn, b)

    if fetch_wiki_facts:
        print("Fetching Wikipedia facts (cached into SQLite)...")
        for b in BREEDS:
            existing = db.get_breed(conn, b.name)
            if existing and existing.summary and not refresh_wiki:
                print(f"  = {b.name}: cached")
                continue
            title = WIKI_TITLES.get(b.name, b.name)
            extract, page_url = fetch_wiki(title)
            db.set_breed_wiki(conn, b.name, extract, page_url)
            status = "ok" if extract else "no extract (offline?)"
            print(f"  + {b.name}: {status}")
            time.sleep(0.4)  # be polite to the Wikipedia API (avoid 429s)

    print("Seeding rules...")
    for r in RULES:
        db.upsert_rule(conn, r)

    print("Seeding scenarios...")
    for s in SCENARIOS:
        db.upsert_scenario(conn, s)

    print("Seeding golden corpus...")
    _seed_corpus(conn)
    print("Done.")


def _seed_corpus(conn) -> None:
    """Promote the initial counterexamples if they are not present yet."""
    # FR-1: the worked counterexample. Tempting repair = Persian; correct = Siberian.
    if not db.corpus_has_scenario(conn, "allergy_lapcat"):
        db.promote_case(
            conn, "allergy_lapcat",
            expected=Recommendation(
                operation=Operation.RECOMMEND, breed="Siberian",
                cited_rules=["allergy_requires_hypoallergenic"],
                rationale="Big, fluffy, affectionate AND hypoallergenic.",
            ),
            tempting=Recommendation(
                operation=Operation.RECOMMEND, breed="Persian",
                cited_rules=[],
                rationale="Highest preference match, but non-hypoallergenic.",
            ),
            violated_rule="allergy_requires_hypoallergenic",
            sketch_clause="FR-1 allergy override",
            note=("Persian closes the 'big/fluffy/affectionate' gap and passes replay, "
                  "but violates the allergy rule. Compare must reject it on `breed`."),
        )
    # Happy path: same catalog, but here Persian IS correct (no allergy).
    if not db.corpus_has_scenario(conn, "novice_quiet"):
        db.promote_case(
            conn, "novice_quiet",
            expected=Recommendation(
                operation=Operation.RECOMMEND, breed="Persian", cited_rules=[],
                rationale="Calm, low-vocal, affectionate lap cat; no hard rule applies.",
            ),
            tempting=None,
            violated_rule="",
            sketch_clause="RECOMMEND ranking",
            note="Happy path: replay and compare both accept.",
        )
    # Abstention: hard rules empty the candidate set.
    if not db.corpus_has_scenario(conn, "over_constrained"):
        db.promote_case(
            conn, "over_constrained",
            expected=Recommendation(
                operation=Operation.ABSTAIN, breed=None,
                cited_rules=[
                    "allergy_requires_hypoallergenic",
                    "apartment_no_high_energy",
                    "children_require_good_with_children",
                    "long_hours_no_high_sociability",
                    "severe_allergy_low_shedding",
                ],
                rationale="No breed satisfies all hard rules; decline rather than force a fit.",
            ),
            tempting=None,
            violated_rule="",
            sketch_clause="Abstention rule",
            note="No survivor after hard filtering; must ABSTAIN, not relax a hard rule.",
        )


if __name__ == "__main__":
    conn = db.connect()
    seed_all(conn, fetch_wiki_facts=True)
    conn.close()
