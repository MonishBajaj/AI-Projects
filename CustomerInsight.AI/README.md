 Pharma Financial Analysis Dashboard

A Streamlit dashboard that downloads SEC 10-K filings for four large pharma companies, extracts financial tables, indexes the content into a vector store, and answers natural language questions with citations traced back to the source filing.

Companies

I chose Pfizer (PFE), Eli Lilly (LLY), AbbVie (ABBV), and Johnson & Johnson (JNJ) because each company tells a different financial story over the same period. Pfizer saw revenue fall sharply after COVID vaccine demand collapsed. Lilly grew rapidly on GLP-1 drug sales. AbbVie lost Humira exclusivity to biosimilars and had to replace that revenue with newer drugs. J&J spun off its consumer division in 2023, which creates a real comparability problem across years. Putting these four side by side produces comparisons that are actually worth analyzing.

Setup

You need Python 3.10 or higher and a free Groq API key from https://console.groq.com.

```bash
git clone <repo> && cd CustomerInsight.AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add two values to `.env`:
```
GROQ_API_KEY=your_key_here
SEC_USER_AGENT=Your Name your@email.com
```

Start the app:
```bash
streamlit run app.py
```

Building the Pipeline

On first run, go to the Pipeline tab and run these steps for each ticker: Download filing, Parse document, Build embeddings. Each company takes about 2 to 3 minutes. The embedding model downloads once at roughly 90MB and runs locally after that.

To index all four companies at once from the terminal:

```bash
python -c "
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('$(pwd)/.env')
import parser, embedder
for ticker in ['PFE', 'LLY', 'ABBV', 'JNJ']:
    parsed = parser.load_parsed(ticker)
    if parsed:
        vs = embedder.embed_ticker(parsed, reset=True)
        print(f'{ticker}: {vs._collection.count()} chunks indexed')
"
```

To run the evaluation suite:
```bash
python eval.py
```

Design Decisions

**Table extraction uses BeautifulSoup, not regex.** SEC 10-K filings are HTML documents with many tables. Regex on raw text finds the wrong number because the label "revenues" appears in footnotes, segment breakdowns, and risk factors well before the consolidated income statement row. BeautifulSoup parses the DOM so we can match row labels against specific table cells.

**Embeddings run locally.** The app uses `all-MiniLM-L6-v2` from HuggingFace with no API calls. It runs on CPU and produces good retrieval quality for financial text.

**Cross-company queries fetch from each store separately.** A single merged similarity search returns mostly chunks from whichever company has the most similar text to the query. Instead, the app fetches a fixed number of chunks from each company's index so every company contributes to comparative answers.

**The system refuses unanswerable questions.** When retrieved context does not support an answer, the system returns an INSUFFICIENT_DATA response rather than generating a plausible-sounding number. This was a deliberate choice because a wrong number is worse than no number.

Document Sources

All filings come from the SEC EDGAR public API. No authentication required.

| Company | Ticker | CIK | Period | Filed |
|---|---|---|---|---|
| Pfizer Inc. | PFE | 0000078003 | FY2025 | 2026-02-26 |
| Eli Lilly and Company | LLY | 0000059478 | FY2025 | 2026-02-12 |
| AbbVie Inc. | ABBV | 0001551152 | FY2025 | 2026-02-20 |
| Johnson & Johnson | JNJ | 0000200406 | FY2025 | 2026-02-11 |

EDGAR submissions endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`

Project Structure

```
├── app.py              # Streamlit UI with four tabs
├── config.py           # API keys, paths, ticker config
├── downloader.py       # SEC EDGAR filing fetcher
├── parser.py           # HTML table and text extraction
├── embedder.py         # Chunking and ChromaDB indexing
├── rag_chain.py        # Query rewriting, retrieval, answer generation
├── metrics.py          # Financial ratio computation
├── eval.py             # Labeled Q&A evaluation framework
├── requirements.txt
├── .env.example
├── README.md
├── WRITEUP.md
├── EVAL_RESULTS.md
└── data/               # Generated at runtime, gitignored
    ├── filings/
    ├── parsed/
    └── chroma/
```
