Evaluation Results

 Summary

| Metric | Score |
|---|---|
| Total questions | 13 |
| Overall correctness | 92% |
| Answerable correctness | 86% reported / 57% true (see note below) |
| Unanswerable refusal rate | 100% |
| Hallucination rate | 0% |
| Comparative correctness | 100% |
| Average citations per answer | 8.8 |
| Average latency | 6.8 seconds |

Full per-question results: `data/eval_results.json`

 Question Set

I wrote 13 questions across three categories.

Answerable (7): Questions the filing should be able to answer directly. These cover Pfizer's 2024 revenue, net income, R&D spend, total debt, operating cash flow, management commentary on Comirnaty revenue decline, and patent expiry risk disclosures. I recorded expected keywords for each and used an LLM grader to check whether the system response contained them.

**Unanswerable (4): Questions that no 10-K filing can answer. I asked for Pfizer's 2027 revenue forecast, hiring plans for the next quarter, current stock price, and CEO comments from a 2019 earnings call. The correct behavior is to refuse.

Comparative (2): Questions that require pulling data from more than one company. I asked which company had the highest R&D intensity across all four, and how Pfizer and Lilly revenue trends compared over two years. These questions only work if the retrieval system actually hits different company indexes.

Results and Interpretation

The refusal behavior performed well. All four unanswerable questions returned clean INSUFFICIENT_DATA responses. The system did not attempt to generate plausible numbers for future forecasts or real-time data. The 0% hallucination rate reflects genuine behavior, not a measurement artifact.

The comparative questions also worked after I fixed the retrieval logic. The original implementation did one merged similarity search across all indexes, which returned mostly Pfizer chunks because Pfizer's index is the largest. Pharma Financial Analysis Dashboard

A RAG-powered financial analysis dashboard over SEC 10-K filings for four major
pharma companies: Pfizer (PFE), Eli Lilly (LLY), AbbVie (ABBV), and Johnson & Johnson (JNJ).

 Why These Companies

These four represent the most analytically compelling stories in large-cap pharma:
- **Pfizer** — post-COVID revenue contraction from ~$100B peak to ~$63B
- **Eli Lilly** — explosive GLP-1 growth (Mounjaro/Zepbound), highest margins in the group
- **AbbVie** — navigating the Humira biosimilar cliff, offset by Skyrizi/Rinvoq
- **J&J** — post-Kenvue spinoff restructuring, creating a restatement comparability challenge

Choosing pharma was intentional: CustomerInsights.AI serves pharma commercial teams,
so the domain language (R&D intensity, patent cliffs, biosimilar erosion) is directly
relevant to their evaluators.

 How to Run

 Prerequisites
- Python 3.10+
- A Groq API key (free at https://console.groq.com)
- SEC EDGAR access (public, no key needed)

 Setup

```bash
git clone <repo> && cd CustomerInsight.AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY and SEC_USER_AGENT
```

 First Run — Build the Pipeline

```bash
streamlit run app.py
```

Then in the app, for each ticker (PFE, LLY, ABBV, JNJ):
1. **Pipeline tab** → Download filing → Parse document → Build embeddings

Or run the bulk indexer from terminal:

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
        print(f'{ticker}: {vs._collection.count()} chunks')
"
```

Run Evaluation

```bash
python eval.py
```

Architecture The fix fetches a fixed number of chunks from each company separately, which guarantees representation from every ticker.

Honest Assessment of the Answerable Score# Pharma Financial Analysis Dashboard

A RAG-powered financial analysis dashboard over SEC 10-K filings for four major
pharma companies: Pfizer (PFE), Eli Lilly (LLY), AbbVie (ABBV), and Johnson & Johnson (JNJ).

Why These Companies

These four represent the most analytically compelling stories in large-cap pharma:
- **Pfizer** — post-COVID revenue contraction from ~$100B peak to ~$63B
- **Eli Lilly** — explosive GLP-1 growth (Mounjaro/Zepbound), highest margins in the group
- **AbbVie** — navigating the Humira biosimilar cliff, offset by Skyrizi/Rinvoq
- **J&J** — post-Kenvue spinoff restructuring, creating a restatement comparability challenge

Choosing pharma was intentional: CustomerInsights.AI serves pharma commercial teams,
so the domain language (R&D intensity, patent cliffs, biosimilar erosion) is directly
relevant to their evaluators.

How to Run

### Prerequisites
- Python 3.10+
- A Groq API key (free at https://console.groq.com)
- SEC EDGAR access (public, no key needed)

Setup

```bash
git clone <repo> && cd CustomerInsight.AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY and SEC_USER_AGENT
```

First Run — Build the Pipeline

```bash
streamlit run app.py
```

Then in the app, for each ticker (PFE, LLY, ABBV, JNJ):
1. **Pipeline tab** → Download filing → Parse document → Build embeddings

Or run the bulk indexer from terminal:

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
        print(f'{ticker}: {vs._collection.count()} chunks')
"
```

### Run Evaluation

```bash
python eval.py
```

Architecture

The 86% answerable correctness figure is inflated. The LLM grader has a flaw: it treats INSUFFICIENT_DATA as an acceptable response even for answerable questions, because it pattern-matches the string rather than checking the question category. Questions A02, A04, A05, and A06 received INSUFFICIENT_DATA responses from the system and the grader marked them correct.

The real answerable correctness is 57%, meaning 4 out of 7 answerable questions got actual answers. The other 3 triggered unnecessary refusals.

The cause is chunk size. At 1200 characters, chunks are too large and pull in too much surrounding narrative. A question about total debt retrieves chunks from sections that discuss debt in general terms rather than the balance sheet row with the actual number. Reducing chunk size to around 700 characters with higher retrieval k would improve recall on these specific line-item questions.

This is the first thing I would fix before using this in production.

A Ground Truth Error

Question A01 asked for Pfizer's 2024 revenue and I wrote the expected range as $58-59 billion based on an estimate I had before running the pipeline. The filing reports $63,627 million. The system returned the correct figure. My expected range was wrong.

This highlights why you need to verify eval question ground truth against the actual source documents before trusting aggregate scores. One bad ground truth entry can shift correctness percentages and mislead you about system quality.
