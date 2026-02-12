"""
Scrape and parse the SSA Blue Book (all 14 adult listing sections).

Downloads each section page, extracts individual listings and section intros,
and saves structured JSON to data/ directory.

Usage:
    python scraper.py

If SSA blocks requests (403), the scraper will:
1. Try with browser-like headers
2. Fall back to local HTML files in data/raw_html/
3. Print instructions for manual download if neither works
"""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

from config import (
    BLUE_BOOK_URLS,
    DATA_DIR,
    LISTINGS_JSON,
    RAW_HTML_DIR,
    REQUEST_HEADERS,
    SECTION_MAP,
    SECTION_URL_MAP,
    SECTIONS_JSON,
)


def fetch_page(url: str, section_number: str) -> str | None:
    """
    Fetch a Blue Book section page. Tries the live URL first,
    then falls back to a locally saved HTML file.

    Returns the HTML string, or None if all attempts fail.
    """
    # Attempt 1: Fetch from SSA website
    try:
        print(f"  Fetching from SSA: {url}")
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        if response.status_code == 200:
            # Cache the raw HTML for future use
            save_raw_html(section_number, response.text)
            return response.text
        else:
            print(f"  Got status {response.status_code}, trying fallback...")
    except requests.RequestException as e:
        print(f"  Request failed: {e}, trying fallback...")

    # Attempt 2: Load from local cache
    return fetch_from_local(section_number)


