# Phase 1: Blue Book Knowledge Base — Explained From Scratch

## Written for Philip. No assumptions. Start from zero.

---

## WHAT IS THE BLUE BOOK?

The Blue Book is just a big document on the SSA website. It lists every medical condition they consider a disability, and for EACH condition, it tells you: "if the person has THIS specific evidence, they qualify."

It lives here: https://www.ssa.gov/disability/professionals/bluebook/

There are 14 sections (body systems), each with multiple "listings" (specific conditions).

Example — **Listing 1.15** (back problems causing nerve issues):

```
To qualify, you need ALL of these at the same time (within 4 months):

A. Nerve-related symptoms — pain, tingling, numbness, or muscle weakness
   that follows the pattern of the specific nerve root affected

B. Neurological signs — a doctor documented specific findings during
   a physical exam OR on a diagnostic test

C. Imaging — MRI or similar showing the nerve is actually being
   compressed in the spine

D. Functional limitation — this has lasted (or will last) at least
   12 months AND causes at least ONE of these:
   - Can't walk effectively without a cane/walker
   - Can't use both arms to reach, push, pull, etc.
   - Can't sit/stand/walk for reasonable periods
```

Right now, lawyers read through 500+ pages of medical records by hand, then check the Blue Book by hand, and try to figure out: "does my client's evidence check all these boxes?"

**That's what we're automating.**

---

## WHAT IS "SCRAPING"?

Scraping = writing code that automatically visits a website and downloads the text.

Instead of you going to ssa.gov, reading each page, and copy-pasting — a Python script does it.

### What it looks like in Python:

```python
# This is a real, working scraper concept for the Blue Book

import requests
from bs4 import BeautifulSoup

# The Blue Book has 14 sections, each is a web page
BLUE_BOOK_URLS = [
    "https://www.ssa.gov/disability/professionals/bluebook/1.00-Musculoskeletal-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/2.00-SpecialSensesandSpeech-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/3.00-Respiratory-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/4.00-Cardiovascular-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/5.00-Digestive-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/6.00-Genitourinary-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/7.00-Hematological-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/8.00-Skin-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/9.00-Endocrine-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/10.00-CongenitalDisordersAffecting-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/11.00-Neurological-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/12.00-MentalDisorders-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/13.00-Cancer-Adult.htm",
    "https://www.ssa.gov/disability/professionals/bluebook/14.00-Immune-Adult.htm",
]

def scrape_blue_book():
    """Download all Blue Book pages and save the text."""
    all_sections = []

    for url in BLUE_BOOK_URLS:
        # Step 1: Download the web page
        response = requests.get(url)

        # Step 2: Parse the HTML (turn messy HTML into readable text)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Step 3: Extract the main content (ignore navigation, headers, footers)
        content = soup.find('div', class_='field-items')  # or whatever the main content div is

        # Step 4: Get the clean text
        text = content.get_text(separator='\n', strip=True)

        all_sections.append({
            'url': url,
            'text': text
        })

    return all_sections

# That's it. You now have all 14 sections as text.
# Next step: parse each section into structured listings.
```

### What you need to install:

```bash
pip install requests beautifulsoup4
```

That's 2 libraries. `requests` downloads web pages. `beautifulsoup4` reads the HTML and extracts the text.

**NOTE:** SSA might block automated requests (I got 403 errors when trying). If that happens, you have options:
- Download the pages manually once (just save each page as HTML)
- Use the Code of Federal Regulations version instead (same content, different URL): https://www.ssa.gov/OP_Home/cfr20/404/404-app-p01.htm
- Use a headless browser (Playwright/Selenium) that looks like a real person browsing

---

## WHAT IS "STRUCTURING" THE DATA?

Right now the Blue Book is just paragraphs of text. A human can read it, but a computer can't easily work with it.

"Structuring" means taking this:

```
"1.15 Disorders of the skeletal spine resulting in compromise of a nerve
root(s). With A through D: A. Neuro-anatomic distribution of one or more
of the following symptoms: 1. Pain; or 2. Paresthesia; or 3. Muscle fatigue..."
```

And turning it into this:

```python
{
    "listing_number": "1.15",
    "title": "Disorders of the skeletal spine resulting in compromise of a nerve root(s)",
    "body_system": "Musculoskeletal",
    "logic": "ALL of A through D required",
    "criteria": [
        {
            "id": "A",
            "description": "Neuro-anatomic distribution of symptoms",
            "logic": "ONE OR MORE of the following",
            "sub_criteria": [
                {"id": "A1", "text": "Pain"},
                {"id": "A2", "text": "Paresthesia"},
                {"id": "A3", "text": "Muscle fatigue"}
            ]
        },
        {
            "id": "B",
            "description": "Radicular distribution of neurological signs",
            "logic": "Present during exam OR on diagnostic test",
            "evidence_needed": "Physical examination findings or diagnostic test results"
        },
        {
            "id": "C",
            "description": "Imaging consistent with nerve root compromise",
            "evidence_needed": "MRI, CT, or other imaging of cervical or lumbosacral spine"
        },
        {
            "id": "D",
            "description": "Physical limitation lasting 12+ months",
            "logic": "AT LEAST ONE of the following",
            "sub_criteria": [
                {"id": "D1", "text": "Inability to ambulate effectively"},
                {"id": "D2", "text": "Inability to perform fine and gross motor movements"},
                {"id": "D3", "text": "Inability to stand/walk/sit for reasonable periods"}
            ]
        }
    ],
    "duration_requirement": "12 months continuous",
    "timing_requirement": "All criteria within 4-month window"
}
```

