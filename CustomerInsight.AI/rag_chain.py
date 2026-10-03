"""LangChain RAG — query rewriting, cross-company retrieval, refusal logic."""
from __future__ import annotations
from typing import Any
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
# from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

import config

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You rewrite user questions about pharma SEC 10-K filings into short, "
     "natural keyword search queries. Output ONLY the query, no SQL, no explanation. "
     "Example: 'research and development expenses Pfizer Eli Lilly 2024 2025'"),
    ("human", "Original: {question}\n\nRewritten query:"),
])

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """You are a financial analyst assistant for pharma companies (Pfizer, Eli Lilly, \
AbbVie, Johnson & Johnson). Answer using ONLY the provided filing context.

Rules:
1. If the context does not contain enough information to answer, respond EXACTLY with:
   "INSUFFICIENT_DATA: [brief reason why]"
2. If figures appear in multiple filings with different values for the same period, \
flag it: "NOTE: Conflicting figures found — [details]"
3. Always cite sources as [1], [2] etc. matching the context list.
4. For any number you state, mention the unit (millions, billions, %).
5. Never invent or estimate figures not present in the context."""),
    ("human", "Context:\n{context}\n\n---\nQuestion: {question}\n\nAnswer:"),
])



def _get_llm():
    if not config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set.")
    return ChatGroq(
        model=config.LLM_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=0,
    )

def rewrite_query(question: str) -> str:
    chain = REWRITE_PROMPT | _get_llm() | StrOutputParser()
    return chain.invoke({"question": question}).strip()


def _format_docs(docs: list[Any]) -> tuple[str, list[dict]]:
    parts, citations = [], []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        ticker = meta.get("ticker", "?")
        year = meta.get("filing_year", meta.get("year", ""))
        page = meta.get("page", "")
        doc_type = meta.get("type", "text")
        label = f"[{i}] {ticker} {year} {doc_type}" + (f" p.{page}" if page else "")
        parts.append(f"{label}\n{doc.page_content[:2000]}")
        citations.append({
            "index": i, "ticker": ticker, "year": year,
            "page": page, "type": doc_type,
            "source": meta.get("source", ""),
            "snippet": doc.page_content[:300],
        })
    return "\n\n".join(parts), citations


def ask(
    vectorstores: dict[str, Chroma] | Chroma,
    question: str,
) -> dict[str, Any]:
    """
    Run RAG query. Accepts either a single Chroma store or a dict of
    {ticker: Chroma} for cross-company queries.
    """
    llm = _get_llm()
    rewritten = rewrite_query(question)

    all_docs = []
    if isinstance(vectorstores, dict):
        k_per_store = max(2, config.TOP_K_RETRIEVAL // len(vectorstores))
        for ticker, vs in vectorstores.items():
            try:
                docs = vs.similarity_search(rewritten, k=k_per_store)
                for doc in docs:
                    meta = doc.metadata or {}
                    doc.metadata = {**meta, "ticker": meta.get("ticker", ticker)}
                all_docs.extend(docs)
                print(f"  {ticker}: {len(docs)} chunks retrieved")
            except Exception as e:
                print(f"  {ticker}: retrieval failed — {e}")
    else:
        all_docs = vectorstores.similarity_search(rewritten, k=config.TOP_K_RETRIEVAL)

    if not all_docs:
        return {
            "answer": "INSUFFICIENT_DATA: No relevant context found in any indexed filing.",
            "rewritten_query": rewritten,
            "citations": [],
            "retrieved_count": 0,
            "refused": True,
        }

    context, citations = _format_docs(all_docs)
    answer = (RAG_PROMPT | llm | StrOutputParser()).invoke(
        {"context": context, "question": question}
    )

    refused = answer.strip().startswith("INSUFFICIENT_DATA")
    return {
        "answer": answer,
        "rewritten_query": rewritten,
        "citations": citations,
        "retrieved_count": len(all_docs),
        "refused": refused,
    }
