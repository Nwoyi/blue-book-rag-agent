"""Tests for _validate_analysis() and _get_age_category()."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag import _get_age_category, _validate_analysis


# --- Age Category Tests ---

def test_age_category_younger():
    assert _get_age_category(35) == "younger individual"
    assert _get_age_category(49) == "younger individual"


def test_age_category_closely_approaching():
    assert _get_age_category(50) == "closely approaching advanced age"
    assert _get_age_category(54) == "closely approaching advanced age"


def test_age_category_advanced():
    assert _get_age_category(55) == "advanced age"
    assert _get_age_category(59) == "advanced age"


def test_age_55_is_advanced_not_closely_approaching():
    """Critical test: 55 is 'advanced age', NOT 'closely approaching advanced age'."""
    cat = _get_age_category(55)
    assert cat == "advanced age"
    assert cat != "closely approaching advanced age"


def test_age_category_approaching_retirement():
    assert _get_age_category(60) == "closely approaching retirement age"
    assert _get_age_category(64) == "closely approaching retirement age"


def test_age_category_retirement():
    assert _get_age_category(65) == "retirement age"
    assert _get_age_category(70) == "retirement age"


# --- Validation: Missing Sections ---

def test_validation_catches_missing_sources():
    analysis = "## POTENTIALLY MATCHING LISTINGS\n## CRITERIA ANALYSIS\n## EVIDENCE GAPS\n## STRENGTH ASSESSMENT\n## STRATEGIC PATHWAY RANKING\n## RFC\n## STRENGTHS AND WEAKNESSES\n"
    warnings = _validate_analysis(analysis, "Age 55 patient with back pain")
    assert any("Sources" in w for w in warnings)


def test_validation_catches_missing_strategic_ranking():
    analysis = "## POTENTIALLY MATCHING LISTINGS\n## CRITERIA ANALYSIS\n## EVIDENCE GAPS\n## STRENGTH ASSESSMENT\n## RFC\n## STRENGTHS AND WEAKNESSES\n## SOURCES\n"
    warnings = _validate_analysis(analysis, "Age 55 patient with back pain")
    assert any("pathway ranking" in w.lower() for w in warnings)


# --- Validation: Age Error ---

def test_validation_catches_age_error_55():
    """If analysis says 'closely approaching advanced age' for a 55yo, flag it."""
    analysis = "The claimant is closely approaching advanced age.\n## SOURCES\n"
    warnings = _validate_analysis(analysis, "55-year-old male with back pain")
    assert any("AGE ERROR" in w for w in warnings)


def test_validation_no_age_error_when_correct():
    analysis = "The claimant is at advanced age.\n## POTENTIALLY MATCHING LISTINGS\n## CRITERIA ANALYSIS\n## EVIDENCE GAPS\n## STRENGTH ASSESSMENT\n## STRATEGIC PATHWAY RANKING\n## RFC\n## STRENGTHS AND WEAKNESSES\n## SOURCES\n"
    warnings = _validate_analysis(analysis, "55-year-old male with back pain")
    age_errors = [w for w in warnings if "AGE ERROR" in w]
    assert len(age_errors) == 0


# --- Validation: Hearing/Vision Contamination ---

def test_validation_catches_hearing_contamination():
    analysis = "Recommend audiometric testing and otoscopic examination.\n## SOURCES\n"
    findings = "62-year-old with diabetic retinopathy and visual acuity 20/200"
    warnings = _validate_analysis(analysis, findings)
    assert any("CONTAMINATION" in w for w in warnings)


def test_validation_no_contamination_when_clean():
    analysis = "Recommend ophthalmological exam and Goldmann perimetry.\n## POTENTIALLY MATCHING LISTINGS\n## CRITERIA ANALYSIS\n## EVIDENCE GAPS\n## STRENGTH ASSESSMENT\n## STRATEGIC PATHWAY RANKING\n## RFC\n## STRENGTHS AND WEAKNESSES\n## SOURCES\n"
    findings = "62-year-old with diabetic retinopathy and visual acuity 20/200"
    warnings = _validate_analysis(analysis, findings)
    contamination = [w for w in warnings if "CONTAMINATION" in w]
    assert len(contamination) == 0


# --- Validation: Calculation Gap ---

def test_validation_catches_calculation_gap():
    analysis = "Visual acuity efficiency cannot be calculated.\n## SOURCES\n"
    findings = "Patient with retinopathy and visual acuity 20/100"
    warnings = _validate_analysis(analysis, findings)
    assert any("CALCULATION" in w for w in warnings)


# --- Validation: Good Response Passes ---

def test_good_response_passes(mock_claude_good_response, sample_vision_findings):
    warnings = _validate_analysis(mock_claude_good_response, sample_vision_findings)
    # Should have no age errors, no contamination, no calculation gaps
    critical = [w for w in warnings if "AGE ERROR" in w or "CONTAMINATION" in w or "CALCULATION" in w]
    assert len(critical) == 0


def test_bad_response_catches_errors(mock_claude_bad_response, sample_vision_findings):
    warnings = _validate_analysis(mock_claude_bad_response, sample_vision_findings)
    # Should catch: missing sections, age error, hearing contamination, calculation gap
    assert len(warnings) >= 3, f"Expected >= 3 warnings, got {len(warnings)}: {warnings}"
