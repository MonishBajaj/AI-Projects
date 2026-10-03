"""
Evaluation framework for the pharma RAG pipeline.
Measures answer correctness, citation accuracy, and hallucination rate.
Run: python eval.py
Results saved to data/eval_results.json and printed to stdout.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
import config
import embedder
import rag_chain

# ------------------------------------------------------------------
# Labeled evaluation dataset
# Questions are grouped into three categories:
#   answerable   — ground truth known, system should answer correctly
#   unanswerable — not in filings, system must refuse (INSUFFICIENT_DATA)
#   comparative  — cross-company, tests multi-store retrieval
# ------------------------------------------------------------------
EVAL_QUESTIONS: list[dict[str, Any]] = [

    # ── ANSWERABLE (factual, verifiable against PFE 2025 10-K) ────
    {
        "id": "A01",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What was Pfizer's total revenue for fiscal year 2024?",
        "ground_truth_contains": ["58", "59", "billion", "million"],
        "notes": "PFE FY2024 revenue ~$58-59B; accept any figure in that range",
    },
    {
        "id": "A02",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What was Pfizer's net income in fiscal year 2024?",
        "ground_truth_contains": ["net income", "earnings", "billion", "million"],
        "notes": "Should cite income statement",
    },
    {
        "id": "A03",
        "category": "answerable",
        "ticker": "PFE",
        "question": "How much did Pfizer spend on research and development in 2024?",
        "ground_truth_contains": ["research", "development", "billion", "million"],
        "notes": "R&D expense should be cited from income statement",
    },
    {
        "id": "A04",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What does Pfizer management say about the decline in Comirnaty revenue?",
        "ground_truth_contains": ["comirnaty", "covid", "vaccine", "revenue"],
        "notes": "MD&A section discusses COVID vaccine revenue decline",
    },
    {
        "id": "A05",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What are the primary risk factors Pfizer discloses related to patent expiries?",
        "ground_truth_contains": ["patent", "expir", "exclusiv", "biosimilar"],
        "notes": "Risk factors section",
    },
    {
        "id": "A06",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What was Pfizer's total debt as of the end of fiscal year 2024?",
        "ground_truth_contains": ["debt", "billion", "million", "borrowing"],
        "notes": "Balance sheet line item",
    },
    {
        "id": "A07",
        "category": "answerable",
        "ticker": "PFE",
        "question": "What was Pfizer's operating cash flow in 2024?",
        "ground_truth_contains": ["operating", "cash", "billion", "million"],
        "notes": "Cash flow statement",
    },

    # ── UNANSWERABLE (must trigger INSUFFICIENT_DATA refusal) ─────
    {
        "id": "U01",
        "category": "unanswerable",
        "ticker": "PFE",
        "question": "What will Pfizer's revenue be in fiscal year 2027?",
        "ground_truth_contains": ["INSUFFICIENT_DATA"],
        "notes": "Future forecast not in filings — must refuse",
    },
    {
        "id": "U02",
        "category": "unanswerable",
        "ticker": "PFE",
        "question": "How many employees does Pfizer plan to hire in the next quarter?",
        "ground_truth_contains": ["INSUFFICIENT_DATA"],
        "notes": "Forward-looking hiring plans not disclosed — must refuse",
    },
    {
        "id": "U03",
        "category": "unanswerable",
        "ticker": "PFE",
        "question": "What is Pfizer's current stock price?",
        "ground_truth_contains": ["INSUFFICIENT_DATA"],
        "notes": "Real-time market data not in filings — must refuse",
    },
    {
        "id": "U04",
        "category": "unanswerable",
        "ticker": "PFE",
        "question": "What did Pfizer's CEO say in the Q3 2019 earnings call?",
        "ground_truth_contains": ["INSUFFICIENT_DATA"],
        "notes": "Earnings call transcripts not in 10-K — must refuse",
    },

    # ── COMPARATIVE (cross-company, requires multi-store RAG) ─────
    {
        "id": "C01",
        "category": "comparative",
        "ticker": "ALL",
        "question": "Which company had the highest R&D spending as a percentage of revenue among Pfizer, Lilly, AbbVie, and J&J?",
        "ground_truth_contains": ["lilly", "pfizer", "abbvie", "johnson", "r&d", "%"],
        "notes": "Requires cross-company retrieval; Lilly typically highest R&D intensity",
    },
    {
        "id": "C02",
        "category": "comparative",
        "ticker": "ALL",
        "question": "How does Pfizer's revenue trend compare to Eli Lilly's over the past two years?",
        "ground_truth_contains": ["pfizer", "lilly", "revenue", "growth", "decline"],
        "notes": "PFE declining post-COVID, LLY growing from GLP-1 drugs",
    },
]


# ------------------------------------------------------------------
# LLM-based answer grader
# ------------------------------------------------------------------
GRADE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are evaluating a RAG system answer against expected keywords. "
     'Respond with JSON only: {{"correct": true/false, "reason": "brief explanation"}}. '
     "Mark correct=true if the answer addresses the question and contains the key concepts. "
     "For INSUFFICIENT_DATA questions, correct=true only if the answer starts with INSUFFICIENT_DATA."),
    ("human",
     "Question: {question}\n"
     "Expected keywords: {keywords}\n"
     "System answer: {answer}\n\n"
     "Grade (JSON only):"),
])


def grade_answer(
    question: str,
    expected_keywords: list[str],
    system_answer: str,
    llm: ChatGroq,
) -> dict[str, Any]:
    chain = GRADE_PROMPT | llm | StrOutputParser()
    raw = chain.invoke({
        "question": question,
        "keywords": ", ".join(expected_keywords),
        "answer": system_answer[:1000],
    })
    try:
        raw_clean = raw.strip().replace("```json", "").replace("```", "")
        return json.loads(raw_clean)
    except Exception:
        # Fallback: keyword check
        answer_lower = system_answer.lower()
        hits = sum(1 for k in expected_keywords if k.lower() in answer_lower)
        return {
            "correct": hits >= len(expected_keywords) // 2,
            "reason": f"Keyword fallback: {hits}/{len(expected_keywords)} matched",
        }


# ------------------------------------------------------------------
# Main evaluation runner
# ------------------------------------------------------------------
def run_evaluation(
    vectorstores: dict[str, Any],
    questions: list[dict] | None = None,
    save_path: str = "data/eval_results.json",
) -> dict[str, Any]:
    questions = questions or EVAL_QUESTIONS
    llm = ChatGroq(
        model=config.LLM_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=0,
    )

    results = []
    print(f"\n{'='*60}")
    print(f"Running evaluation: {len(questions)} questions")
    print(f"{'='*60}\n")

    for q in questions:
        qid = q["id"]
        category = q["category"]
        question = q["question"]
        ticker = q["ticker"]
        print(f"[{qid}] {category.upper()} — {question[:60]}...")

        # Select vectorstore(s)
        if ticker == "ALL":
            vs_input = vectorstores
        elif ticker in vectorstores:
            vs_input = {ticker: vectorstores[ticker]}
        else:
            print(f"  ⚠ No index for {ticker}, skipping")
            continue

        try:
            t0 = time.time()
            response = rag_chain.ask(vs_input, question)
            elapsed = round(time.time() - t0, 2)
            answer = response["answer"]
            refused = response.get("refused", False)
            citations = response.get("citations", [])
        except Exception as exc:
            answer = f"ERROR: {exc}"
            elapsed = 0
            refused = False
            citations = []

        # Grade
        grade = grade_answer(question, q["ground_truth_contains"], answer, llm)
        correct = grade.get("correct", False)

        result = {
            "id": qid,
            "category": category,
            "ticker": ticker,
            "question": question,
            "answer": answer[:500],
            "correct": correct,
            "refused": refused,
            "citation_count": len(citations),
            "latency_s": elapsed,
            "grade_reason": grade.get("reason", ""),
            "notes": q.get("notes", ""),
        }
        results.append(result)

        status = "✓" if correct else "✗"
        print(f"  {status} correct={correct} | refused={refused} | "
              f"citations={len(citations)} | {elapsed}s")
        print(f"  Reason: {grade.get('reason', '')}")
        time.sleep(0.5)  # rate limit

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------
    answerable = [r for r in results if r["category"] == "answerable"]
    unanswerable = [r for r in results if r["category"] == "unanswerable"]
    comparative = [r for r in results if r["category"] == "comparative"]

    def pct(subset: list, key: str = "correct") -> str:
        if not subset:
            return "N/A"
        return f"{sum(r[key] for r in subset) / len(subset) * 100:.0f}%"

    # Hallucination rate = unanswerable questions where system did NOT refuse
    hallucinations = [r for r in unanswerable if not r["refused"]]
    hallucination_rate = (
        len(hallucinations) / len(unanswerable) * 100 if unanswerable else 0
    )

    summary = {
        "total_questions": len(results),
        "overall_correctness": pct(results),
        "answerable_correctness": pct(answerable),
        "unanswerable_refusal_rate": pct(unanswerable, "refused"),
        "hallucination_rate_pct": round(hallucination_rate, 1),
        "comparative_correctness": pct(comparative),
        "avg_citations": round(
            sum(r["citation_count"] for r in results) / len(results), 1
        ) if results else 0,
        "avg_latency_s": round(
            sum(r["latency_s"] for r in results) / len(results), 1
        ) if results else 0,
        "hallucinated_questions": [r["id"] for r in hallucinations],
    }

    output = {"summary": summary, "results": results}

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_text(json.dumps(output, indent=2))

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nFull results saved to {save_path}")

    return output


if __name__ == "__main__":
    print("Loading vector indexes...")
    stores = embedder.load_all_vectorstores()
    if not stores:
        print("ERROR: No indexed filings found. Run the pipeline first.")
        print("Index at least PFE before running eval.")
        exit(1)

    print(f"Loaded indexes: {list(stores.keys())}")
    run_evaluation(stores)