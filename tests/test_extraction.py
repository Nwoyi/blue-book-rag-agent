"""Tests for _extract_condition_queries() — keyword-to-query mapping."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag import _extract_condition_queries


def test_vision_keywords_trigger_vision_query():
    queries = _extract_condition_queries("Patient has diabetic retinopathy with visual acuity loss")
    assert any("visual" in q.lower() for q in queries)


def test_hearing_keywords_trigger_hearing_query():
    queries = _extract_condition_queries("Bilateral sensorineural hearing loss")
    assert any("hearing" in q.lower() for q in queries)


def test_diabetes_triggers_endocrine_query():
    queries = _extract_condition_queries("Type 2 diabetes mellitus with A1c 9.2%")
    assert any("endocrine" in q.lower() or "diabetes" in q.lower() for q in queries)


def test_neuropathy_triggers_neuropathy_query():
    queries = _extract_condition_queries("Peripheral neuropathy bilateral lower extremities")
    assert any("neuropathy" in q.lower() or "motor function" in q.lower() for q in queries)


def test_kidney_triggers_renal_query():
    queries = _extract_condition_queries("CKD Stage 4 with eGFR 22, on dialysis")
    assert any("kidney" in q.lower() or "renal" in q.lower() for q in queries)


def test_spine_triggers_spine_query():
    queries = _extract_condition_queries("Lumbar disc herniation L4-L5 with radiculopathy")
    assert any("spine" in q.lower() or "nerve root" in q.lower() for q in queries)


def test_cancer_triggers_cancer_query():
    queries = _extract_condition_queries("Non-Hodgkin lymphoma undergoing chemotherapy")
    assert any("neoplastic" in q.lower() or "cancer" in q.lower() for q in queries)


def test_mental_triggers_mental_query():
    queries = _extract_condition_queries("Major depressive disorder with anxiety")
    assert any("mental" in q.lower() or "depressive" in q.lower() for q in queries)


def test_multiple_conditions_produce_multiple_queries():
    text = "Diabetes with retinopathy and peripheral neuropathy and depression"
    queries = _extract_condition_queries(text)
    assert len(queries) >= 3, f"Expected >= 3 queries, got {len(queries)}: {queries}"


def test_no_matches_returns_empty():
    queries = _extract_condition_queries("The weather is nice today")
    assert queries == []


def test_case_insensitive():
    queries = _extract_condition_queries("DIABETES MELLITUS WITH RETINOPATHY")
    assert len(queries) >= 2
