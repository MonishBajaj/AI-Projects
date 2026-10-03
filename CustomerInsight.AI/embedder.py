"""Chunk parsed filing text and embed into ChromaDB."""

from __future__ import annotations

import re
import shutil
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

# Local persistent client only — never HttpClient / remote server
_CHROMA_SETTINGS = Settings(
    anonymized_telemetry=False,
    allow_reset=True,
    is_persistent=True,
)


def _get_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _chroma_persist_dir(ticker: str) -> str:
    return str(config.CHROMA_DIR / ticker.upper())


def _chroma_client(ticker: str) -> chromadb.PersistentClient:
    """Persistent local Chroma client (HttpClient=False)."""
    return chromadb.PersistentClient(
        path=_chroma_persist_dir(ticker),
        settings=_CHROMA_SETTINGS,
    )


def _chroma_store(
    ticker: str,
    *,
    embedding_function=None,
) -> Chroma:
    """Create LangChain Chroma wrapper bound to a local PersistentClient."""
    return Chroma(
        client=_chroma_client(ticker),
        collection_name=_collection_name(ticker),
        embedding_function=embedding_function or _get_embeddings(),
        client_settings=_CHROMA_SETTINGS,
    )


def _collection_name(ticker: str) -> str:
    return f"filings_{ticker.upper()}"


def _filing_year_from_source(source: str) -> str:
    match = re.search(r"(20\d{2})", source)
    return match.group(1) if match else ""


def build_documents(parsed: dict[str, Any]) -> list[Document]:
    """Turn parsed filing into LangChain Documents with metadata."""
    ticker = parsed.get("ticker", "UNKNOWN")
    source = parsed.get("source", "")
    filing_year = _filing_year_from_source(source)
    base_meta = {"ticker": ticker, "source": source, "filing_year": filing_year}
    docs: list[Document] = []

    if parsed.get("full_text"):
        docs.append(
            Document(
                page_content=parsed["full_text"],
                metadata={**base_meta, "type": "full_text"},
            )
        )

    for table_doc in parsed.get("documents", []):
        docs.append(
            Document(
                page_content=table_doc["content"],
                metadata={
                    **base_meta,
                    "type": "table",
                    "page": table_doc.get("page"),
                    "id": table_doc.get("id"),
                },
            )
        )
    return docs


def load_all_vectorstores() -> dict[str, Chroma]:
    """Load every indexed ticker collection for cross-company RAG."""
    stores: dict[str, Chroma] = {}
    for ticker in config.COMPANY_TICKERS:
        vs = load_vectorstore(ticker)
        if vs:
            stores[ticker] = vs
    return stores


def chunk_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def embed_ticker(parsed: dict[str, Any], *, reset: bool = False) -> Chroma:
    """
    Chunk and embed parsed filing for a ticker into ChromaDB.
    Returns the vector store instance.
    """
    ticker = parsed.get("ticker", "").upper()
    if not ticker:
        raise ValueError("Parsed data must include a ticker.")

    if reset:
        path = config.CHROMA_DIR / ticker
        if path.exists():
            shutil.rmtree(path)

    raw_docs = build_documents(parsed)
    chunks = chunk_documents(raw_docs)
    if not chunks:
        raise ValueError(f"No content to embed for {ticker}.")

    embeddings = _get_embeddings()
    vectorstore = _chroma_store(ticker, embedding_function=embeddings)
    vectorstore.add_documents(chunks)
    return vectorstore


def load_vectorstore(ticker: str) -> Chroma | None:
    """Load existing Chroma collection for a ticker."""
    persist_dir = config.CHROMA_DIR / ticker.upper()
    if not persist_dir.exists():
        return None
    try:
        return _chroma_store(ticker)
    except Exception:
        return None


def is_indexed(ticker: str) -> bool:
    return (config.CHROMA_DIR / ticker.upper()).exists()
