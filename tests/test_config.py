"""Tests for config.py — verify all 14 sections and constants are correct."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    BLUE_BOOK_URLS,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
    SECTION_MAP,
    SECTION_URL_MAP,
    get_openrouter_headers,
)


def test_section_map_has_14_sections():
    assert len(SECTION_MAP) == 14


def test_blue_book_urls_has_14_entries():
    assert len(BLUE_BOOK_URLS) == 14


def test_section_url_map_has_14_entries():
    assert len(SECTION_URL_MAP) == 14


def test_all_sections_present():
    expected = {"1.00", "2.00", "3.00", "4.00", "5.00", "6.00", "7.00",
                "8.00", "9.00", "10.00", "11.00", "12.00", "13.00", "14.00"}
    assert set(SECTION_MAP.keys()) == expected


def test_section_url_map_matches_section_map():
    for section_num in SECTION_MAP:
        assert section_num in SECTION_URL_MAP, f"Missing URL for section {section_num}"


def test_all_urls_are_ssa_gov():
    for _, url in BLUE_BOOK_URLS:
        assert "ssa.gov" in url, f"URL not on ssa.gov: {url}"


def test_embedding_model_constant():
    assert EMBEDDING_MODEL == "all-MiniLM-L6-v2"


def test_chroma_collection_name():
    assert CHROMA_COLLECTION_NAME == "blue_book"


def test_openrouter_headers_raises_without_key():
    original = os.environ.get("OPENROUTER_API_KEY")
    try:
        os.environ["OPENROUTER_API_KEY"] = ""
        # Reload config to pick up empty key
        import importlib
        import config
        importlib.reload(config)
        try:
            config.get_openrouter_headers()
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
    finally:
        if original:
            os.environ["OPENROUTER_API_KEY"] = original
            import importlib
            import config
            importlib.reload(config)
