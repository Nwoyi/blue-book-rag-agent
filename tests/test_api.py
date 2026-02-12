"""Tests for FastAPI endpoints — no API key needed for most tests."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_listings_endpoint():
    response = client.get("/listings")
    assert response.status_code == 200
    listings = response.json()
    assert len(listings) >= 100, f"Expected >= 100 listings, got {len(listings)}"


def test_listings_have_required_fields():
    response = client.get("/listings")
    listings = response.json()
    if listings:
        first = listings[0]
        assert "listing_number" in first
        assert "title" in first
        assert "body_system" in first


def test_get_specific_listing():
    response = client.get("/listings/1.15")
    assert response.status_code == 200
    data = response.json()
    assert data["listing_number"] == "1.15"


def test_get_nonexistent_listing():
    response = client.get("/listings/99.99")
    assert response.status_code == 404


def test_analyze_empty_body():
    response = client.post("/analyze", json={"medical_findings": ""})
    assert response.status_code == 400


def test_analyze_too_short():
    response = client.post("/analyze", json={"medical_findings": "back pain"})
    assert response.status_code == 400


def test_analyze_missing_field():
    response = client.post("/analyze", json={})
    assert response.status_code == 422  # Pydantic validation error


def test_response_model_has_validation_warnings():
    """Verify the AnalyzeResponse model includes validation_warnings field."""
    from main import AnalyzeResponse

    fields = AnalyzeResponse.model_fields
    assert "validation_warnings" in fields
