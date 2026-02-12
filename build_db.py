"""
Build the ChromaDB vector database from scraped Blue Book JSON data.

Loads listings and section intros from JSON files, embeds them using
sentence-transformers, and stores them in a persistent ChromaDB collection.

Usage:
    python build_db.py

Can be re-run to rebuild the database (deletes and recreates the collection).
"""

import json
import os
import sys

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    EMBEDDING_MODEL,
    LISTINGS_JSON,
    SECTIONS_JSON,
)


def build_database():
    """Build/rebuild the ChromaDB collection from JSON data."""

    # Check that data files exist
    if not os.path.exists(LISTINGS_JSON):
        print(f"ERROR: {LISTINGS_JSON} not found.")
        print("Run 'python scraper.py' first to scrape the Blue Book data.")
        sys.exit(1)

    if not os.path.exists(SECTIONS_JSON):
        print(f"ERROR: {SECTIONS_JSON} not found.")
        print("Run 'python scraper.py' first to scrape the Blue Book data.")
        sys.exit(1)

    # Load data
    print("Loading Blue Book data from JSON files...")
    with open(LISTINGS_JSON, "r", encoding="utf-8") as f:
        listings = json.load(f)
    with open(SECTIONS_JSON, "r", encoding="utf-8") as f:
        sections = json.load(f)

    print(f"  Loaded {len(listings)} listings and {len(sections)} section intros")

    # Initialize embedding function
    # First run will download the model (~80MB)
    print(f"\nInitializing embedding model: {EMBEDDING_MODEL}")
    print("  (First run will download the model, this may take a minute...)")
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    # Create persistent ChromaDB client
    print(f"\nSetting up ChromaDB at: {CHROMA_DB_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Delete existing collection if present (for clean rebuilds)
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
        print(f"  Deleted existing '{CHROMA_COLLECTION_NAME}' collection")
    except Exception:
        pass

    # Create fresh collection with cosine similarity
    collection = client.create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"  Created collection: '{CHROMA_COLLECTION_NAME}'")

    # Add listings
    print(f"\nAdding {len(listings)} listings to database...")
    for i, listing in enumerate(listings):
        # Combine title + full text + summary for better embedding quality
        doc_text = (
            f"{listing['title']}\n\n"
            f"{listing['full_text']}\n\n"
            f"Summary: {listing['criteria_summary']}"
        )

        # Build metadata — include subsection info if present (Section 2.00 splits)
        meta = {
            "listing_number": listing["listing_number"],
            "body_system": listing["body_system"],
            "section_number": listing["section_number"],
            "doc_type": "listing",
            "source_url": listing.get("source_url", ""),
        }
        if "subsection" in listing:
            meta["subsection"] = listing["subsection"]
            meta["subsection_topic"] = listing.get("subsection_topic", "")

        collection.add(
            documents=[doc_text],
            ids=[f"listing_{listing['listing_number']}"],
            metadatas=[meta],
        )

        # Progress indicator
        if (i + 1) % 10 == 0 or i + 1 == len(listings):
            print(f"  Added {i + 1}/{len(listings)} listings")

    # Add section intros
    print(f"\nAdding {len(sections)} section intros to database...")
    for section in sections:
        if not section.get("intro_text", "").strip():
            continue

        collection.add(
            documents=[section["intro_text"]],
            ids=[f"section_{section['section_number']}"],
            metadatas=[
                {
                    "section_number": section["section_number"],
                    "body_system": section["body_system"],
                    "doc_type": "section_intro",
                }
            ],
        )

    # Verify
    total = collection.count()
    print(f"\nDatabase built successfully!")
    print(f"  Total documents: {total}")
    print(f"  Database location: {os.path.abspath(CHROMA_DB_PATH)}")

    # Quick test query
    print(f"\nRunning test query: 'back pain nerve compression spine'...")
    results = collection.query(
        query_texts=["back pain nerve compression spine"],
        n_results=3,
        include=["metadatas", "distances"],
    )
    print("  Top 3 results:")
    for i, (doc_id, metadata, distance) in enumerate(
        zip(results["ids"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(
            f"    {i + 1}. {doc_id} - {metadata.get('body_system', 'N/A')} "
            f"(distance: {distance:.4f})"
        )

    print(f"\nDone! Next step: python main.py")


if __name__ == "__main__":
    build_database()
