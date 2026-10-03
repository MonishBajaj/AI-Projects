WRITEUP.md

Architecture and Files

The system runs a RAG pipeline over SEC 10-K filings for Pfizer, Eli Lilly, AbbVie, and Johnson & Johnson.

`downloader.py` fetches the most recent 10-K for each company from the SEC EDGAR submissions API. `parser.py` uses BeautifulSoup to extract HTML tables into structured rows and columns, and pulls clean text from the rest of the document. `embedder.py` splits the content into chunks using LangChain's RecursiveCharacterTextSplitter and stores them in a ChromaDB PersistentClient collection using HuggingFace `all-MiniLM-L6-v2` embeddings, which run locally with no API key. `rag_chain.py` rewrites the user query into a retrieval-optimized search string, fetches chunks from each company's index separately, and passes the combined context to Groq's LLaMA 3.3 70B to generate a cited answer. `metrics.py` extracts financial line items from parsed tables and computes ratios including gross margin, operating margin, net margin, R&D intensity, and free cash flow. `app.py` presents everything through a four-tab Streamlit interface covering pipeline management, per-company metrics, cross-company comparison charts, and a chat interface. `eval.py` runs a labeled question set and reports correctness, refusal rate, and hallucination rate.

I chose pharma specifically because the four companies have meaningfully different financial trajectories, which makes comparison worthwhile. Choosing four companies in the same sector also mirrors what CustomerInsights.AI builds for its pharma clients.

Hallucination Rate and Executive Readiness

The measured hallucination rate is 0%. Every unanswerable question returned a clean refusal. The system did not attempt to generate numbers for future forecasts, real-time data, or information outside the filing corpus.

I would not put this dashboard in front of an executive yet. The refusal behavior is too aggressive on answerable questions. Three questions that have clear answers in the filing returned INSUFFICIENT_DATA responses because retrieval surfaced narrative chunks rather than the financial table rows containing the actual numbers. An executive asking about debt position or cash flow and getting a refusal would stop trusting the tool quickly.

The fix is chunk size reduction. At 1200 characters, chunks capture too much surrounding narrative. Cutting to 700 characters and raising retrieval k to 10 would improve precision on line-item lookups. That is the first change I would make.

 Most Interesting Insight

Eli Lilly's gross margin is 83%. Pfizer's is 13.1%. Both companies reported roughly $62 to 65 billion in revenue for the same fiscal year.

Lilly retains 83 cents of every revenue dollar after cost of goods. Pfizer retains 13 cents. The gap comes from product mix. Lilly's revenue increasingly concentrates in Mounjaro and Zepbound, which carry high list prices and face limited competition. Pfizer runs a broader, more mature portfolio with heavier manufacturing exposure and more products facing generic and biosimilar pressure.

I am confident in these numbers. Both figures come from financial statement tables in the respective 10-Ks, not from narrative sections. The RAG chat independently confirmed both with citations to the income statement. The margin gap is large enough that extraction noise does not change the conclusion.

 Failure Found and Diagnosed

The metrics extractor initially returned a revenue figure of $6,801,591 million for Pfizer. The correct figure is $63,627 million, so the extraction was off by a factor of roughly 100.

Two problems combined to produce this. First, the income statement HTML table had no year labels in its column headers. Columns were numbered 1, 2, 3 rather than labeled 2025, 2024, 2023. The extractor stored values using the column index as the year key. Second, the label matching used substring search, so "revenues" matched a Biopharma segment subtable row (Biopharma revenues: approximately $6.8 billion) before it reached the consolidated total revenues row ($63.6 billion). The extractor grabbed the first match.

I fixed label matching to require the cell text to start with the candidate string rather than contain it anywhere. That eliminated most spurious segment row matches. I also added column index remapping: when year keys look like column indices rather than actual years (max value below 100), the code remaps them to actual years counting back from the filing year in the filename.

A residual bug remains. Pfizer's R&D intensity shows as 0% in the comparison table because the remapped R&D rows and revenue rows end up with mismatched year keys and the ratio computation returns None. I know where the bug is and did not have time to fix it cleanly before submission.

How I Used AI Tools

I used Cursor throughout the project for scaffolding, debugging, and iterating on individual modules. I reviewed every file and made material changes to several.

The most significant override was in `metrics.py`. The AI-generated version used regex patterns on raw filing text to extract line items. I replaced the entire approach with HTML table extraction using BeautifulSoup. Regex on SEC filing text consistently finds the wrong number because the same label appears in footnotes and segment disclosures before the consolidated financial statements. Table-based extraction with strict row matching produces diagnosable errors: you can inspect which table row matched and why.

LangChain helped with retriever abstraction. Wiring cross-company retrieval as a dict of Chroma stores required few code changes. Where I dropped to direct API calls was ChromaDB client management. The LangChain Chroma wrapper threw a readonly database error when Streamlit and the terminal both held references to the same collection simultaneously. Switching to `chromadb.PersistentClient` directly and passing it into the Chroma wrapper resolved the lock conflict. The LangChain abstraction was not transparent enough about the underlying client behavior to debug through it.

What I Did Not Complete

Multi-year indexing is the largest gap. The downloader includes a `download_for_year()` function that fetches a filing for a specific year. I only indexed the most recent 10-K per company rather than three years each. Revenue trend charts show multi-year data because each 10-K contains a three-year comparative income statement, so the data comes from a single filing rather than from separate indexed documents.

Restatement and conflict detection is the other gap. J&J's Kenvue spinoff in 2023 means pre-spinoff and post-spinoff revenue figures are not directly comparable. The system does not flag this. Surfacing that kind of inconsistency would require cross-filing comparison logic that I did not build.
