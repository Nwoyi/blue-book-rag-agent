"""
Download Blue Book pages using Playwright (headless browser).
Use this when SSA blocks requests (403 errors).

Usage:
    python download_pages.py
"""

import os
import time
from playwright.sync_api import sync_playwright

from config import BLUE_BOOK_URLS, RAW_HTML_DIR

def main():
    os.makedirs(RAW_HTML_DIR, exist_ok=True)

    print("Downloading Blue Book pages with headless browser...")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for section_number, url in BLUE_BOOK_URLS:
            filename = f"section_{section_number}.html"
            filepath = os.path.join(RAW_HTML_DIR, filename)

            print(f"\n[{section_number}] Fetching: {url}")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  Saved: {filepath} ({len(html):,} bytes)")
            except Exception as e:
                print(f"  ERROR: {e}")

            time.sleep(2)

        browser.close()

    print(f"\n{'='*60}")
    print("Done! Now run: python scraper.py")

if __name__ == "__main__":
    main()
