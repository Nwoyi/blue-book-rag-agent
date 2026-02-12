"""
RAG Pipeline for Blue Book analysis.

Takes medical findings text, searches ChromaDB for relevant Blue Book listings,
constructs a prompt, and calls Claude via OpenRouter for analysis.

No LangChain — built manually for simplicity.
"""

import re

import chromadb
import requests
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    CLAUDE_MODEL,
    EMBEDDING_MODEL,
    OPENROUTER_BASE_URL,
    TOP_K,
    get_openrouter_headers,
)

# System prompt for Claude — defines how to analyze medical findings
SYSTEM_PROMPT = """You are an SSA Blue Book analysis assistant for disability attorneys. You help lawyers understand how a client's medical evidence maps to SSA disability listings.

IMPORTANT DISCLAIMERS:
- This is a research aid, not legal advice
- All analysis must be verified by the attorney
- This does not replace professional legal judgment

CRITICAL RULES:

SECTION 2.00 (Special Senses and Speech):
Section 2.00 covers BOTH vision AND hearing disorders. You MUST keep them strictly separate:
- For VISION cases: only reference visual evaluation criteria and listings 2.02, 2.03, 2.04. Evidence gaps should only recommend ophthalmological exams, visual acuity tests, visual field tests, etc.
- For HEARING cases: only reference hearing evaluation criteria and listings 2.10, 2.11. Evidence gaps should only recommend audiometric testing, audiological exams, etc.
- NEVER recommend hearing-related evidence (audiologist, otoscopic exam, audiometric testing) for a vision case, or vice versa.

SSA AGE CLASSIFICATIONS — MANDATORY (you MUST use these exact categories, no exceptions):
- "Younger individual": under age 50
- "Closely approaching advanced age": age 50-54
- "Advanced age": age 55 and older (NOTE: age 55 IS "advanced age", NOT "closely approaching")
- "Closely approaching retirement age": age 60-64
A 55-year-old is AT advanced age. A 54-year-old is closely approaching advanced age. Do not confuse these.

VISUAL ACUITY REFERENCE TABLE (Blue Book Table 1 — use these exact values, do not estimate):
Snellen Acuity → Visual Acuity Efficiency % → Visual Acuity Impairment Value
20/16  → 100% → 0.00
20/20  → 100% → 0.00
20/25  → 95%  → 0.10
20/30  → 90%  → 0.18  (NOT 92%)
20/40  → 85%  → 0.25  (NOT 80%)
20/50  → 75%  → 0.35
20/60  → 70%  → 0.48  (NOT 65%)
20/70  → 65%  → 0.52
20/80  → 60%  → 0.57
20/100 → 50%  → 0.70  (NOT 60%)
20/125 → 45%  → 0.78
20/150 → 40%  → 0.83  (NOT 35%)
20/200 → 20%  → 1.00
20/400 → 0%   → (statutory blindness)
When visual acuity data is provided, ALWAYS look up and state the exact efficiency % and impairment value from this table. Never say "cannot be calculated" if the Snellen acuity is provided.

CALCULATION REQUIREMENTS:
- When you have acuity values, ALWAYS calculate visual acuity efficiency and impairment values using the table above
- Show the threshold each listing requires and compare it to the patient's numbers
- For Listing 2.04A: visual efficiency % = (2 × visual acuity efficiency + visual field efficiency) / 3, must be ≤20%
- For Listing 2.04B: visual impairment value = (visual acuity impairment + visual field impairment) × 0.5, must be ≥1.00
- Never say "calculations cannot be performed" when you have the input values. Show the math.

Given the Blue Book listings below and the client's medical findings, provide:

1. POTENTIALLY MATCHING LISTINGS
   For each listing that could potentially apply:
   - Listing number and title
   - Why it might apply based on the medical findings provided
   IMPORTANT: Analyze EVERY sub-listing individually (e.g., 2.03A, 2.03B, 2.03C, 2.04A, 2.04B). Do not skip sub-listings or say "not fully provided in database." Use the evaluation guidelines to fill in criteria details.

2. CRITERIA ANALYSIS
   For each potentially matching listing and sub-listing, go through EACH criterion and state:
   - ✅ MET — if the medical findings clearly support this criterion (cite the specific evidence)
   - ❓ UNCLEAR — if there's partial evidence but not enough to confirm
   - ❌ MISSING — if no evidence was provided for this criterion
   Show threshold values: what the listing REQUIRES vs. what the patient HAS.

3. EVIDENCE GAPS
   List specifically what additional medical evidence the attorney should obtain:
   - What type of evidence (imaging, lab work, specialist exam, etc.)
   - Why it's needed (which criterion it would satisfy)
   - What it should show to meet the listing requirement
   Only recommend evidence types that are relevant to the specific listings being analyzed.

4. STRENGTH ASSESSMENT
   Rate the overall strength of the case for each listing:
   - STRONG — most criteria clearly met
   - MODERATE — some criteria met, key evidence gaps are obtainable
   - WEAK — significant criteria missing, may need different approach

5. STRATEGIC PATHWAY RANKING
   Rank ALL potential listing pathways from most viable to least viable. For each:
   - State the specific sub-listing (e.g., "2.04B" not just "2.04")
   - Show what threshold must be met and how close the patient is
   - Explain why this pathway is ranked where it is
   - Identify the single most critical piece of evidence needed
   Put the most promising pathway first. This helps the attorney prioritize.

6. RESIDUAL FUNCTIONAL CAPACITY (RFC) CONSIDERATIONS
   If no listing is fully met, outline specific functional limitations supported by the evidence that could support an RFC-based claim:
   - Physical restrictions (lifting, standing, walking, sitting, reaching, etc.)
   - Sensory limitations (vision, hearing, communication)
   - Mental limitations (concentration, social functioning, adaptation)
   - Environmental restrictions (hazards, driving, machinery)
   - How these limitations affect the ability to perform past relevant work
   - Whether the medical-vocational guidelines (Grid Rules) would direct a finding of disability given the claimant's age, education, and work experience

7. CASE STRENGTHS AND WEAKNESSES
   Identify factors that help or hurt the case:
   - Compliance concerns (e.g., elevated A1c suggesting non-compliance)
   - Favorable factors (e.g., age category, work history, education level)
   - Potential SSA counterarguments and how to address them

8. SOURCES
   At the end of your analysis, include a "SOURCES" section listing each Blue Book listing you referenced with its direct link to the SSA website. Use the source URLs provided with each listing. Format each as:
   - Listing X.XX — Title — URL

Be precise. Cite specific listing criteria by letter (A, B, C, D) and sub-criteria by number (1, 2, 3). Reference the specific medical findings the user provided when marking criteria as met.

Do NOT hallucinate criteria. Only reference criteria that appear in the Blue Book text provided to you. If you're unsure about a criterion, say so."""


