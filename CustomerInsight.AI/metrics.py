"""Financial metric extraction and ratio computation for pharma 10-K filings."""
from __future__ import annotations
import re
from typing import Any
import pandas as pd


# ------------------------------------------------------------------
# Unit normalization — pharma filings report in millions
# ------------------------------------------------------------------
def _normalize_to_millions(value: float, unit_hint: str) -> float:
    """Convert extracted number to millions based on filing unit hint."""
    hint = unit_hint.lower()
    if "billion" in hint:
        return value * 1000
    if "thousand" in hint:
        return value / 1000
    # Default: already in millions (standard for large pharma 10-Ks)
    return value


def _parse_number(value: str) -> float | None:
    """Parse dollar amounts including parenthetical negatives and commas."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text in ("—", "-", "n/a", "na", "", "—"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^\d.]", "", text)
    if not text:
        return None
    try:
        num = float(text)
        return -num if negative else num
    except ValueError:
        return None


# ------------------------------------------------------------------
# Table-based extraction (preferred — much more accurate than regex)
# ------------------------------------------------------------------
_INCOME_STMT_KEYS = {
    "revenue": [
        "total revenues", "total revenue", "revenues", "revenue",
        "net revenues", "net sales", "total net revenues", "sales",
        "sales to customers",
    ],
    "cost_of_goods": [
        "cost of sales", "cost of goods sold", "cost of products sold",
        "cost of revenues", "manufacturing and other"
    ],
    "gross_profit": ["gross profit", "gross margin"],
    "rd_expense": [
        "research and development", "research & development",
        "r&d expenses", "research and development expenses"
    ],
    "operating_income": [
        "income from operations", "operating income",
        "earnings from operations", "operating earnings"
    ],
    "net_income": [
        "net income", "net earnings", "net income attributable",
        "net earnings attributable", "net income (loss)"
    ],
    "ebit": ["earnings before interest and taxes", "ebit"],
}

_BALANCE_SHEET_KEYS = {
    "cash": [
        "cash and cash equivalents",
        "cash, cash equivalents and short-term investments",
        "cash and short-term investments"
    ],
    "current_assets": ["total current assets"],
    "total_assets": ["total assets"],
    "current_liabilities": ["total current liabilities"],
    "long_term_debt": [
        "long-term debt", "long-term debt, net",
        "notes payable and long-term debt"
    ],
    "total_liabilities": ["total liabilities"],
    "shareholders_equity": [
        "total equity", "total stockholders' equity",
        "total shareholders' equity", "total equity attributable"
    ],
}

_CASHFLOW_KEYS = {
    "operating_cash_flow": [
        "net cash provided by operating activities",
        "cash flows from operating activities",
        "net cash from operating activities"
    ],
    "capex": [
        "capital expenditures", "purchases of property, plant and equipment",
        "acquisition of property, plant and equipment",
        "capital expenditures for property, plant and equipment"
    ],
}


def _match_label(cell: str, candidates: list[str]) -> bool:
    cell_clean = cell.strip().lower().rstrip(":").strip()
    # Exact match only (longest candidates first) — avoids
    # "total revenues increase" matching "total revenues"
    for c in sorted(candidates, key=len, reverse=True):
        if cell_clean == c:
            return True
    return False


def _extract_from_tables(
    tables: list[dict[str, Any]],
    key_map: dict[str, list[str]],
) -> dict[str, dict[int, float]]:
    """
    Extract line items from parsed tables.
    Returns {metric: {year_col_index: value}} for multi-year data.
    """
    results: dict[str, dict[int, float]] = {k: {} for k in key_map}

    for table in tables:
        headers = [str(h).strip().lower() for h in table.get("headers", [])]
        rows = table.get("rows", [])
        if not headers or not rows:
            continue

        # Detect year columns (headers containing 4-digit years)
        year_cols: dict[int, int] = {}
        for col_idx, h in enumerate(headers):
            yr_match = re.search(r"(20\d{2})", h)
            if yr_match:
                year_cols[col_idx] = int(yr_match.group(1))

        for row in rows:
            if not row:
                continue
            label = str(row[0]).strip().lower() if row else ""
            for metric, candidates in key_map.items():
                if not _match_label(label, candidates):
                    continue
                for col_idx in range(1, len(row)):
                    val = _parse_number(str(row[col_idx]))
                    if val is None or val == 0:
                        continue
                    year = year_cols.get(col_idx, col_idx)
                    existing = results[metric].get(year)
                    if existing is None or (
                        metric in ("revenue", "net_income", "total_assets")
                        and abs(val) > abs(existing)
                    ):
                        results[metric][year] = val

    return results


def extract_all_line_items(
    parsed: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Master extraction: combines table-based and text-fallback extraction.
    Returns structured dict with values by year and source tracking.
    """
    tables = parsed.get("tables", [])
    filing_stem = parsed.get("source", "")

    # Try to infer year from filename (e.g. PFE_10-K_2023.htm)
    yr_match = re.search(r"(20\d{2})", filing_stem)
    filing_year = int(yr_match.group(1)) if yr_match else None

    income = _extract_from_tables(tables, _INCOME_STMT_KEYS)
    balance = _extract_from_tables(tables, _BALANCE_SHEET_KEYS)
    cashflow = _extract_from_tables(tables, _CASHFLOW_KEYS)

    all_items = {**income, **balance, **cashflow}

    # Flatten: if multi-year, keep all; otherwise key by filing_year
    flat: dict[str, Any] = {}
    for metric, year_vals in all_items.items():
        if year_vals:
            flat[metric] = year_vals  # {year: value}
        else:
            flat[metric] = {}

    return {
        "ticker": parsed.get("ticker", ""),
        "filing_year": filing_year,
        "source": filing_stem,
        "line_items": flat,  # {metric: {year: value_in_millions}}
    }


