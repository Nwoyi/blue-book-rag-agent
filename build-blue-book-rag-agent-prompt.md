# PROMPT: Build the SSA Blue Book RAG Agent

## Give this prompt + the file `research/blue-book-knowledge-base-explained.md` to your coding AI agent (Claude Code, Cursor, etc.)

---

## THE PROMPT

You are helping me build an SSA Blue Book RAG Agent — a tool that SSDI disability lawyers can use to check whether a client's medical evidence matches SSA Blue Book disability listings.

## WHAT THIS SYSTEM DOES

A lawyer pastes in a client's medical findings (symptoms, diagnoses, test results, functional limitations). The system:

1. Searches the SSA Blue Book for relevant disability listings
2. Shows which listings might apply
3. For each listing, shows which criteria are MET (based on the evidence provided) and which are MISSING
4. Recommends what additional evidence the lawyer should obtain

This is a standalone web app. Not connected to any voice agent or CRM. Just a tool lawyers open in their browser, paste medical info, and get back a Blue Book analysis.

## TECH STACK (Use exactly these — no substitutions)

- **Python 3.12+**
- **FastAPI** — backend API
- **ChromaDB** — vector database (local, persistent storage)
- **sentence-transformers** — embeddings (model: `all-MiniLM-L6-v2`, runs locally, free)
- **Claude API via OpenRouter** — LLM for analysis (use `anthropic/claude-sonnet-4-20250514` model)
- **Requests + BeautifulSoup4** — for scraping the Blue Book
- **A simple frontend** — HTML/CSS/JS served by FastAPI. No React. Keep it simple. Clean, professional, dark theme. One page with a text input area and results display.

## STEP-BY-STEP BUILD ORDER

### Step 1: Scrape and Parse the SSA Blue Book

Scrape ALL 14 adult listing sections from the SSA Blue Book website. The URLs follow this pattern:
```
https://www.ssa.gov/disability/professionals/bluebook/1.00-Musculoskeletal-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/2.00-SpecialSensesandSpeech-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/3.00-Respiratory-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/4.00-Cardiovascular-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/5.00-Digestive-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/6.00-Genitourinary-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/7.00-Hematological-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/8.00-Skin-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/9.00-Endocrine-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/10.00-CongenitalDisordersAffecting-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/11.00-Neurological-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/12.00-MentalDisorders-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/13.00-Cancer-Adult.htm
https://www.ssa.gov/disability/professionals/bluebook/14.00-Immune-Adult.htm
```

If SSA blocks requests (returns 403), use these fallback approaches:
- Try the Code of Federal Regulations version: `https://www.ssa.gov/OP_Home/cfr20/404/404-app-p01.htm`
- Add a User-Agent header that mimics a browser
- If both fail, create a `/data` folder where I can manually save the HTML files, and parse from local files instead

For each section, parse the HTML and extract:
- **Section introductory text** (the X.00 general information about evaluating that body system)
- **Individual listings** (each numbered listing like 1.15, 1.16, etc.)

For each individual listing, extract and structure as JSON:
```json
{
  "listing_number": "1.15",
  "title": "Disorders of the skeletal spine resulting in compromise of a nerve root(s)",
  "body_system": "Musculoskeletal",
  "section_number": "1.00",
  "full_text": "the complete raw text of the listing",
  "criteria_summary": "brief plain-language summary of what's required"
}
```

Save the structured data as `data/blue_book_listings.json`.

Also create a `data/blue_book_sections.json` with the section-level introductory text (the general evaluation guidelines for each body system). These are important because they explain HOW to evaluate evidence for that body system.

### Step 2: Build the Vector Database

Using ChromaDB with persistent storage and sentence-transformers embeddings:

