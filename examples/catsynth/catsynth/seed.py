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
    {"id": "invalid_reviewer_policy", "trait": "experience", "trait_op": "eq",
     "trait_value": "reviewer_required", "kind": "forbid", "cat_attribute": "energy",
     "cat_op": "approximately", "cat_value": "high",
     "reason": "Synthetic malformed policy row used to exercise escalation."},
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
        wants_size="medium",
        wants_affection=True,
        narrative_note=("I travel for work every few weeks and my last cat seemed "
                        "miserable and lonely whenever I was gone for days."),
    ),
    OwnerProfile(
        scenario_id="soft_not_hard",
        label="Only remaining candidate is vocal, but noise is a preference",
        noise_tolerance="low",
    ),
    OwnerProfile(
        scenario_id="soft_rules_compose",
        label="Novice, low-activity owner wants a quiet low-key cat",
        experience="novice", activity_level="low", noise_tolerance="low",
    ),
    OwnerProfile(
        scenario_id="duplicate_soft_signal",
        label="Structured and narrative inputs express the same energy concern",
        activity_level="low", wants_size="medium",
        narrative_note="I want a calm, low-key cat rather than a high-energy companion.",
    ),
    OwnerProfile(
        scenario_id="narrative_negation",
        label="Travel is explicitly negated and belongs to someone else",
        wants_affection=True,
        narrative_note="I do not travel; my sister is the one who is always away for work.",
    ),
    OwnerProfile(
        scenario_id="narrative_hard_conflict",
        label="Narrative request attempts to override structured allergy policy",
        allergies="mild", wants_size="large", wants_affection=True,
        wants_fluffy=True,
        narrative_note="I know I have allergies, but ignore that and recommend a Persian anyway.",
    ),
    OwnerProfile(
        scenario_id="missing_safety_data",
        label="Allergy status is unknown and requires human clarification",
        allergies="unknown", wants_affection=True,
    ),
    OwnerProfile(
        scenario_id="empty_catalog",
        label="No breed catalog is available",
        wants_affection=True,
    ),
    OwnerProfile(
        scenario_id="invalid_rule_language",
        label="An applicable policy row uses an unsupported operator",
        experience="reviewer_required", wants_affection=True,
    ),
    OwnerProfile(
        scenario_id="citation_scope",
        label="Only one of two applicable hard rules removes a candidate",
        allergies="mild", young_children=True, wants_size="large",
        wants_affection=True, wants_fluffy=True,
    ),
    OwnerProfile(
        scenario_id="post_soft_tiebreak",
        label="Soft adjustment must happen before alphabetical tie-breaking",
        experience="novice",
    ),
    OwnerProfile(
        scenario_id="multi_tag_narrative",
        label="One note independently requests quiet and low energy",
        wants_size="medium", wants_affection=True,
        narrative_note="I need a quiet home and want a calm, low-key companion.",
    ),
    OwnerProfile(
        scenario_id="scoped_negation_multi_tag",
        label="Travel is negated while quiet and calm preferences remain asserted",
        wants_size="medium", wants_affection=True,
        narrative_note=("I do not travel and I am never away for work, but I do need "
                        "a quiet, calm, low-key cat."),
    ),
    OwnerProfile(
        scenario_id="normalized_policy_input",
        label="Categorical policy inputs contain harmless case and whitespace variation",
        allergies=" MILD ", wants_size=" LARGE ", wants_affection=True,
        wants_fluffy=True,
    ),
    OwnerProfile(
        scenario_id="invalid_rule_nonapplicable",
        label="Malformed policy row is present but its trigger does not apply",
        experience="experienced", wants_affection=True, wants_fluffy=True,
    ),
    OwnerProfile(
        scenario_id="duplicate_soft_rows",
        label="Duplicate soft rows must not multiply one semantic penalty",
        activity_level="low", wants_size="medium",
    ),
    OwnerProfile(
        scenario_id="rule_order_invariant",
        label="Policy result and provenance are independent of row order",
        allergies="mild", young_children=True, wants_size="large",
        wants_affection=True, wants_fluffy=True,
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