# ------------------------------------------------------------------
# Ratio computation (from extracted line items for a single year)
# ------------------------------------------------------------------
def _get_year_val(
    line_items: dict[str, dict[int, float]],
    metric: str,
    year: int | None,
) -> float | None:
    vals = line_items.get(metric, {})
    if not vals:
        return None
    if year and year in vals:
        return vals[year]
    # Fallback: most recent year available
    return vals.get(max(vals.keys()))


def compute_ratios(
    line_items: dict[str, dict[int, float]],
    year: int | None = None,
) -> dict[str, float | None]:
    def g(metric: str) -> float | None:
        return _get_year_val(line_items, metric, year)

    revenue = g("revenue")
    cogs = g("cost_of_goods")
    gross = g("gross_profit") or ((revenue - cogs) if revenue and cogs else None)
    op_income = g("operating_income")
    net_income = g("net_income")
    assets = g("total_assets")
    equity = g("shareholders_equity")
    liabilities = g("total_liabilities")
    current_assets = g("current_assets")
    current_liabilities = g("current_liabilities")
    cash = g("cash")
    rd = g("rd_expense")
    ocf = g("operating_cash_flow")
    capex = g("capex")

    def div(a: float | None, b: float | None) -> float | None:
        if a is None or b is None or b == 0:
            return None
        return a / b

    fcf = (ocf - abs(capex)) if ocf is not None and capex is not None else None

    return {
        "gross_margin": div(gross, revenue),
        "operating_margin": div(op_income, revenue),
        "net_profit_margin": div(net_income, revenue),
        "rd_intensity": div(rd, revenue),          # R&D as % revenue — key pharma metric
        "return_on_assets": div(net_income, assets),
        "return_on_equity": div(net_income, equity),
        "debt_to_equity": div(liabilities, equity),
        "current_ratio": div(current_assets, current_liabilities),
        "fcf_millions": fcf,                        # Free cash flow in $M
        "asset_turnover": div(revenue, assets),
    }


def ratios_from_parsed(parsed: dict[str, Any]) -> dict[str, Any]:
    extracted = extract_all_line_items(parsed)
    filing_year = extracted.get("filing_year")
    line_items = extracted["line_items"]

    # Column indices (1,2,3) → fiscal years when headers lack year labels
    for metric, year_vals in line_items.items():
        keys = sorted(year_vals.keys())
        if keys and max(keys) < 100:
            if filing_year:
                remapped = {}
                for i, k in enumerate(keys):
                    remapped[filing_year - i] = year_vals[k]
                line_items[metric] = remapped

    # Sanity filter: pharma revenue-scale line items must be > $500M
    for metric in ["revenue", "net_income", "total_assets"]:
        if metric in line_items:
            line_items[metric] = {
                yr: val
                for yr, val in line_items[metric].items()
                if val is None or abs(val) > 500
            }

    ratios = compute_ratios(line_items, filing_year)
    return {
        "ticker": extracted["ticker"],
        "filing_year": filing_year,
        "line_items": line_items,
        "ratios": ratios,
    }


def build_comparison_df(
    all_results: list[dict[str, Any]],
    metric: str,
) -> pd.DataFrame:
    """
    Build a DataFrame of metric values by ticker and year for charting.
    all_results: list of ratios_from_parsed() outputs across all companies/years.
    """
    rows = []
    for r in all_results:
        ticker = r["ticker"]
        line_items = r.get("line_items", {})
        vals = line_items.get(metric, {})
        for year, val in vals.items():
            rows.append({"ticker": ticker, "year": year, "value": val})
    return pd.DataFrame(rows)


def format_ratio(value: float | None, as_percent: bool = False) -> str:
    if value is None:
        return "N/A"
    if as_percent:
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"