def get_chroma_collection():
    """Get the ChromaDB collection with the correct embedding function."""
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client.get_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_fn,
    )


def search_blue_book(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Multi-query search: extract medical conditions from the input,
    run targeted sub-queries for each condition, then merge and
    deduplicate results. This ensures each condition gets its own
    semantic match instead of diluting the signal in one big query.

    Guarantees that the top GUARANTEED_PER_QUERY results from each
    sub-query are included, so no condition is drowned out by others.

    Returns a list of matched documents with their text and metadata.
    """
    collection = get_chroma_collection()
    GUARANTEED_PER_QUERY = 3  # top N from each sub-query always included

    # Build condition-specific sub-queries from the medical findings
    sub_queries = _extract_condition_queries(query)

    # Always include the full query as the primary search
    all_queries = [query] + sub_queries

    # Phase 1: Run all queries and collect results
    # Each doc tracks the best (lowest) rank it achieved across all queries
    doc_map = {}  # doc_id -> doc dict

    for q in all_queries:
        results = collection.query(
            query_texts=[q],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        for i in range(len(results["ids"][0])):
            doc_id = results["ids"][0][i]
            dist = results["distances"][0][i]

            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": dist,
                    "best_rank": i,  # best rank across all queries
                }
            else:
                # Keep the best (lowest) distance and rank
                if dist < doc_map[doc_id]["distance"]:
                    doc_map[doc_id]["distance"] = dist
                if i < doc_map[doc_id]["best_rank"]:
                    doc_map[doc_id]["best_rank"] = i

    # Phase 1b: Split into guaranteed (top-ranked in ANY query) vs overflow
    guaranteed_docs = []
    overflow_docs = []
    for doc in doc_map.values():
        if doc["best_rank"] < GUARANTEED_PER_QUERY:
            guaranteed_docs.append(doc)
        else:
            overflow_docs.append(doc)

    # Phase 2: Filter out irrelevant results (distance too high = poor match)
    MAX_DISTANCE = 0.6  # cosine distance threshold; above this is noise
    guaranteed_docs = [d for d in guaranteed_docs if d["distance"] <= MAX_DISTANCE]
    overflow_docs = [d for d in overflow_docs if d["distance"] <= MAX_DISTANCE]

    # Phase 3: Merge — guaranteed docs + best overflow docs by distance
    overflow_docs.sort(key=lambda d: d["distance"])

    # Budget: total cap minus guaranteed slots
    max_total = top_k * 2  # allow more since we have condition-specific queries
    overflow_budget = max(0, max_total - len(guaranteed_docs))
    final_docs = guaranteed_docs + overflow_docs[:overflow_budget]

    # Sort final set by distance for consistent ordering
    final_docs.sort(key=lambda d: d["distance"])
    return final_docs


def _extract_condition_queries(medical_text: str) -> list[str]:
    """
    Extract condition-specific search queries from medical findings.

    This enables targeted retrieval: instead of one diluted embedding,
    each medical condition gets its own focused search. For example,
    a patient with diabetes + vision loss + neuropathy generates
    separate queries for each, catching listings that a single
    combined query would miss.
    """
    text_lower = medical_text.lower()
    sub_queries = []

    # Map keywords in the medical text to focused Blue Book search queries
    condition_map = [
        # Vision
        (["visual acuity", "vision loss", "visual field", "retinopathy", "macular",
          "blindness", "optic", "glaucoma", "cataract"],
         "loss of central visual acuity visual field contraction visual efficiency impairment"),
        # Hearing
        (["hearing loss", "deaf", "audiometric", "cochlear", "tinnitus"],
         "hearing loss audiometric cochlear implant speech recognition"),
        # Musculoskeletal / Spine
        (["back pain", "spine", "disc", "herniation", "stenosis", "lumbar",
          "cervical", "nerve root", "radiculopathy"],
         "disorders of the spine nerve root compression lumbar cervical"),
        # Neuropathy
        (["neuropathy", "peripheral neuropathy", "decreased sensation", "numbness",
          "tingling", "nerve damage"],
         "peripheral neuropathy disorganization of motor function sensory disturbance"),
        # Diabetes / Endocrine
        (["diabetes", "diabetic", "a1c", "insulin", "endocrine", "thyroid"],
         "endocrine disorders diabetes complications multiple body systems"),
        # Kidney / Renal
        (["ckd", "kidney", "renal", "egfr", "dialysis", "transplant", "creatinine"],
         "chronic kidney disease renal impairment genitourinary"),
        # Cardiovascular
        (["heart", "cardiac", "coronary", "hypertension", "heart failure", "arrhythmia"],
         "chronic heart failure ischemic heart disease cardiovascular"),
        # Respiratory
        (["copd", "asthma", "pulmonary", "lung", "breathing", "oxygen", "fev1"],
         "chronic pulmonary insufficiency asthma respiratory disorders"),
        # Mental disorders
        (["depression", "anxiety", "ptsd", "bipolar", "schizophrenia", "mental",
          "psychiatric", "psychological"],
         "depressive disorders anxiety disorders mental disorders cognitive limitations"),
        # Neurological
        (["seizure", "epilepsy", "stroke", "multiple sclerosis", "parkinsons",
          "cerebral", "brain injury"],
         "epilepsy cerebral palsy central nervous system vascular accident neurological"),
        # Cancer
        (["cancer", "tumor", "malignant", "chemotherapy", "radiation", "oncology",
          "carcinoma", "lymphoma", "leukemia"],
         "neoplastic diseases malignant cancer treatment effects"),
        # Immune
        (["hiv", "lupus", "autoimmune", "immune", "rheumatoid", "inflammatory bowel"],
         "immune system disorders systemic lupus inflammatory arthritis"),
        # Skin
        (["dermatitis", "skin lesions", "burns", "psoriasis", "skin disorder"],
         "skin disorders dermatitis burns ichthyosis"),
    ]

    for keywords, search_query in condition_map:
        # Use word boundaries to avoid false positives (e.g., "disc" matching "discrimination")
        patterns = [rf"\b{re.escape(kw)}\b" for kw in keywords]
        if any(re.search(pattern, text_lower) for pattern in patterns):
            sub_queries.append(search_query)

    return sub_queries


def build_claude_prompt(
    medical_findings: str, retrieved_docs: list[dict]
) -> list[dict]:
    """
    Construct the messages array for the Claude API call.

    Separates retrieved docs into listings and section intros,
    then builds a structured user message.
    """
    # Separate listings from section intros, and filter out irrelevant subsections
    listings = []
    section_intros = []
    subsection_docs = []  # Section 2.00 subsections stored as listings
    for doc in retrieved_docs:
        if doc["metadata"].get("doc_type") == "section_intro":
            section_intros.append(doc)
        elif doc["metadata"].get("subsection_topic"):
            # This is a Section 2.00 subsection — treat as evaluation guideline
            subsection_docs.append(doc)
        else:
            listings.append(doc)

    # Filter Section 2.00 subsections: only include those relevant to retrieved listings
    # e.g., if we have vision listings (2.02-2.04), only include visual_disorders subsection
    if subsection_docs:
        listing_nums = {doc["metadata"].get("listing_number", "") for doc in listings}
        has_vision = any(n in listing_nums for n in ("2.02", "2.03", "2.04"))
        has_hearing = any(n in listing_nums for n in ("2.10", "2.11"))
        has_vestibular = "2.07" in listing_nums
        has_speech = "2.09" in listing_nums

        relevant_topics = {"general"}  # always include general guidelines
        if has_vision:
            relevant_topics.add("visual_disorders")
        if has_hearing:
            relevant_topics.add("hearing_loss")
        if has_vestibular:
            relevant_topics.add("vestibular")
        if has_speech:
            relevant_topics.add("speech")

        # If no specific 2.xx listings found, include all subsections
        if not (has_vision or has_hearing or has_vestibular or has_speech):
            relevant_topics = {"visual_disorders", "hearing_loss", "vestibular", "speech", "general"}

        for doc in subsection_docs:
            topic = doc["metadata"].get("subsection_topic", "")
            if topic in relevant_topics:
                section_intros.append(doc)  # include as evaluation guideline

    # Build the user message with retrieved context
    user_parts = []

    if listings:
        user_parts.append("BLUE BOOK LISTINGS (retrieved from database):")
        user_parts.append("-" * 60)
        for doc in listings:
            meta = doc["metadata"]
            source_url = meta.get("source_url", "")
            user_parts.append(
                f"Listing {meta.get('listing_number', 'N/A')} "
                f"- {meta.get('body_system', 'Unknown')} System"
            )
            if source_url:
                user_parts.append(f"Source: {source_url}")
            user_parts.append(doc["text"])
            user_parts.append("-" * 40)
        user_parts.append("")

    if section_intros:
        user_parts.append("EVALUATION GUIDELINES (from relevant body system sections):")
        user_parts.append("-" * 60)
        for doc in section_intros:
            meta = doc["metadata"]
            subsection_topic = meta.get("subsection_topic", "")
            label = meta.get("listing_number", meta.get("section_number", "N/A"))
            user_parts.append(
                f"Section {label} "
                f"- {meta.get('body_system', 'Unknown')}"
            )
            intro_text = doc["text"]
            # Visual disorders subsection gets higher limit — contains calculation
            # tables (Table 1, Table 2) that are critical for accurate analysis
            if subsection_topic == "visual_disorders":
                max_len = 20000  # keep tables intact
            else:
                max_len = 3000
            if len(intro_text) > max_len:
                intro_text = intro_text[:max_len] + "\n[... truncated for brevity ...]"
            user_parts.append(intro_text)
            user_parts.append("-" * 40)
        user_parts.append("")

    user_parts.append("CLIENT'S MEDICAL FINDINGS:")
    user_parts.append("-" * 60)
    user_parts.append(medical_findings)
    user_parts.append("-" * 60)
    user_parts.append("")
    user_parts.append(
        "Please analyze these medical findings against the Blue Book listings above."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def call_claude(messages: list[dict]) -> str:
    """
    Call Claude via OpenRouter API.

    Returns the assistant's response text.
    Raises an exception with a user-friendly message on failure.
    """
    try:
        response = requests.post(
            OPENROUTER_BASE_URL,
            headers=get_openrouter_headers(),
            json={
                "model": CLAUDE_MODEL,
                "messages": messages,
                "max_tokens": 8192,
                "temperature": 0.2,
            },
            timeout=120,
        )
    except requests.Timeout:
        raise Exception(
            "The analysis request timed out. Claude may be under heavy load. "
            "Please try again in a moment."
        )
    except requests.ConnectionError:
        raise Exception(
            "Could not connect to OpenRouter API. "
            "Please check your internet connection."
        )

    if response.status_code == 401:
        raise Exception(
            "Invalid OpenRouter API key. "
            "Check your .env file and make sure OPENROUTER_API_KEY is correct."
        )
    elif response.status_code == 429:
        raise Exception(
            "Rate limit exceeded on OpenRouter. "
            "Please wait a moment and try again."
        )
    elif response.status_code >= 500:
        raise Exception(
            f"OpenRouter server error ({response.status_code}). "
            "Please try again in a moment."
        )
    elif response.status_code != 200:
        raise Exception(
            f"OpenRouter API error ({response.status_code}): {response.text[:200]}"
        )

    data = response.json()

    # Extract the response text
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise Exception(
            f"Unexpected response format from OpenRouter: {str(data)[:200]}"
        )


def _validate_analysis(analysis: str, medical_findings: str) -> list[str]:
    """
    Post-analysis validation layer.

    Checks the Claude output for completeness and common errors.
    Returns a list of warning strings (empty if all checks pass).
    """
    warnings = []
    analysis_upper = analysis.upper()

    # --- Required Section Checks ---
    required_sections = {
        "POTENTIALLY MATCHING LISTINGS": "Listing identification section",
        "CRITERIA ANALYSIS": "Criteria analysis section",
        "EVIDENCE GAPS": "Evidence gaps section",
        "STRENGTH ASSESSMENT": "Strength assessment section",
        "STRATEGIC PATHWAY RANKING": "Strategic pathway ranking",
        "RFC": "RFC considerations section",
        "STRENGTHS AND WEAKNESSES": "Case strengths and weaknesses",
        "SOURCES": "Sources section with Blue Book links",
    }
    for keyword, label in required_sections.items():
        if keyword not in analysis_upper:
            warnings.append(f"Missing section: {label}")

    # --- Age Classification Check ---
    findings_lower = medical_findings.lower()
    # Support "Age 55", "Aged 55", "55-year-old", "55 year old"
    age_match = re.search(r"(?:age|aged?)\s*[:\s]*(\d{2})|(\d{2})\s*(?=-year-old|year\s*old)", findings_lower)
    if age_match:
        # Get the first non-None group
        age_str = age_match.group(1) or age_match.group(2)
        age = int(age_str)
        correct_category = _get_age_category(age)
        # Check for common misclassifications
        if age >= 55 and "closely approaching advanced age" in analysis.lower():
            warnings.append(
                f"AGE ERROR: Patient is {age} years old = \"{correct_category}\". "
                f"Analysis incorrectly says \"closely approaching advanced age\" "
                f"(that category is for ages 50-54 only)."
            )
        if age >= 50 and age < 55 and "advanced age" in analysis.lower():
            # Make sure it's not "closely approaching advanced age"
            if "closely approaching advanced age" not in analysis.lower():
                warnings.append(
                    f"AGE ERROR: Patient is {age} years old = \"{correct_category}\". "
                    f"Analysis may have the wrong age category."
                )

    # --- Calculation Check (vision cases) ---
    vision_keywords = ["visual acuity", "snellen", "retinopathy", "visual field",
                       "vision loss", "macular", "optic"]
    has_vision = any(kw in findings_lower for kw in vision_keywords)
    if has_vision:
        # Check that actual numbers/percentages appear (not "cannot be calculated")
        if "cannot be calculated" in analysis.lower() or "cannot be determined" in analysis.lower():
            warnings.append(
                "CALCULATION GAP: Analysis says values 'cannot be calculated' or "
                "'cannot be determined' despite visual acuity data being available. "
                "Use the Visual Acuity Reference Table to look up exact values."
            )

    # --- Hearing/Vision Contamination Check ---
    if has_vision:
        hearing_contaminants = ["audiologist", "audiometric", "otoscopic",
                                "hearing evaluation", "cochlear", "audiological"]
        found = [term for term in hearing_contaminants if term in analysis.lower()]
        if found:
            warnings.append(
                f"CONTAMINATION WARNING: Vision case contains hearing-related "
                f"recommendations: {', '.join(found)}. These should be removed."
            )

    return warnings


def _get_age_category(age: int) -> str:
    """Return the correct SSA age classification."""
    if age < 50:
        return "younger individual"
    elif age < 55:
        return "closely approaching advanced age"
    elif age < 60:
        return "advanced age"
    elif age < 65:
        return "closely approaching retirement age"
    else:
        return "retirement age"


def analyze_medical_findings(medical_findings: str) -> dict:
    """
    Main entry point for the RAG pipeline.

    Takes medical findings text and returns a structured analysis result.
    """
    # Validate input
    medical_findings = medical_findings.strip()
    if not medical_findings:
        return {
            "status": "error",
            "analysis": "",
            "matched_listings": [],
            "retrieved_count": 0,
            "disclaimer": "",
            "error": "Medical findings text cannot be empty.",
        }

    if len(medical_findings) < 20:
        return {
            "status": "error",
            "analysis": "",
            "matched_listings": [],
            "retrieved_count": 0,
            "disclaimer": "",
            "error": "Please provide more detailed medical findings (at least a few sentences).",
        }

    # Step 1: Search ChromaDB for relevant documents
    try:
        retrieved_docs = search_blue_book(medical_findings)
    except Exception as e:
        return {
            "status": "error",
            "analysis": "",
            "matched_listings": [],
            "retrieved_count": 0,
            "disclaimer": "",
            "error": f"Database search failed: {str(e)}. Make sure you've run build_db.py first.",
        }

    if not retrieved_docs:
        return {
            "status": "no_results",
            "analysis": "No matching Blue Book listings were found for the provided medical findings.",
            "matched_listings": [],
            "retrieved_count": 0,
            "disclaimer": "This is a research aid for attorneys. It does not constitute legal advice.",
        }

    # Step 2: Build the prompt with retrieved context
    messages = build_claude_prompt(medical_findings, retrieved_docs)

    # Step 3: Call Claude for analysis
    try:
        analysis_text = call_claude(messages)
    except Exception as e:
        return {
            "status": "error",
            "analysis": "",
            "matched_listings": [],
            "retrieved_count": len(retrieved_docs),
            "disclaimer": "",
            "error": str(e),
        }

    # Step 4: Validate the analysis output
    validation_warnings = _validate_analysis(analysis_text, medical_findings)

    # If validation found critical issues, append them to the analysis
    if validation_warnings:
        warning_block = "\n\n---\n⚠️ **AUTOMATED VALIDATION FLAGS:**\n"
        for w in validation_warnings:
            warning_block += f"- {w}\n"
        analysis_text += warning_block

    # Step 5: Extract listing numbers mentioned in the response
    matched_listings = list(
        set(re.findall(r"(?:Listing\s+)?(\d{1,2}\.\d{2})", analysis_text))
    )
    matched_listings.sort()

    # Step 6: Build source links from retrieved documents
    sources = {}
    for doc in retrieved_docs:
        meta = doc["metadata"]
        listing_num = meta.get("listing_number", "")
        source_url = meta.get("source_url", "")
        if listing_num and source_url and listing_num not in sources:
            sources[listing_num] = {
                "listing_number": listing_num,
                "body_system": meta.get("body_system", ""),
                "source_url": source_url,
            }

    return {
        "status": "success",
        "analysis": analysis_text,
        "matched_listings": matched_listings,
        "retrieved_count": len(retrieved_docs),
        "sources": sources,
        "validation_warnings": validation_warnings,
        "disclaimer": "This is a research aid for attorneys. It does not constitute legal advice. All analysis must be independently verified.",
    }
