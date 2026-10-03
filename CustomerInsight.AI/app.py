"""Streamlit financial analysis dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
import downloader
import embedder
import metrics
import parser
import rag_chain

# config.py loads .env on import; refresh in case Streamlit hot-reloaded modules
config.GROQ_API_KEY = os.getenv("GROQ_API_KEY", config.GROQ_API_KEY)


st.set_page_config(
    page_title="Financial Analysis Dashboard",
    page_icon="📊",
    layout="wide",
)

RATIO_LABELS = {
    "gross_margin": ("Gross Margin", True),
    "operating_margin": ("Operating Margin", True),
    "net_profit_margin": ("Net Profit Margin", True),
    "rd_intensity": ("R&D Intensity", True),
    "return_on_assets": ("Return on Assets", True),
    "return_on_equity": ("Return on Equity", True),
    "debt_to_equity": ("Debt to Equity", False),
    "current_ratio": ("Current Ratio", False),
    "fcf_millions": ("Free Cash Flow ($M)", False),
    "asset_turnover": ("Asset Turnover", False),
}


_FILING_SUFFIXES = {".htm", ".html", ".pdf"}


def _is_filing_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in _FILING_SUFFIXES
        and ".meta." not in path.name
    )


def _list_filing_candidates(ticker: str) -> list[Path]:
    filings_dir = config.FILINGS_DIR / ticker.upper()
    if not filings_dir.exists():
        return []
    return sorted(
        (f for f in filings_dir.iterdir() if _is_filing_file(f)),
        reverse=True,
    )


def _resolve_filing_path(ticker: str, stored: Path | str | None) -> Path | None:
    if stored:
        path = Path(stored) if not isinstance(stored, Path) else stored
        if _is_filing_file(path) and path.exists():
            return path
    candidates = _list_filing_candidates(ticker)
    return candidates[0] if candidates else None


def init_session_state() -> None:
    defaults = {
        "parsed": None,
        "metrics_result": None,
        "vectorstore": None,
        "chat_history": [],
        "filing_path": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def sidebar_controls() -> tuple[str, str]:
    st.sidebar.header("Company & Filing")
    tickers = list(config.COMPANY_TICKERS.keys())
    ticker = st.sidebar.selectbox(
        "Ticker",
        tickers,
        index=tickers.index(config.DEFAULT_TICKER)
        if config.DEFAULT_TICKER in tickers
        else 0,
    )
    company_name = config.COMPANY_TICKERS[ticker]["name"]
    st.sidebar.caption(company_name)

    form_type = st.sidebar.selectbox("Filing type", ["10-K", "10-Q"], index=0)
    return ticker, form_type


def pipeline_section(ticker: str, form_type: str) -> None:
    st.subheader("Data pipeline")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Download filing", use_container_width=True):
            with st.spinner("Fetching from SEC EDGAR..."):
                try:
                    path = downloader.download_filing(ticker, form_type=form_type)
                    st.session_state.filing_path = str(path)
                    st.success(f"Saved: {path.name}")
                except Exception as exc:
                    st.error(str(exc))

    with col2:
        if st.button("Parse document", use_container_width=True):
            filing = _resolve_filing_path(ticker, st.session_state.filing_path)
            if filing:
                st.session_state.filing_path = str(filing)
            if not filing:
                st.warning("Download a filing first.")
            else:
                with st.spinner("Extracting text and tables..."):
                    try:
                        st.session_state.parsed = parser.parse_filing(filing)
                        st.session_state.metrics_result = metrics.ratios_from_parsed(
                            st.session_state.parsed
                        )
                        st.success(
                            f"Parsed {st.session_state.parsed['table_count']} tables, "
                            f"{st.session_state.parsed['text_length']:,} chars"
                        )
                    except Exception as exc:
                        st.error(str(exc))

    with col3:
        if st.button("Build embeddings", use_container_width=True):
            parsed = st.session_state.parsed or parser.load_parsed(ticker)
            if not parsed:
                st.warning("Parse a filing first.")
            else:
                with st.spinner("Embedding into ChromaDB..."):
                    try:
                        st.session_state.vectorstore = embedder.embed_ticker(
                            parsed, reset=True
                        )
                        st.success("Vector index ready.")
                    except Exception as exc:
                        st.error(str(exc))

    with col4:
        if st.button("Load cached index", use_container_width=True):
            vs = embedder.load_vectorstore(ticker)
            if vs:
                st.session_state.vectorstore = vs
                st.success("Loaded existing index.")
            else:
                st.warning("No index found. Build embeddings first.")


def metrics_dashboard() -> None:
    st.subheader("Financial metrics")
    result = st.session_state.metrics_result
    if not result:
        parsed = st.session_state.parsed
        if parsed:
            result = metrics.ratios_from_parsed(parsed)
        else:
            loaded = parser.load_parsed(st.session_state.get("_ticker", ""))
            if loaded:
                result = metrics.ratios_from_parsed(loaded)

    if not result:
        st.info("Run **Parse document** to compute ratios from filing text.")
        return

    line_items = result.get("line_items", {})
    ratios = result.get("ratios", {})
    filing_year = result.get("filing_year")
    if filing_year:
        st.caption(f"Filing year: {filing_year} · values in $M ({config.REPORTING_UNIT})")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Extracted line items (table-based)**")
        rows = []
        for metric, year_vals in line_items.items():
            if isinstance(year_vals, dict) and year_vals:
                for year, val in sorted(year_vals.items()):
                    rows.append({
                        "Metric": metric.replace("_", " ").title(),
                        "Year": year,
                        "Value ($M)": f"{val:,.1f}",
                    })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("No line items matched — parse HTML tables or try another filing.")

    with col_b:
        st.markdown("**Financial ratios**")
        ratio_rows = []
        for key, (label, as_pct) in RATIO_LABELS.items():
            val = ratios.get(key)
            if key == "fcf_millions" and val is not None:
                formatted = f"${val:,.1f}M"
            else:
                formatted = metrics.format_ratio(val, as_pct)
            ratio_rows.append({"Ratio": label, "Value": formatted})
        st.dataframe(pd.DataFrame(ratio_rows), hide_index=True, use_container_width=True)

    ratio_vals = {RATIO_LABELS[k][0]: ratios.get(k) for k in RATIO_LABELS if ratios.get(k) is not None}
    if ratio_vals:
        fig = go.Figure(
            data=[
                go.Bar(
                    x=list(ratio_vals.keys()),
                    y=list(ratio_vals.values()),
                    marker_color="#2563eb",
                )
            ]
        )
        fig.update_layout(
            title="Ratio overview",
            yaxis_title="Value",
            height=400,
            margin=dict(l=20, r=20, t=40, b=80),
        )
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

    pct_ratios = {
        RATIO_LABELS[k][0]: ratios[k]
        for k in RATIO_LABELS
        if RATIO_LABELS[k][1] and ratios.get(k) is not None
    }
    if pct_ratios:
        fig_pie = px.pie(
            names=list(pct_ratios.keys()),
            values=[abs(v) for v in pct_ratios.values()],
            title="Margin & return metrics (absolute share)",
        )
        st.plotly_chart(fig_pie, use_container_width=True)


def comparison_section() -> None:
    st.subheader("Cross-Company Pharma Comparison")
    st.caption("All values in $M. Data extracted from most recent 10-K per company.")

    all_results = []
    for ticker in config.COMPANY_TICKERS:
        parsed = parser.load_parsed(ticker)
        if parsed:
            result = metrics.ratios_from_parsed(parsed)
            result["company"] = config.COMPANY_TICKERS[ticker]["name"]
            all_results.append(result)

    if not all_results:
        st.info("Parse filings for at least 2 companies to see comparisons.")
        return

    tickers_loaded = [r["ticker"] for r in all_results]
    st.caption(f"Loaded: {', '.join(tickers_loaded)}")

    st.markdown("### Revenue ($M)")
    rev_rows = []
    for r in all_results:
        vals = r.get("line_items", {}).get("revenue", {})
        for year, val in vals.items():
            if isinstance(year, int) and year > 2020 and val and val > 1000:
                rev_rows.append({
                    "ticker": r["ticker"],
                    "year": str(year),
                    "revenue_m": val,
                })
    if rev_rows:
        df_rev = pd.DataFrame(rev_rows)
        fig = px.bar(
            df_rev,
            x="year",
            y="revenue_m",
            color="ticker",
            barmode="group",
            labels={"revenue_m": "Revenue ($M)", "year": "Year", "ticker": "Company"},
            color_discrete_map={
                "PFE": "#0068b5",
                "LLY": "#d4202a",
                "ABBV": "#7b2d8b",
                "JNJ": "#cc0000",
            },
            title="Annual Revenue by Company",
        )
        fig.update_layout(height=400, legend_title="Ticker")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No revenue data extracted yet — re-parse filings.")

    st.markdown("### Margin Comparison (%)")
    margin_rows = []
    margin_metrics = {
        "gross_margin": "Gross Margin",
        "operating_margin": "Operating Margin",
        "net_profit_margin": "Net Margin",
        "rd_intensity": "R&D Intensity",
    }
    for r in all_results:
        ratios = r.get("ratios", {})
        for key, label in margin_metrics.items():
            val = ratios.get(key)
            if val is not None and -2 < val < 2:
                margin_rows.append({
                    "ticker": r["ticker"],
                    "metric": label,
                    "value_pct": round(val * 100, 1),
                })
    if margin_rows:
        df_margins = pd.DataFrame(margin_rows)
        fig2 = px.bar(
            df_margins,
            x="metric",
            y="value_pct",
            color="ticker",
            barmode="group",
            labels={"value_pct": "Margin (%)", "metric": "Metric", "ticker": "Company"},
            color_discrete_map={
                "PFE": "#0068b5",
                "LLY": "#d4202a",
                "ABBV": "#7b2d8b",
                "JNJ": "#cc0000",
            },
            title="Margin & R&D Intensity Comparison",
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### R&D Spending ($M)")
    rd_rows = []
    for r in all_results:
        vals = r.get("line_items", {}).get("rd_expense", {})
        for year, val in vals.items():
            if isinstance(year, int) and year > 2020 and val and val > 100:
                rd_rows.append({
                    "ticker": r["ticker"],
                    "year": str(year),
                    "rd_m": val,
                })
    if rd_rows:
        df_rd = pd.DataFrame(rd_rows)
        fig3 = px.line(
            df_rd,
            x="year",
            y="rd_m",
            color="ticker",
            markers=True,
            labels={"rd_m": "R&D Expense ($M)", "year": "Year"},
            color_discrete_map={
                "PFE": "#0068b5",
                "LLY": "#d4202a",
                "ABBV": "#7b2d8b",
                "JNJ": "#cc0000",
            },
            title="R&D Spending Trend",
        )
        fig3.update_layout(height=400)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### Key Metrics Summary")
    summary_rows = []
    for r in all_results:
        ratios = r.get("ratios", {})
        line_items = r.get("line_items", {})

        def latest(metric: str) -> str:
            vals = line_items.get(metric, {})
            if not vals:
                return "N/A"
            v = vals.get(max(k for k in vals if isinstance(k, int)), None)
            return f"${v:,.0f}M" if v else "N/A"

        summary_rows.append({
            "Company": r["ticker"],
            "Revenue": latest("revenue"),
            "Net Income": latest("net_income"),
            "R&D Expense": latest("rd_expense"),
            "Gross Margin": metrics.format_ratio(ratios.get("gross_margin"), True),
            "Net Margin": metrics.format_ratio(ratios.get("net_profit_margin"), True),
            "R&D Intensity": metrics.format_ratio(ratios.get("rd_intensity"), True),
            "Debt/Equity": metrics.format_ratio(ratios.get("debt_to_equity")),
        })

    st.dataframe(
        pd.DataFrame(summary_rows),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("### 💡 Analytical Narrative")
    st.info(
        "**Story these four companies tell:** Eli Lilly is experiencing explosive "
        "revenue growth driven by GLP-1 drugs (Mounjaro/Zepbound). Pfizer is digesting "
        "a massive post-COVID revenue contraction from peak ~$100B. AbbVie is navigating "
        "the Humira biosimilar cliff, offset by Skyrizi/Rinvoq growth. J&J restructured "
        "by spinning off Kenvue (consumer) in 2023, making year-over-year comparisons "
        "require careful interpretation — a restatement scenario this dashboard surfaces."
    )


def chat_section(ticker: str) -> None:
    st.subheader("Ask the filing")

    if not config.GROQ_API_KEY:
        st.warning("Set GROQ_API_KEY in .env or environment.")
        return

    cross_company = st.sidebar.checkbox(
        "Cross-company chat (all indexed tickers)",
        key="cross_company_checkbox",
    )

    if cross_company:
        vs_input = embedder.load_all_vectorstores()
        if not vs_input:
            st.info("No indexes found. Build embeddings first.")
            return
        st.caption(f"🔍 Searching across: {', '.join(vs_input.keys())}")
    else:
        vs = st.session_state.get("vectorstore") or embedder.load_vectorstore(ticker)
        if not vs:
            st.info("Build or load embeddings to chat with filing content.")
            return
        vs_input = {ticker: vs}
        st.caption(f"🔍 Searching: {ticker} only")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander("Sources"):
                    for cite in msg["citations"]:
                        st.markdown(
                            f"**[{cite['index']}]** {cite.get('ticker', '?')} "
                            f"{cite.get('year', '')} {cite['type']}"
                            + (f" (page {cite['page']})" if cite.get("page") else "")
                        )
                        st.caption(cite["snippet"][:200] + "...")

    if prompt := st.chat_input("Ask about revenue, risk factors, debt..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching filings..."):
                try:
                    response = rag_chain.ask(vs_input, prompt)
                    answer = response["answer"]
                    st.markdown(answer)
                    st.caption(f"Rewritten query: *{response['rewritten_query']}*")
                    if response.get("refused"):
                        st.warning("⚠️ System refused — insufficient data in filings.")
                    if response.get("citations"):
                        with st.expander("Sources"):
                            for cite in response["citations"]:
                                st.markdown(
                                    f"**[{cite['index']}]** {cite.get('ticker', '?')} "
                                    f"{cite.get('year', '')} {cite['type']}"
                                    + (f" p.{cite['page']}" if cite.get("page") else "")
                                )
                                st.caption(cite["snippet"][:200] + "...")
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "citations": response.get("citations"),
                    })
                except Exception as exc:
                    st.error(str(exc))


def main() -> None:
    init_session_state()
    st.title("Pharma Financial Analysis Dashboard")
    st.markdown(
        "SEC EDGAR 10-K → HTML table extraction → ChromaDB RAG → pharma ratios & charts"
    )

    ticker, form_type = sidebar_controls()
    st.session_state["_ticker"] = ticker

    tab_pipeline, tab_metrics, tab_compare, tab_chat = st.tabs(
        ["Pipeline", "Metrics & Charts", "📊 Comparisons", "Chat"]
    )

    with tab_pipeline:
        pipeline_section(ticker, form_type)
        filing = _resolve_filing_path(ticker, st.session_state.filing_path)
        if filing:
            st.caption(f"Latest file: `{filing.name}`")
        if embedder.is_indexed(ticker):
            st.caption("Vector index: indexed")

    with tab_metrics:
        metrics_dashboard()

    with tab_compare:
        comparison_section()

    with tab_chat:
        chat_section(ticker)


if __name__ == "__main__":
    main()
