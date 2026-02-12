# Blue Book RAG Agent

A tool for SSDI disability lawyers to check whether a client's medical evidence matches SSA Blue Book disability listings. Paste medical findings, get back a detailed analysis of matching listings, met/missing criteria, and evidence gaps.

## Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai/) API key

## Setup

1. Install dependencies (note: sentence-transformers will download ~2GB of PyTorch dependencies):

```bash
pip install -r requirements.txt
```

2. Configure your API key:

```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

3. Scrape the Blue Book data:

```bash
python scraper.py
```

If SSA blocks the requests (403 errors), the scraper will print instructions for manually downloading the HTML files.

4. Build the vector database:

```bash
python build_db.py
```

5. Start the server:

```bash
python main.py
```

6. Open http://localhost:8000 in your browser.

## Usage

1. Paste your client's medical findings into the text area (diagnoses, symptoms, test results, functional limitations)
2. Click "Analyze"
3. Review the results showing matching Blue Book listings, criteria analysis, and evidence gaps

## Troubleshooting

- **SSA 403 errors during scraping**: Download the Blue Book pages manually from your browser, save as HTML files in `data/raw_html/` named `section_1.00.html`, `section_2.00.html`, etc., then re-run `python scraper.py`
- **ChromaDB errors**: Delete the `chroma_db/` folder and re-run `python build_db.py`
- **OpenRouter API errors**: Check that your API key is correct in `.env` and that you have credits on OpenRouter