def fetch_from_local(section_number: str) -> str | None:
    """Load HTML from data/raw_html/ fallback directory."""
    filename = f"section_{section_number}.html"
    filepath = os.path.join(RAW_HTML_DIR, filename)
    if os.path.exists(filepath):
        print(f"  Loading from local file: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return None


def save_raw_html(section_number: str, html: str):
    """Save raw HTML to data/raw_html/ for caching."""
    os.makedirs(RAW_HTML_DIR, exist_ok=True)
    filename = f"section_{section_number}.html"
    filepath = os.path.join(RAW_HTML_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


def find_content_div(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Find the main content area of the page.
    SSA pages use different structures, so we try multiple selectors.
    """
    # Try common content selectors
    for selector in [
        {"class_": "field-items"},
        {"id": "content"},
        {"class_": "content"},
        {"role": "main"},
    ]:
        found = soup.find("div", **selector)
        if found:
            return found

    # Try <main> tag
    main = soup.find("main")
    if main:
        return main

    # Last resort: use body
    return soup.body if soup.body else soup


def parse_section(html: str, section_number: str, body_system: str) -> dict:
    """
    Parse a Blue Book section page into intro text and individual listings.

    Returns:
        {
            "section_intro": { section_number, body_system, intro_text },
            "listings": [ { listing_number, title, body_system, section_number, full_text, criteria_summary } ]
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    content = find_content_div(soup)
    text = content.get_text(separator="\n", strip=True)

    # Split the text into chunks based on listing number patterns.
    # Listing numbers look like: 1.15, 2.04, 12.06, 14.09
    # We split right before each listing number that starts a new listing.
    # Pattern: a listing number at the start of a line (or after whitespace),
    # followed by a space and title text.
    # We need to be careful not to split on sub-criteria references like "1.15A"
    # or inline mentions like "see listing 1.15".

    # First, extract the section intro (everything before the first individual listing)
    # Individual listings start with a number like X.XX followed by title text
    section_prefix = section_number.split(".")[0]  # e.g., "1" from "1.00"

    # Pattern to find individual listing starts (not the X.00 section intro)
    # Matches: "1.15 Title text" or "12.04 Title text" at line boundaries
    listing_pattern = re.compile(
        rf"^({section_prefix}\.\d{{2}})\s+([A-Z].*?)$",
        re.MULTILINE,
    )

    matches = list(listing_pattern.finditer(text))

    # Everything before the first listing match is the section intro
    if matches:
        intro_text = text[: matches[0].start()].strip()
    else:
        intro_text = text.strip()

    # Extract individual listings
    listings = []
    for i, match in enumerate(matches):
        listing_number = match.group(1)
        title_text = match.group(2).strip()

        # Get the full text: from this match to the next match (or end of text)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        full_text = text[start:end].strip()

        # Create a brief criteria summary (first 300 chars after the title)
        title_line = f"{listing_number} {title_text}"
        remaining = full_text[len(title_line) :].strip()
        criteria_summary = remaining[:300].strip()
        if len(remaining) > 300:
            criteria_summary += "..."

        # Build source URL linking directly to this section on SSA website
        source_url = SECTION_URL_MAP.get(section_number, "")

        listings.append(
            {
                "listing_number": listing_number,
                "title": title_text,
                "body_system": body_system,
                "section_number": section_number,
                "full_text": full_text,
                "criteria_summary": criteria_summary,
                "source_url": source_url,
            }
        )

    return {
        "section_intro": {
            "section_number": section_number,
            "body_system": body_system,
            "intro_text": intro_text,
            "source_url": SECTION_URL_MAP.get(section_number, ""),
        },
        "listings": listings,
    }


def split_section_2_listing(listings: list[dict]) -> list[dict]:
    """
    Split the mega-listing '2.00' into separate subsection documents.

    Section 2.00 contains evaluation guidelines for BOTH vision (A) and
    hearing (B), plus vestibular (C), speech (D), and general (E).
    Keeping them as one document causes hearing criteria to contaminate
    vision analysis and vice versa.

    Returns the listings list with 2.00 replaced by 2.00_A through 2.00_E.
    """
    result = []
    for listing in listings:
        if listing["listing_number"] != "2.00":
            result.append(listing)
            continue

        text = listing["full_text"]

        # Find subsection boundaries: B, C, D, E headers
        # Section A has no explicit header — it's everything before B
        subsection_pattern = re.compile(
            r"^([B-E])\.\s+(How do we .+|Loss of .+)",
            re.MULTILINE,
        )
        matches = list(subsection_pattern.finditer(text))

        if not matches:
            # Fallback: keep as-is if headers not found
            result.append(listing)
            continue

        # Define subsection metadata
        topic_map = {
            "A": "visual_disorders",
            "B": "hearing_loss",
            "C": "vestibular",
            "D": "speech",
            "E": "general",
        }
        topic_titles = {
            "A": "Visual Disorders Evaluation",
            "B": "Hearing Loss Evaluation",
            "C": "Vestibular Function Evaluation",
            "D": "Speech Loss Evaluation",
            "E": "General Evaluation Guidelines",
        }

        # Build subsection boundaries: [(letter, start, end), ...]
        boundaries = []
        # Section A: from start to first match
        boundaries.append(("A", 0, matches[0].start()))
        # Sections B through E
        for i, match in enumerate(matches):
            letter = match.group(1)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            boundaries.append((letter, start, end))

        for letter, start, end in boundaries:
            sub_text = text[start:end].strip()
            if not sub_text:
                continue

            result.append({
                "listing_number": f"2.00_{letter}",
                "title": f"Section 2.00{letter} - {topic_titles[letter]}",
                "body_system": listing["body_system"],
                "section_number": listing["section_number"],
                "full_text": sub_text,
                "criteria_summary": sub_text[:300].strip() + ("..." if len(sub_text) > 300 else ""),
                "source_url": listing["source_url"],
                "subsection": letter,
                "subsection_topic": topic_map[letter],
            })

        print(f"  Split listing 2.00 into {len(boundaries)} subsections: {[b[0] for b in boundaries]}")

    return result


def scrape_all() -> tuple[list[dict], list[dict]]:
    """
    Scrape all 14 Blue Book sections.

    Returns:
        (all_listings, all_sections) - two lists of dicts
    """
    all_listings = []
    all_sections = []
    failed_sections = []

    for section_number, url in BLUE_BOOK_URLS:
        body_system = SECTION_MAP.get(section_number, "Unknown")
        print(f"\n[{section_number}] {body_system}")

        html = fetch_page(url, section_number)
        if html is None:
            print(f"  FAILED - Could not fetch section {section_number}")
            failed_sections.append((section_number, body_system, url))
            continue

        result = parse_section(html, section_number, body_system)
        all_sections.append(result["section_intro"])
        all_listings.extend(result["listings"])
        print(f"  Found {len(result['listings'])} listings")

        # Be polite to SSA servers
        time.sleep(2)

    # Deduplicate listings: keep the version with the longest full_text
    deduped = {}
    for listing in all_listings:
        num = listing["listing_number"]
        if num not in deduped or len(listing["full_text"]) > len(deduped[num]["full_text"]):
            deduped[num] = listing
    all_listings = list(deduped.values())

    # Split Section 2.00 mega-listing into separate vision/hearing/etc. subsections
    all_listings = split_section_2_listing(all_listings)

    # Report results
    print(f"\n{'='*60}")
    print(f"Scraping complete!")
    print(f"  Sections processed: {len(all_sections)}/{len(BLUE_BOOK_URLS)}")
    print(f"  Total listings found: {len(all_listings)} (deduplicated)")

    if failed_sections:
        print(f"\n  FAILED SECTIONS ({len(failed_sections)}):")
        print(f"  To fix: manually download these pages and save as HTML in {RAW_HTML_DIR}/")
        for sec_num, sys_name, sec_url in failed_sections:
            filename = f"section_{sec_num}.html"
            print(f"    - {sec_num} ({sys_name})")
            print(f"      URL: {sec_url}")
            print(f"      Save as: {os.path.join(RAW_HTML_DIR, filename)}")

    return all_listings, all_sections


def save_data(listings: list[dict], sections: list[dict]):
    """Save scraped data to JSON files."""
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(LISTINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(listings)} listings to {LISTINGS_JSON}")

    with open(SECTIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(sections, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(sections)} section intros to {SECTIONS_JSON}")


def main():
    """Main entry point: scrape Blue Book and save to JSON."""
    print("SSA Blue Book Scraper")
    print("=" * 60)
    print("Scraping all 14 adult listing sections...")

    listings, sections = scrape_all()

    if not listings:
        print("\nERROR: No listings were extracted.")
        print("This likely means all SSA pages returned 403 errors.")
        print(f"\nManual fallback:")
        print(f"1. Open each URL in your browser")
        print(f"2. Save the page as HTML (Ctrl+S)")
        print(f"3. Put the files in: {os.path.abspath(RAW_HTML_DIR)}")
        print(f"4. Name them: section_1.00.html, section_2.00.html, etc.")
        print(f"5. Re-run this script")
        return

    save_data(listings, sections)
    print("\nDone! Next step: python build_db.py")


if __name__ == "__main__":
    main()
