"""
Evaluation tests — parametrized over medical scenarios.

Tests retrieval quality and anti-hallucination using real ChromaDB.
No API key needed (tests retrieval only, not Claude).
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from rag import search_blue_book


# Load eval cases
EVAL_DIR = os.path.dirname(__file__)
EVAL_CASES_PATH = os.path.join(EVAL_DIR, "eval_cases.json")

with open(EVAL_CASES_PATH, "r", encoding="utf-8") as f:
    EVAL_CASES = json.load(f)


@pytest.fixture(scope="module")
def valid_listing_numbers():
    """Load all valid listing numbers from the JSON dataset."""
    listings_path = os.path.join(EVAL_DIR, "..", "..", "data", "blue_book_listings.json")
    if not os.path.exists(listings_path):
        pytest.skip("blue_book_listings.json not found — run scraper.py first")
    with open(listings_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["listing_number"] for item in data}


def _get_retrieved_listing_numbers(medical_findings: str) -> set:
    """Run search and extract listing numbers from results."""
    results = search_blue_book(medical_findings)
    listing_nums = set()
    for r in results:
        ln = r["metadata"].get("listing_number", "")
        if ln and "." in ln:
            listing_nums.add(ln)
    return listing_nums


@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_expected_listings_retrieved(case):
    """Each expected listing should appear in retrieval results."""
    retrieved = _get_retrieved_listing_numbers(case["medical_findings"])
    for expected in case["expected_listings"]:
        assert expected in retrieved, (
            f"[{case['id']}] Expected listing {expected} not found in results. "
            f"Retrieved: {sorted(retrieved)}"
        )


@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_no_contamination_listings(case):
    """Unexpected listings should NOT appear in results."""
    if not case["unexpected_listings"]:
        pytest.skip("No unexpected listings defined for this case")
    retrieved = _get_retrieved_listing_numbers(case["medical_findings"])
    for unexpected in case["unexpected_listings"]:
        assert unexpected not in retrieved, (
            f"[{case['id']}] Unexpected listing {unexpected} found in results. "
            f"This indicates cross-contamination between conditions."
        )


@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_no_hallucinated_listings(case, valid_listing_numbers):
    """Every retrieved listing must exist in the actual Blue Book database."""
    retrieved = _get_retrieved_listing_numbers(case["medical_findings"])
    for ln in retrieved:
        assert ln in valid_listing_numbers, (
            f"[{case['id']}] Retrieved listing {ln} does NOT exist in blue_book_listings.json. "
            f"This is a hallucinated or invalid listing number."
        )


@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_retrieval_returns_results(case):
    """Every eval case should return at least some results."""
    results = search_blue_book(case["medical_findings"])
    assert len(results) > 0, f"[{case['id']}] No results returned for: {case['description']}"


@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_age_category_matches(case):
    """Verify the expected age category is correct per SSA rules."""
    from rag import _get_age_category
    import re

    age_match = re.search(r"(\d{2})-year-old", case["medical_findings"])
    if not age_match:
        pytest.skip("No age found in medical findings")
    age = int(age_match.group(1))
    actual = _get_age_category(age)
    assert actual == case["expected_age_category"], (
        f"[{case['id']}] Age {age}: expected '{case['expected_age_category']}', "
        f"got '{actual}'"
    )