1. Create a persistent ChromaDB database at `./chroma_db/`
2. Create a collection called `blue_book`
3. For each listing from the JSON:
   - Create a document combining the listing title + full text + criteria summary
   - Also store the section introductory text as separate documents (tagged with metadata so we know they're section-level, not individual listings)
4. Embed all documents using `sentence-transformers/all-MiniLM-L6-v2`
5. Store metadata with each document: `listing_number`, `body_system`, `section_number`, `doc_type` (either "listing" or "section_intro")

Create a script `build_db.py` that:
- Loads the JSON data
- Builds/rebuilds the ChromaDB collection
- Can be re-run if the Blue Book is updated (deletes and recreates the collection)

### Step 3: Build the RAG Pipeline

Create a module `rag.py` that:

1. Takes user input (medical findings text)
2. Embeds the query using sentence-transformers
3. Searches ChromaDB for the top 10 most relevant documents
4. Constructs a prompt for Claude that includes:
   - The retrieved Blue Book listing texts (the actual criteria)
   - The relevant section introductory text (evaluation guidelines)
   - The user's medical findings
   - Clear instructions for what to analyze

The Claude prompt should instruct the LLM to:

```
You are an SSA Blue Book analysis assistant for disability attorneys. You help lawyers understand how a client's medical evidence maps to SSA disability listings.

IMPORTANT DISCLAIMERS:
- This is a research aid, not legal advice
- All analysis must be verified by the attorney
- This does not replace professional legal judgment

Given the Blue Book listings below and the client's medical findings, provide:

1. POTENTIALLY MATCHING LISTINGS
   For each listing that could potentially apply:
   - Listing number and title
   - Why it might apply based on the medical findings provided

2. CRITERIA ANALYSIS
   For each potentially matching listing, go through EACH criterion (A, B, C, D, etc.) and state:
   - ✅ MET — if the medical findings clearly support this criterion (cite the specific evidence)
   - ❓ UNCLEAR — if there's partial evidence but not enough to confirm
   - ❌ MISSING — if no evidence was provided for this criterion

3. EVIDENCE GAPS
   List specifically what additional medical evidence the attorney should obtain:
   - What type of evidence (imaging, lab work, specialist exam, etc.)
   - Why it's needed (which criterion it would satisfy)
   - What it should show to meet the listing requirement

4. STRENGTH ASSESSMENT
   Rate the overall strength of the case for each listing:
   - STRONG — most criteria clearly met
   - MODERATE — some criteria met, key evidence gaps are obtainable
   - WEAK — significant criteria missing, may need different approach

Be precise. Cite specific listing criteria by letter (A, B, C, D) and sub-criteria by number (1, 2, 3). Reference the specific medical findings the user provided when marking criteria as met.

Do NOT hallucinate criteria. Only reference criteria that appear in the Blue Book text provided to you. If you're unsure about a criterion, say so.
```

The Claude API call should go through OpenRouter:
- Base URL: `https://openrouter.ai/api/v1`
- Model: `anthropic/claude-sonnet-4-20250514`
- Use the `OPENROUTER_API_KEY` environment variable

### Step 4: Build the FastAPI Backend

Create `main.py` with these endpoints:

**POST /analyze**
- Request body: `{ "medical_findings": "string of medical findings text" }`
- Response: The Claude analysis result as structured JSON
- This is the main endpoint the frontend calls

**GET /listings**
- Returns all Blue Book listings (listing number, title, body system)
- For a reference sidebar or dropdown in the UI

**GET /listings/{listing_number}**
- Returns the full text of a specific listing
- So lawyers can read the actual criteria themselves

**GET /health**
- Basic health check endpoint

### Step 5: Build the Frontend

A single HTML page served by FastAPI at the root `/`. Keep it simple but professional:

**Layout:**
- Header: "Blue Book Analysis Tool" with a subtitle "SSDI Listing Matcher"
- Main area: Large text input area (textarea) with placeholder text like "Paste the client's medical findings, diagnoses, symptoms, test results, and functional limitations here..."
- A "Analyze" button
- Results area below that shows the analysis with clear sections, icons for ✅❓❌, and collapsible listing details
- A disclaimer footer: "This tool is a research aid for attorneys. It does not constitute legal advice. All analysis must be independently verified."

**Design:**
- Dark theme (dark background, light text)
- Clean, professional — this is for lawyers, not developers
- Monospace or clean sans-serif font
- Loading spinner while waiting for Claude's response
- Responsive (works on desktop and tablet)

**No framework needed.** Plain HTML + CSS + vanilla JavaScript. Serve static files from a `/static` folder via FastAPI.

### Step 6: Configuration and Environment

Create a `.env` file (with `.env.example` for the template):
```
OPENROUTER_API_KEY=your_key_here
CLAUDE_MODEL=anthropic/claude-sonnet-4-20250514
CHROMA_DB_PATH=./chroma_db
```

Create a `requirements.txt`:
```
fastapi
uvicorn
chromadb
sentence-transformers
requests
beautifulsoup4
python-dotenv
httpx
```

Create a `README.md` with:
1. What this project does (1-2 sentences)
2. Setup instructions (install requirements, set env vars, run build_db.py, run server)
3. Usage instructions

## PROJECT STRUCTURE

```
blue-book-rag/
├── main.py                  # FastAPI app
├── rag.py                   # RAG pipeline (embed query → search ChromaDB → call Claude)
├── scraper.py               # Scrape Blue Book from SSA website
├── build_db.py              # Build ChromaDB from scraped data
├── config.py                # Load env vars, constants
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── blue_book_listings.json    # Structured listing data
│   └── blue_book_sections.json    # Section introductory text
├── chroma_db/                     # ChromaDB persistent storage (gitignored)
└── static/
    ├── index.html            # Frontend
    ├── style.css             # Styling
    └── script.js             # Frontend logic
```

## IMPORTANT RULES

1. **Do NOT use LangChain.** Build the RAG pipeline manually. It's simpler for this use case — just embed the query, search ChromaDB, construct the prompt, call Claude via OpenRouter HTTP API. LangChain adds unnecessary complexity here.

2. **All Blue Book data must be loaded from local files**, not fetched from SSA on every request. The scraper runs once (or on-demand), saves to JSON, and the app reads from JSON/ChromaDB.

3. **Handle SSA scraping failures gracefully.** If the scraper can't access SSA (403 errors), it should print clear instructions for the user to manually download the HTML files and save them to a `data/raw_html/` folder, then parse from there.

4. **The ChromaDB collection should be rebuildable.** Running `build_db.py` should delete the old collection and create a fresh one from the JSON data.

5. **No authentication needed for MVP.** This runs locally. No login system.

6. **Error handling.** If Claude API fails, return a clear error message to the frontend. If ChromaDB returns no results, tell the user no matching listings were found.

7. **Keep the code clean and well-commented.** I'm learning — I need to understand what each part does.

8. **Test with this example query after building:**

```
Patient is a 52-year-old male with chronic low back pain for 3 years.
MRI of lumbar spine shows L4-L5 disc herniation with left L5 nerve root compression.
Physical exam: positive straight leg raise at 30 degrees on the left, decreased sensation in left L5 dermatome, 4/5 weakness in left ankle dorsiflexion.
Patient uses a cane for ambulation and reports inability to walk more than one block.
Patient also reports depression and anxiety secondary to chronic pain, currently seeing a psychiatrist monthly.
Medications: gabapentin 600mg TID, duloxetine 60mg daily, hydrocodone 10-325 PRN.
Patient has not worked since January 2024. Previously worked as a warehouse worker (heavy exertion) for 15 years.
```

This should match Listing 1.15 (spinal disorders) and potentially Listing 12.04 or 12.06 (mental disorders). The system should identify which criteria are met, which are missing, and what additional evidence to obtain.

## START BUILDING

Begin with the scraper (Step 1), then build the database (Step 2), then the RAG pipeline (Step 3), then the API (Step 4), then the frontend (Step 5). Test each step before moving to the next.
