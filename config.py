"""
Configuration and constants for the Blue Book RAG Agent.
Loads environment variables and defines all shared settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- OpenRouter / Claude Settings ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- ChromaDB Settings ---
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME = "blue_book"

# --- Embedding Model ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- RAG Settings ---
TOP_K = 10  # Number of documents to retrieve per query

# --- Data Paths ---
DATA_DIR = "data"
LISTINGS_JSON = os.path.join(DATA_DIR, "blue_book_listings.json")
SECTIONS_JSON = os.path.join(DATA_DIR, "blue_book_sections.json")
RAW_HTML_DIR = os.path.join(DATA_DIR, "raw_html")

# --- Section metadata: maps section number to body system name ---
SECTION_MAP = {
    "1.00": "Musculoskeletal",
    "2.00": "Special Senses and Speech",
    "3.00": "Respiratory",
    "4.00": "Cardiovascular",
    "5.00": "Digestive",
    "6.00": "Genitourinary",
    "7.00": "Hematological",
    "8.00": "Skin",
    "9.00": "Endocrine",
    "10.00": "Congenital Disorders",
    "11.00": "Neurological",
    "12.00": "Mental Disorders",
    "13.00": "Cancer (Neoplastic Diseases)",
    "14.00": "Immune System",
}

# --- Blue Book URLs (all 14 adult listing sections) ---
BLUE_BOOK_URLS = [
    ("1.00", "https://www.ssa.gov/disability/professionals/bluebook/1.00-Musculoskeletal-Adult.htm"),
    ("2.00", "https://www.ssa.gov/disability/professionals/bluebook/2.00-SpecialSensesandSpeech-Adult.htm"),
    ("3.00", "https://www.ssa.gov/disability/professionals/bluebook/3.00-Respiratory-Adult.htm"),
    ("4.00", "https://www.ssa.gov/disability/professionals/bluebook/4.00-Cardiovascular-Adult.htm"),
    ("5.00", "https://www.ssa.gov/disability/professionals/bluebook/5.00-Digestive-Adult.htm"),
    ("6.00", "https://www.ssa.gov/disability/professionals/bluebook/6.00-Genitourinary-Adult.htm"),
    ("7.00", "https://www.ssa.gov/disability/professionals/bluebook/7.00-HematologicalDisorders-Adult.htm"),
    ("8.00", "https://www.ssa.gov/disability/professionals/bluebook/8.00-Skin-Adult.htm"),
    ("9.00", "https://www.ssa.gov/disability/professionals/bluebook/9.00-Endocrine-Adult.htm"),
    ("10.00", "https://www.ssa.gov/disability/professionals/bluebook/10.00-MultipleBody-Adult.htm"),
    ("11.00", "https://www.ssa.gov/disability/professionals/bluebook/11.00-Neurological-Adult.htm"),
    ("12.00", "https://www.ssa.gov/disability/professionals/bluebook/12.00-MentalDisorders-Adult.htm"),
    ("13.00", "https://www.ssa.gov/disability/professionals/bluebook/13.00-NeoplasticDiseases-Malignant-Adult.htm"),
    ("14.00", "https://www.ssa.gov/disability/professionals/bluebook/14.00-Immune-Adult.htm"),
]

# --- Section URL map (for source links in analysis results) ---
SECTION_URL_MAP = {sec_num: url for sec_num, url in BLUE_BOOK_URLS}

# --- CFR Fallback URL ---
CFR_FALLBACK_URL = "https://www.ssa.gov/OP_Home/cfr20/404/404-app-p01.htm"

# --- Request Headers (mimics a browser to avoid 403) ---
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def get_openrouter_headers() -> dict:
    """Return headers for OpenRouter API calls."""
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file: OPENROUTER_API_KEY=your_key_here"
        )
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Blue Book RAG Agent",
    }
