"""
Shared fixtures for Blue Book RAG Agent tests.
"""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def chroma_collection():
    """Real ChromaDB collection (read-only). Skip if DB doesn't exist."""
    from rag import get_chroma_collection

    try:
        return get_chroma_collection()
    except Exception:
        pytest.skip("ChromaDB not available — run build_db.py first")


@pytest.fixture(scope="session")
def listings_data():
    """Load all listings from JSON."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "blue_book_listings.json")
    if not os.path.exists(path):
        pytest.skip("blue_book_listings.json not found — run scraper.py first")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def valid_listing_numbers(listings_data):
    """Set of all valid listing numbers in the database."""
    return {listing["listing_number"] for listing in listings_data}


@pytest.fixture
def test_client():
    """FastAPI test client."""
    from main import app

    return TestClient(app)


@pytest.fixture
def sample_vision_findings():
    return (
        "62-year-old female, former secretary. Diagnosed with diabetic retinopathy "
        "bilateral. Best corrected visual acuity: 20/200 OD, 20/100 OS. "
        "Peripheral visual field loss documented on Goldmann perimetry. "
        "Diabetes mellitus type 2, A1c 8.5%. No hearing complaints."
    )


@pytest.fixture
def sample_spine_findings():
    return (
        "55-year-old male, former construction worker. MRI shows L4-L5 disc "
        "herniation with nerve root compression. Positive straight leg raise "
        "bilaterally. Uses a walker for ambulation. Chronic lower back pain "
        "with radiculopathy bilateral lower extremities."
    )


@pytest.fixture
def sample_cardiac_findings():
    return (
        "52-year-old male, former warehouse worker. Diagnosed with congestive "
        "heart failure NYHA Class III. Ejection fraction 30%. On maximum medical "
        "therapy including ACE inhibitor, beta blocker, diuretic. Experiences "
        "dyspnea on minimal exertion."
    )


@pytest.fixture
def mock_claude_good_response():
    """A well-formed Claude response with all required sections."""
    return """## 1. POTENTIALLY MATCHING LISTINGS

**Listing 2.02 — Loss of Central Visual Acuity**
This listing applies because the patient has documented visual acuity loss in both eyes.

**Listing 2.04 — Loss of Visual Efficiency**
Applicable due to combined central acuity and field loss.

## 2. CRITERIA ANALYSIS

**Listing 2.02:**
- Criterion A: Remaining vision in the better eye after best correction of 20/200 or less
  - Right eye (OD): 20/200 — this is at the statutory blindness threshold
  - Left eye (OS): 20/100 — visual acuity efficiency = 50% per Table 1

**Listing 2.04A (Visual Efficiency):**
- Visual acuity efficiency OS: 20/100 = 50%
- Visual field efficiency: requires Goldmann perimetry data
- Formula: (2 x 50% + field%) / 3 — must be <=20%

## 3. EVIDENCE GAPS

- Obtain formal Goldmann visual field testing results with degree measurements
- Request ophthalmological exam confirming best corrected acuity
- Document visual acuity efficiency calculations per Table 1

## 4. STRENGTH ASSESSMENT

- **Listing 2.02**: STRONG — 20/200 OD meets statutory blindness threshold
- **Listing 2.04A**: MODERATE — need field data to complete calculation

## 5. STRATEGIC PATHWAY RANKING

1. **Listing 2.02** (best pathway) — OD acuity at 20/200 meets threshold directly
2. **Listing 2.04A** — promising but requires field loss data to calculate

## 6. RESIDUAL FUNCTIONAL CAPACITY (RFC) CONSIDERATIONS

The claimant's visual limitations would restrict:
- Cannot perform work requiring fine visual acuity (reading, computer work)
- Cannot drive commercial vehicles
- At advanced age (62 = closely approaching retirement age), limited transferable skills

## 7. CASE STRENGTHS AND WEAKNESSES

**Strengths:**
- Age 62 = closely approaching retirement age (favorable under Grid Rules)
- 20/200 OD meets statutory blindness in one eye
- A1c 8.5% shows ongoing diabetic complications

**Weaknesses:**
- A1c 8.5% could suggest non-compliance with treatment
- Need complete visual field testing

## 8. SOURCES

- Listing 2.02 — Loss of Central Visual Acuity — https://www.ssa.gov/disability/professionals/bluebook/2.00-SpecialSensesandSpeech-Adult.htm
- Listing 2.04 — Loss of Visual Efficiency — https://www.ssa.gov/disability/professionals/bluebook/2.00-SpecialSensesandSpeech-Adult.htm
"""


@pytest.fixture
def mock_claude_bad_response():
    """A flawed Claude response — wrong age, hearing contamination, missing sections."""
    return """## 1. POTENTIALLY MATCHING LISTINGS

**Listing 2.02 — Loss of Central Visual Acuity**

## 2. CRITERIA ANALYSIS

Right eye 20/200, left eye 20/100. Visual acuity cannot be calculated without additional data.

## 3. EVIDENCE GAPS

- Obtain audiometric testing to rule out hearing involvement
- Schedule otoscopic examination
- Request ophthalmological exam

## 4. STRENGTH ASSESSMENT

- Listing 2.02: MODERATE

The claimant at age 62 is closely approaching advanced age.
"""