**See the difference?** Now a computer can:
- Search: "find all listings that require imaging evidence"
- Match: "my client has back pain + MRI showing compression + can't walk → check listing 1.15"
- Gap analysis: "my client has A, B, C but is missing D → tell the lawyer what's needed"

### How to do the structuring:

You have TWO options:

**Option A: Manual + LLM (Faster to start, good enough)**
1. Download all 14 Blue Book pages as text
2. Feed each one to Claude/GPT with a prompt like:

```
Here is the text of SSA Blue Book Section 1.00 (Musculoskeletal Disorders).

For EACH listing (1.15, 1.16, 1.17, 1.18, 1.20, 1.21, 1.22, 1.23):
Extract and structure it as JSON with these fields:
- listing_number
- title
- body_system
- logic (are all criteria required? or just some?)
- criteria (each criterion with its sub-criteria)
- duration_requirement
- timing_requirement
- evidence_types_needed (what kinds of medical evidence: imaging, lab, exam, etc.)

Output valid JSON.
```

3. Save the JSON. That's your knowledge base.

**Option B: Automated parsing (More work upfront, more maintainable)**
1. Write a Python script that parses the HTML structure
2. Use regex patterns to identify listing numbers, criteria letters (A, B, C, D), sub-items (1, 2, 3)
3. Build the JSON automatically
4. Advantage: when SSA updates the Blue Book, you just re-run the script

---

## WHAT ARE "VECTOR EMBEDDINGS"?

Okay this is where it gets a little more technical, but I'll keep it simple.

### The Problem:
You have a structured Blue Book knowledge base. A client's medical records say something like: "Patient presents with chronic low back pain radiating to the left leg, positive straight leg raise test, MRI shows L4-L5 disc herniation compressing the left L5 nerve root."

How does the computer know that this text matches Listing 1.15?

The words are different. The medical records don't say "Listing 1.15." They describe symptoms in medical language.

### The Solution: Embeddings

An "embedding" is when you convert text into a list of numbers that capture its MEANING, not just its words.

```
"chronic low back pain radiating to left leg"
    → [0.23, -0.45, 0.87, 0.12, -0.33, 0.56, ...]  (hundreds of numbers)

"Neuro-anatomic distribution of pain"
    → [0.21, -0.43, 0.85, 0.14, -0.31, 0.54, ...]  (similar numbers!)
```

Because these two phrases MEAN similar things, their number lists are similar. The computer can measure the distance between them and say "these are related."

### How it works in practice:

```python
# Step 1: Install what you need
# pip install chromadb openai  (or use any embedding provider)

import chromadb
from openai import OpenAI

client = OpenAI()  # uses your API key
chroma = chromadb.Client()

# Step 2: Create a "collection" (like a smart folder)
collection = chroma.create_collection("blue_book")

# Step 3: Add all your Blue Book listings to the collection
# Each listing gets converted to numbers (embeddings) automatically

listings = [
    {
        "id": "1.15",
        "text": "Disorders of the skeletal spine resulting in compromise of a nerve root. Requires neuro-anatomic distribution of pain, paresthesia, or muscle fatigue. Plus neurological signs. Plus imaging showing nerve root compromise. Plus functional limitation lasting 12+ months.",
    },
    {
        "id": "1.16",
        "text": "Lumbar spinal stenosis resulting in compromise of the cauda equina...",
    },
    # ... all other listings
]

for listing in listings:
    collection.add(
        documents=[listing["text"]],
        ids=[listing["id"]]
    )

# Step 4: Now you can SEARCH by meaning, not just keywords

results = collection.query(
    query_texts=["patient has chronic back pain radiating to left leg with MRI showing disc herniation at L4-L5"],
    n_results=3  # get top 3 matches
)

print(results)
# Returns: Listing 1.15, 1.16, 1.17 (the most relevant back-related listings)
```

**That's it.** You put the Blue Book in, and now you can search it by describing a medical condition in plain language, and it finds the matching listings.

### Alternative: Use Pinecone instead of ChromaDB

ChromaDB runs on your computer (local). Pinecone runs in the cloud (easier to scale, costs money).

```python
# ChromaDB = free, runs locally, good for development
# Pinecone = cloud-hosted, $0-70/month, better for production
# Both work the same way conceptually
```

---

## WHAT IS "RAG"?

RAG = **Retrieval Augmented Generation**

Fancy name. Simple concept.

Instead of asking an LLM a question and hoping it knows the answer from training:

```
❌ BAD: "Hey Claude, does this patient meet Listing 1.15?"
   (Claude might hallucinate or use outdated info)
```

