"""SEC EDGAR filing fetcher."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

import config

_HEADERS = {
    "User-Agent": config.SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}


def _request(url: str, *, delay: float = 0.15) -> requests.Response:
    """Rate-limited GET respecting SEC fair-access policy."""
    time.sleep(delay)
    response = requests.get(url, headers=_HEADERS, timeout=60)
    response.raise_for_status()
    return response


def get_cik(ticker: str) -> str:
    """Resolve ticker to zero-padded 10-digit CIK."""
    ticker = ticker.upper()
    if ticker in config.COMPANY_TICKERS:
        return config.COMPANY_TICKERS[ticker]["cik"]
    url = f"{config.SEC_DATA_URL}/submissions/CIK{ticker.zfill(10)}.json"
    try:
        data = _request(url).json()
        return str(data["cik"]).zfill(10)
    except requests.HTTPError:
        raise ValueError(f"Unknown ticker: {ticker}")


def list_filings(
    ticker: str,
    form_type: str = config.DEFAULT_FILING_TYPE,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return recent filings metadata for a ticker."""
    cik = get_cik(ticker)
    url = f"{config.SEC_DATA_URL}/submissions/CIK{cik}.json"
    data = _request(url).json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    filings: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form != form_type:
            continue
        accession = accessions[i].replace("-", "")
        filings.append(
            {
                "ticker": ticker.upper(),
                "cik": cik,
                "form": form,
                "filing_date": dates[i],
                "accession": accessions[i],
                "accession_clean": accession,
                "primary_document": primary_docs[i],
            }
        )
        if len(filings) >= limit:
            break
    return filings


def _filing_index_url(cik: str, accession_clean: str) -> str:
    cik_int = str(int(cik))
    return f"{config.SEC_BASE_URL}/Archives/edgar/data/{cik_int}/{accession_clean}/"


def find_pdf_url(cik: str, accession_clean: str) -> str | None:
    """Locate primary PDF in filing index, if present."""
    index_url = _filing_index_url(cik, accession_clean) + "index.json"
    try:
        index = _request(index_url).json()
    except requests.HTTPError:
        return None

    for item in index.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.lower().endswith(".pdf"):
            return _filing_index_url(cik, accession_clean) + name
    return None


def download_filing(
    ticker: str,
    form_type: str = config.DEFAULT_FILING_TYPE,
    filing_index: int = 0,
) -> Path:
    """
    Download the most recent (or indexed) filing for a ticker.
    Saves HTML or PDF under data/filings/{ticker}/.
    """
    filings = list_filings(ticker, form_type=form_type, limit=filing_index + 1)
    if not filings:
        raise FileNotFoundError(f"No {form_type} filings found for {ticker}")

    filing = filings[filing_index]
    cik = filing["cik"]
    accession_clean = filing["accession_clean"]
    primary = filing["primary_document"]

    out_dir = config.FILINGS_DIR / ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_url = _filing_index_url(cik, accession_clean)
    pdf_url = find_pdf_url(cik, accession_clean)

    if pdf_url:
        ext, url = ".pdf", pdf_url
    else:
        ext, url = Path(primary).suffix or ".htm", base_url + primary

    filename = f"{filing['form']}_{filing['filing_date']}{ext}"
    out_path = out_dir / filename

    if out_path.exists():
        return out_path

    content = _request(url).content
    out_path.write_bytes(content)

    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(filing, indent=2))
    return out_path


def download_all_tickers(
    form_type: str = config.DEFAULT_FILING_TYPE,
) -> dict[str, Path | str]:
    """Download latest filing for every configured ticker."""
    results: dict[str, Path | str] = {}
    for ticker in config.COMPANY_TICKERS:
        try:
            results[ticker] = download_filing(ticker, form_type=form_type)
        except Exception as exc:
            results[ticker] = str(exc)
    return results
