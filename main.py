"""
FastAPI backend for the Blue Book RAG Agent.

Serves the frontend and provides API endpoints for
medical findings analysis and Blue Book listing lookup.

Usage:
    python main.py
    # Then open http://localhost:8000 in your browser
"""

import asyncio
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import LISTINGS_JSON
from rag import analyze_medical_findings

app = FastAPI(title="Blue Book RAG Agent", version="1.0.0")

# --- Cache listings in memory at startup ---
_listings_cache: list[dict] | None = None


def _load_listings() -> list[dict]:
    """Load listings from JSON file, with caching."""
    global _listings_cache
    if _listings_cache is None:
        if not os.path.exists(LISTINGS_JSON):
            return []
        with open(LISTINGS_JSON, "r", encoding="utf-8") as f:
            _listings_cache = json.load(f)
    return _listings_cache


# --- Request/Response Models ---


class AnalyzeRequest(BaseModel):
    medical_findings: str


class AnalyzeResponse(BaseModel):
    status: str
    analysis: str
    matched_listings: list[str]
    retrieved_count: int
    sources: dict = {}
    validation_warnings: list[str] = []
    disclaimer: str
    error: str | None = None


# --- API Endpoints ---


@app.get("/")
async def serve_frontend():
    """Serve the main frontend page."""
    return FileResponse("static/index.html")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Main analysis endpoint.
    Takes medical findings text and returns Blue Book analysis from Claude.
    """
    if not request.medical_findings.strip():
        raise HTTPException(status_code=400, detail="Medical findings text cannot be empty.")

    if len(request.medical_findings.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Please provide more detailed medical findings (at least a few sentences).",
        )

    try:
        # Run the sync RAG pipeline in a thread to avoid blocking FastAPI
        result = await asyncio.to_thread(
            analyze_medical_findings, request.medical_findings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "An unknown error occurred."),
        )

    return AnalyzeResponse(**result)


@app.get("/listings")
async def get_listings():
    """Return all Blue Book listings (number, title, body system) for reference."""
    listings = _load_listings()
    return [
        {
            "listing_number": l["listing_number"],
            "title": l["title"],
            "body_system": l["body_system"],
        }
        for l in listings
    ]


@app.get("/listings/{listing_number}")
async def get_listing(listing_number: str):
    """Return the full text of a specific Blue Book listing."""
    listings = _load_listings()
    for l in listings:
        if l["listing_number"] == listing_number:
            return l
    raise HTTPException(status_code=404, detail=f"Listing {listing_number} not found.")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


# Mount static files AFTER route definitions
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    # Set reload to False for production to save memory
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
