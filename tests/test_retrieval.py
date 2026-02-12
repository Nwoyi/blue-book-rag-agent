"""Tests for ChromaDB retrieval — uses real database (read-only)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rag import search_blue_book, get_chroma_collection


@pytest.fixture(scope="module")
def collection():
    try:
        return get_chroma_collection()
    except Exception:
        pytest.skip("ChromaDB not available — run build_db.py first")


def test_collection_has_enough_docs(collection):
    count = collection.count()
    assert count >= 140, f"Expected >= 140 docs, got {count}"


def test_spine_query_returns_section_1(collection):
    results = collection.query(
        query_texts=["lumbar disc herniation nerve root compression"],
        n_results=5,
        include=["metadatas"],
    )
    listing_nums = [m.get("listing_number", "") for m in results["metadatas"][0]]
    assert any(ln.startswith("1.") for ln in listing_nums), f"No section 1 listings: {listing_nums}"


def test_vision_query_returns_vision_listings(collection):
    results = collection.query(
        query_texts=["visual acuity loss diabetic retinopathy"],
        n_results=10,
        include=["metadatas"],
    )
    listing_nums = [m.get("listing_number", "") for m in results["metadatas"][0]]
    vision_listings = {"2.02", "2.03", "2.04"}
    found = vision_listings & set(listing_nums)
    assert len(found) >= 2, f"Expected vision listings, got {listing_nums}"


def test_hearing_query_returns_hearing_listings(collection):
    results = collection.query(
        query_texts=["hearing loss audiometric cochlear"],
        n_results=10,
        include=["metadatas"],
    )
    listing_nums = [m.get("listing_number", "") for m in results["metadatas"][0]]
    hearing_listings = {"2.10", "2.11"}
    found = hearing_listings & set(listing_nums)
    assert len(found) >= 1, f"Expected hearing listings, got {listing_nums}"


def test_search_blue_book_deduplicates():
    """Multi-query search should not return duplicate doc IDs."""
    results = search_blue_book("Diabetes with retinopathy and peripheral neuropathy")
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


def test_search_blue_book_returns_results():
    results = search_blue_book("Congestive heart failure ejection fraction 30%")
    assert len(results) > 0


def test_all_results_have_metadata():
    results = search_blue_book("COPD chronic pulmonary disease")
    for r in results:
        assert "metadata" in r
        assert "text" in r
        assert "id" in r


def test_distance_threshold():
    """All results should be within the MAX_DISTANCE threshold."""
    results = search_blue_book("Lumbar disc herniation with radiculopathy")
    for r in results:
        assert r["distance"] <= 1.2, f"Result {r['id']} has distance {r['distance']} > 1.2"


def test_multi_condition_finds_all_systems():
    """Multi-query should find listings from multiple body systems."""
    results = search_blue_book(
        "Diabetes with retinopathy, peripheral neuropathy, and chronic kidney disease stage 4"
    )
    sections_found = set()
    for r in results:
        ln = r["metadata"].get("listing_number", "")
        if "." in ln:
            sections_found.add(ln.split(".")[0])
    assert len(sections_found) >= 2, f"Expected >= 2 sections, got {sections_found}"