You FIRST search your knowledge base for relevant info, THEN give it to the LLM along with the question:

```
✅ GOOD:
   1. Search Blue Book embeddings → find Listing 1.15 criteria
   2. Send to Claude: "Here are the EXACT criteria for Listing 1.15: [paste them].
      Here are the patient's medical findings: [paste them].
      Does the patient meet each criterion? Which ones are missing?"
   (Claude now has the real criteria and can give an accurate answer)
```

### RAG in code:

```python
from langchain.chat_models import ChatAnthropic
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA

# Step 1: Set up the vector store with Blue Book data
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(
    collection_name="blue_book",
    embedding_function=embeddings,
    persist_directory="./blue_book_db"
)

# Step 2: Set up the LLM
llm = ChatAnthropic(model="claude-sonnet-4-20250514")

# Step 3: Create the RAG chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",  # "stuff" = put all retrieved docs into one prompt
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),  # get top 5 matches
)

# Step 4: Ask a question
answer = qa_chain.run(
    """
    Patient medical findings:
    - Chronic low back pain radiating to left leg for 18 months
    - MRI shows L4-L5 disc herniation with left L5 nerve root compression
    - Positive straight leg raise test at 30 degrees
    - Decreased sensation in left L5 dermatome
    - Uses a cane for ambulation

    Which Blue Book listings might this patient meet?
    For each listing, which criteria are met and which are missing?
    """
)

print(answer)
# Claude now answers with REAL Blue Book criteria, not hallucinated ones,
# because it was given the actual listing text from our knowledge base
```

---

## THE COMPLETE PICTURE

Here's what Phase 1 looks like end to end:

```
STEP 1: SCRAPE
    Download Blue Book from ssa.gov
    ↓
    Tools: requests + beautifulsoup4
    Time: 1-2 hours

STEP 2: STRUCTURE
    Parse the raw text into JSON objects
    Each listing = one object with criteria, sub-criteria, evidence requirements
    ↓
    Tools: Python + Claude/GPT to help parse
    Time: 4-8 hours (14 sections to process)

STEP 3: EMBED
    Convert each listing into vector embeddings
    Store in ChromaDB (local) or Pinecone (cloud)
    ↓
    Tools: chromadb + openai (for embeddings)
    Time: 1-2 hours

STEP 4: RAG PIPELINE
    Build the search + LLM chain
    Input: patient's medical findings (text)
    Output: matching listings + gap analysis
    ↓
    Tools: langchain + claude API
    Time: 2-4 hours

TOTAL: ~1-2 days of focused work to build Phase 1
```

After this, you have a system where you can paste in medical findings and it tells you:
- Which Blue Book listings the patient might qualify for
- Which criteria are already met (with evidence)
- Which criteria are MISSING (so the lawyer knows what records to get)

**That's the foundation. Everything else builds on top of this.**

---

## WHAT YOU NEED TO KNOW / INSTALL

### Python Libraries
```bash
pip install requests           # Download web pages
pip install beautifulsoup4     # Parse HTML
pip install chromadb           # Vector database (local, free)
pip install openai             # Embeddings + LLM calls
pip install langchain          # Orchestration framework
pip install langchain-anthropic  # Claude integration
pip install langchain-community  # Community integrations
```

### API Keys Needed
- **OpenAI API key** — for embeddings ($0.0001 per 1K tokens, basically free)
- **Anthropic API key** — for Claude (your LLM for analysis)
- OR use **one provider for both** (Claude can do embeddings too via Voyage AI, or you can use open-source embeddings with `sentence-transformers`)

### Free/Cheap Option (No API costs for embeddings)
```bash
pip install sentence-transformers  # Free, local embeddings
```

```python
from sentence_transformers import SentenceTransformer

# This runs locally on your machine — no API calls, no cost
model = SentenceTransformer('all-MiniLM-L6-v2')

embedding = model.encode("Disorders of the skeletal spine")
# Returns a list of 384 numbers — your embedding
```

---

## WHAT THIS DOES NOT DO (Important)

This system does NOT:
- Replace a lawyer's judgment
- Make final decisions about disability claims
- Process actual medical records (that's Phase 2 — needs OCR)
- Handle HIPAA compliance (that's a separate concern when real patient data is involved)

This system DOES:
- Give lawyers a fast way to check which listings might apply
- Identify evidence gaps so they know what records to request
- Save hours of manual Blue Book cross-referencing
- Provide a foundation for more advanced agents later

---

## SOURCES

- SSA Blue Book: https://www.ssa.gov/disability/professionals/bluebook/
- SSA Adult Listings: https://www.ssa.gov/disability/professionals/bluebook/AdultListings.htm
- Listing 1.15 details: https://disabilitydenials.com/social-security-administration-list-of-impairments/1-15/
- Blue Book usage guide: https://www.startdisability.com/how-to-file-ssdi-on-own-learn/bluebook-start
- ChromaDB docs: https://docs.trychroma.com/
- LangChain RAG docs: https://python.langchain.com/docs/tutorials/rag/
- Sentence Transformers: https://www.sbert.net/
