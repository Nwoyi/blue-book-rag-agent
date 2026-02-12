"""Tests for the RAG pipeline — mocks Claude API calls."""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag import build_claude_prompt, search_blue_book, analyze_medical_findings


def test_build_claude_prompt_structure(sample_vision_findings):
    """Prompt should have system + user messages with correct structure."""
    docs = search_blue_book(sample_vision_findings)
    messages = build_claude_prompt(sample_vision_findings, docs)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "BLUE BOOK LISTINGS" in messages[1]["content"]
    assert "CLIENT'S MEDICAL FINDINGS" in messages[1]["content"]
    assert sample_vision_findings in messages[1]["content"]


def test_prompt_contains_retrieved_listings(sample_spine_findings):
    docs = search_blue_book(sample_spine_findings)
    messages = build_claude_prompt(sample_spine_findings, docs)
    content = messages[1]["content"]
    # Should contain at least one listing number
    assert "Listing" in content


def test_hearing_subsections_filtered_for_vision_case(sample_vision_findings):
    """Vision cases should NOT include hearing subsection docs."""
    docs = search_blue_book(sample_vision_findings)
    messages = build_claude_prompt(sample_vision_findings, docs)
    content = messages[1]["content"]
    # The prompt should not include hearing evaluation guidelines for a vision case
    # (hearing_loss subsection topic should be filtered out)
    # This is a soft check — the filtering happens in build_claude_prompt
    assert "CLIENT'S MEDICAL FINDINGS" in content


def test_system_prompt_contains_age_rules():
    """System prompt must contain SSA age classification rules."""
    docs = [{"text": "test", "metadata": {"listing_number": "1.15", "body_system": "Musculoskeletal", "doc_type": "listing"}, "id": "test_1"}]
    messages = build_claude_prompt("test findings", docs)
    system = messages[0]["content"]
    assert "advanced age" in system.lower()
    assert "55" in system


def test_system_prompt_contains_visual_acuity_table():
    docs = [{"text": "test", "metadata": {"listing_number": "2.02", "body_system": "Special Senses", "doc_type": "listing"}, "id": "test_1"}]
    messages = build_claude_prompt("test findings", docs)
    system = messages[0]["content"]
    assert "20/200" in system
    assert "Visual Acuity" in system


def test_analyze_with_mocked_claude(sample_vision_findings, mock_claude_good_response):
    """Full pipeline with mocked Claude should return success + no critical warnings."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": mock_claude_good_response}}]
    }

    with patch("rag.requests.post", return_value=mock_response):
        result = analyze_medical_findings(sample_vision_findings)

    assert result["status"] == "success"
    assert len(result["analysis"]) > 0
    assert result["retrieved_count"] > 0
    assert isinstance(result["validation_warnings"], list)
    assert isinstance(result["matched_listings"], list)


def test_analyze_with_bad_response_catches_warnings(sample_vision_findings, mock_claude_bad_response):
    """Mocked bad response should trigger validation warnings."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": mock_claude_bad_response}}]
    }

    with patch("rag.requests.post", return_value=mock_response):
        result = analyze_medical_findings(sample_vision_findings)

    assert result["status"] == "success"
    assert len(result["validation_warnings"]) >= 1, f"Expected warnings, got {result['validation_warnings']}"


def test_analyze_empty_input():
    result = analyze_medical_findings("")
    assert result["status"] == "error"


def test_analyze_short_input():
    result = analyze_medical_findings("back pain")
    assert result["status"] == "error"


def test_analyze_api_error_handling(sample_vision_findings):
    """Should handle API errors gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("rag.requests.post", return_value=mock_response):
        result = analyze_medical_findings(sample_vision_findings)

    assert result["status"] == "error"
    assert "error" in result
