"""Application configuration."""
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import os

DATA_DIR = BASE_DIR / "data"
FILINGS_DIR = DATA_DIR / "filings"
PARSED_DIR = DATA_DIR / "parsed"
CHROMA_DIR = DATA_DIR / "chroma"

for _dir in (DATA_DIR, FILINGS_DIR, PARSED_DIR, CHROMA_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "FinancialDashboard contact@example.com")
SEC_BASE_URL = "https://www.sec.gov"
SEC_DATA_URL = "https://data.sec.gov"

COMPANY_TICKERS: dict[str, dict[str, str]] = {
    "PFE":  {"name": "Pfizer Inc.",              "cik": "0000078003"},
    "LLY":  {"name": "Eli Lilly and Company",    "cik": "0000059478"},
    "ABBV": {"name": "AbbVie Inc.",              "cik": "0001551152"},
    "JNJ":  {"name": "Johnson & Johnson",        "cik": "0000200406"},
}

DEFAULT_TICKER = "PFE"
DEFAULT_FILING_TYPE = "10-K"
TARGET_YEARS = [2022, 2023, 2024]

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOP_K_RETRIEVAL = 6

# Units: pharma filings report in millions — we normalize everything to millions
REPORTING_UNIT = "millions"
