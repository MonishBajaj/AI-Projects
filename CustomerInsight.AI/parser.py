"""PDF and HTML table + text extraction using pdfplumber."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pdfplumber

import config


def _sanitize_for_json(text: str) -> str:
    """Remove control characters that break JSON serialization."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_tables_from_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """Extract all tables from a PDF with page numbers."""
    tables: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for table_idx, raw_table in enumerate(page.extract_tables() or []):
                if not raw_table:
                    continue
                cleaned = [
                    [_clean_cell(c) for c in row]
                    for row in raw_table
                    if any(_clean_cell(c) for c in row)
                ]
                if len(cleaned) < 2:
                    continue
                tables.append(
                    {
                        "page": page_num,
                        "table_index": table_idx,
                        "headers": cleaned[0],
                        "rows": cleaned[1:],
                        "row_count": len(cleaned) - 1,
                    }
                )
    return tables


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Concatenate text from all PDF pages."""
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = re.sub(r"\n{3,}", "\n\n", text.strip())
            if text:
                chunks.append(f"[Page {page_num}]\n{text}")
    return "\n\n".join(chunks)


def _strip_html_tags(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_tables_from_html(html_path: Path) -> list[dict[str, Any]]:
    """Extract financial tables from SEC HTML filings using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    tables = []

    for table_idx, table_tag in enumerate(soup.find_all("table")):
        rows_data = []
        for tr in table_tag.find_all("tr"):
            cells = [td.get_text(separator=" ", strip=True)
                     for td in tr.find_all(["td", "th"])]
            if any(c for c in cells):
                rows_data.append(cells)

        if len(rows_data) < 2:
            continue
        # Skip tiny tables (navigation/headers)
        if max(len(r) for r in rows_data) < 2:
            continue

        tables.append({
            "page": 1,  # HTML has no pages
            "table_index": table_idx,
            "headers": rows_data[0],
            "rows": rows_data[1:],
            "row_count": len(rows_data) - 1,
        })

    return tables


def extract_text_from_html(html_path: Path) -> str:
    """Extract readable text from SEC HTML, preserving structure."""
    try:
        from bs4 import BeautifulSoup
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()
    except ImportError:
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        return _strip_html_tags(raw)


def table_to_markdown(table: dict[str, Any]) -> str:
    """Render a parsed table as markdown for embedding."""
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    if not headers:
        return ""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows[:50]:
        padded = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
    if len(rows) > 50:
        lines.append(f"\n*({len(rows) - 50} additional rows omitted)*")
    return "\n".join(lines)


def parse_filing(filing_path: Path) -> dict[str, Any]:
    """
    Parse a filing (PDF or HTML) into text, tables, and combined documents.
    Persists JSON to data/parsed/{ticker}/.
    """
    suffix = filing_path.suffix.lower()
    ticker = filing_path.parent.name.upper()

    if suffix == ".pdf":
        full_text = extract_text_from_pdf(filing_path)
        tables = extract_tables_from_pdf(filing_path)
    elif suffix in (".htm", ".html"):
        full_text = extract_text_from_html(filing_path)
        tables = extract_tables_from_html(filing_path)
    else:
        raise ValueError(f"Unsupported filing format: {suffix}")

    full_text = _sanitize_for_json(full_text)

    table_docs = []
    for i, table in enumerate(tables):
        md = table_to_markdown(table)
        if md:
            table_docs.append(
                {
                    "id": f"table_{i}",
                    "page": table["page"],
                    "content": _sanitize_for_json(
                        f"Financial table (page {table['page']}):\n{md}"
                    ),
                }
            )

    result = {
        "ticker": ticker,
        "source": str(filing_path),
        "text_length": len(full_text),
        "table_count": len(tables),
        "full_text": full_text,
        "tables": tables,
        "documents": table_docs,
    }

    out_dir = config.PARSED_DIR / ticker
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{filing_path.stem}_parsed.json"
    out_file.write_text(json.dumps(result, indent=2))
    return result


def load_parsed(ticker: str) -> dict[str, Any] | None:
    """Load the most recent parsed JSON for a ticker."""
    parsed_dir = config.PARSED_DIR / ticker.upper()
    if not parsed_dir.exists():
        return None
    files = sorted(parsed_dir.glob("*_parsed.json"), reverse=True)
    if not files:
        return None
    for f in files:
        try:
            return json.loads(f.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            f.unlink()
            continue
    return None
