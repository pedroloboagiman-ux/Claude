"""
13F Portfolio Analyzer — Streamlit Application

Analyze institutional investor portfolios from SEC 13F filings.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sec_edgar import build_portfolio, search_filers
from cusip_mapper import map_cusips_to_tickers
from financial_data import build_display_dataframe, fetch_all_metrics

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="13F Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1a1d27;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .positive { color: #00c48c; }
    .negative { color: #ff4b4b; }
    .tag-new {
        background: #4f8ef7;
        color: white;
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 11px;
        font-weight: 600;
    }
    div[data-testid="stMetric"] {
        background-color: #1a1d27;
        border-radius: 8px;
        padding: 12px 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
def render_sidebar() -> tuple[str | None, str | None]:
    """Render sidebar search and return (selected_cik, openfigi_api_key)."""
    with st.sidebar:
        st.title("🔍 Find Investor")
        st.caption("Search for institutional investors by name")

        query = st.text_input(
            "Investor Name",
            placeholder="e.g. Berkshire, BlackRock, Tiger Global",
            key="investor_query",
        )

        if st.button("Search", use_container_width=True, type="primary"):
            if query.strip():
                with st.spinner("Searching SEC EDGAR..."):
                    results = search_filers(query.strip())
                st.session_state["search_results"] = results
                st.session_state["selected_cik"] = None
            else:
                st.warning("Enter an investor name to search.")

        # Display search results
        results = st.session_state.get("search_results", [])
        selected_cik = None

        if results:
            st.divider()
            options = {f"{r['name']} (CIK {r['cik']})": r["cik"] for r in results}
            choice = st.selectbox(
                f"Found {len(results)} filer(s)",
                list(options.keys()),
                key="investor_select",
            )
            if st.button("Load Portfolio", use_container_width=True, type="secondary"):
                st.session_state["selected_cik"] = options[choice]
                st.session_state["portfolio_loaded"] = False

            selected_cik = st.session_state.get("selected_cik")

        elif st.session_state.get("search_results") is not None:
            st.info("No institutional investors found. Try a different name.")

        st.divider()

        # CIK direct input
        with st.expander("Enter CIK directly"):
            direct_cik = st.text_input("CIK Number", placeholder="e.g. 0001067983")
            if st.button("Load by CIK", use_container_width=True):
                cik_padded = str(direct_cik).strip().zfill(10)
                st.session_state["selected_cik"] = cik_padded
                st.session_state["portfolio_loaded"] = False
                st.session_state["search_results"] = None

        st.divider()

        # Settings
        with st.expander("⚙️ Settings"):
            api_key = st.text_input(
                "OpenFIGI API Key (optional)",
                type="password",
                help="Increases rate limits for CUSIP→ticker mapping. Free at openfigi.com",
                key="openfigi_key",
            )
            st.caption(
                "Without API key: 25 CUSIPs/request. "
                "With key: 100 CUSIPs/request and higher rate limits."
            )

        st.divider()
        st.caption("Data sources: SEC EDGAR · OpenFIGI · Yahoo Finance")

        return st.session_state.get("selected_cik"), st.session_state.get("openfigi_key", "")


# ─── Portfolio loading ─────────────────────────────────────────────────────────
def load_portfolio_data(cik: str, api_key: str | None):
    """
    Orchestrate data loading pipeline with progress indicators.
    Stores results in session state to avoid reloading on widget interaction.
    """
    cache_key = f"portfolio_{cik}"
    if st.session_state.get("portfolio_loaded") and st.session_state.get("portfolio_cik") == cik:
        return (
            st.session_state.get("display_df"),
            st.session_state.get("portfolio_meta"),
        )

    with st.status("Loading portfolio data...", expanded=True) as status:
        # Step 1: SEC filings
        st.write("📂 Fetching 13F filings from SEC EDGAR...")
        try:
            portfolio_df, meta = build_portfolio(cik)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"SEC EDGAR request failed: {e}")
            st.stop()

        st.write(f"✅ Found {len(portfolio_df)} holdings (as of {meta['filing_date']})")

        # Step 2: CUSIP→ticker mapping
        st.write("🔗 Mapping securities to tickers (OpenFIGI)...")
        cusips = portfolio_df["cusip"].tolist()
        ticker_map = map_cusips_to_tickers(cusips, api_key or None)
        n_resolved = sum(1 for t in ticker_map.values() if t is not None)
        st.write(f"✅ Resolved {n_resolved}/{len(cusips)} CUSIPs to tickers")

        # Step 3: Financial metrics
        valid_tickers = [t for t in ticker_map.values() if t is not None]
        st.write(f"📈 Fetching financial metrics for {len(valid_tickers)} tickers (Yahoo Finance)...")
        metrics = fetch_all_metrics(valid_tickers)

        n_errors = sum(1 for m in metrics.values() if m.get("error"))
        if n_errors:
            st.write(f"⚠️ {n_errors} tickers had partial or missing data")

        # Step 4: Build display DataFrame
        st.write("🏗️ Building portfolio table...")
        display_df = build_display_dataframe(portfolio_df, ticker_map, metrics)

        status.update(label="Portfolio loaded!", state="complete", expanded=False)

    # Cache in session state
    st.session_state["portfolio_loaded"] = True
    st.session_state["portfolio_cik"] = cik
    st.session_state["display_df"] = display_df
    st.session_state["portfolio_meta"] = meta

    return display_df, meta


# ─── UI Rendering ──────────────────────────────────────────────────────────────
def render_header_metrics(meta: dict):
    """Display top-level portfolio summary metrics."""
    total_b = meta["total_value_usd"] / 1_000_000_000
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Filer", meta["filer_name"])
    col2.metric("Filing Date", meta["filing_date"])
    col3.metric(
        "Previous Filing",
        meta["prev_filing_date"] if meta["prev_filing_date"] else "N/A",
    )
    col4.metric("Total Portfolio", f"${total_b:.2f}B")


def _color_qoq(val):
    """Color QoQ values: green positive, red negative."""
    if pd.isna(val) or val is None:
        return ""
    return "color: #00c48c" if val > 0 else ("color: #ff4b4b" if val < 0 else "")


def _color_return(val):
    """Color 1Y return values: green positive, red negative."""
    if pd.isna(val) or val is None:
        return ""
    return "color: #00c48c" if val > 0 else ("color: #ff4b4b" if val < 0 else "")


def render_holdings_table(df: pd.DataFrame):
    """Render the main holdings table with formatted columns."""
    st.subheader(f"Holdings ({len(df)} positions)")

    # Prepare display copy
    display = df.copy()

    # Mark new positions in QoQ column
    def format_qoq(row):
        if row.get("Is New"):
            return "NEW"
        val = row["QoQ %"]
        if pd.isna(val) or val is None:
            return None
        return val

    display["QoQ %"] = display.apply(format_qoq, axis=1)

    cols_to_show = [
        "Company", "Ticker", "Weight %", "QoQ %",
        "Forward P/E", "EV/EBITDA", "ROE %", "1Y Return %", "Value ($M)",
    ]
    display = display[cols_to_show]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            "Company": st.column_config.TextColumn("Company", width="large"),
            "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            "Weight %": st.column_config.NumberColumn(
                "Weight %", format="%.2f%%", width="small"
            ),
            "QoQ %": st.column_config.TextColumn("QoQ Chg", width="small"),
            "Forward P/E": st.column_config.NumberColumn(
                "P/E NTM", format="%.1f×", width="small",
                help="Forward Price-to-Earnings (Next Twelve Months)"
            ),
            "EV/EBITDA": st.column_config.NumberColumn(
                "EV/EBITDA", format="%.1f×", width="small",
                help="Enterprise Value to EBITDA"
            ),
            "ROE %": st.column_config.NumberColumn(
                "ROE %", format="%.1f%%", width="small",
                help="Return on Equity (trailing twelve months)"
            ),
            "1Y Return %": st.column_config.NumberColumn(
                "LTM Return %", format="%.1f%%", width="small",
                help="Last Twelve Months stock price return"
            ),
            "Value ($M)": st.column_config.NumberColumn(
                "Value ($M)", format="$%.1fM", width="small"
            ),
        },
    )

    # Download button
    csv = display.to_csv(index=False)
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv,
        file_name=f"portfolio_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


def render_composition_chart(df: pd.DataFrame):
    """Horizontal bar chart of top 20 holdings by weight."""
    top20 = df.head(20).copy()
    top20 = top20.sort_values("Weight %", ascending=True)

    # Color by 1Y return
    top20["color"] = top20["1Y Return %"].apply(
        lambda x: x if pd.notna(x) and x is not None else 0
    )

    fig = px.bar(
        top20,
        x="Weight %",
        y="Company",
        orientation="h",
        color="1Y Return %",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        hover_data=["Ticker", "Value ($M)", "QoQ %", "1Y Return %"],
        labels={"Weight %": "Portfolio Weight (%)"},
        title="Top 20 Holdings by Portfolio Weight",
        height=550,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        coloraxis_colorbar=dict(title="1Y Return %"),
        margin=dict(l=10, r=10, t=50, b=30),
        yaxis=dict(tickfont=dict(size=11)),
    )
    fig.update_traces(texttemplate="%{x:.1f}%", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def render_valuation_chart(df: pd.DataFrame):
    """Scatter plot: Forward P/E vs EV/EBITDA, sized by weight, colored by 1Y return."""
    scatter_df = df.dropna(subset=["Forward P/E", "EV/EBITDA"]).copy()

    if scatter_df.empty:
        st.info("Not enough valuation data to display scatter chart.")
        return

    # Cap extreme outliers for readability
    scatter_df = scatter_df[scatter_df["Forward P/E"] < 200]
    scatter_df = scatter_df[scatter_df["EV/EBITDA"] < 200]

    fig = px.scatter(
        scatter_df,
        x="Forward P/E",
        y="EV/EBITDA",
        size="Weight %",
        color="1Y Return %",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        hover_name="Company",
        hover_data={
            "Ticker": True,
            "Weight %": ":.2f",
            "Forward P/E": ":.1f",
            "EV/EBITDA": ":.1f",
            "ROE %": ":.1f",
            "1Y Return %": ":.1f",
        },
        title="Valuation Overview: P/E NTM vs EV/EBITDA",
        labels={
            "Forward P/E": "Forward P/E (NTM)",
            "EV/EBITDA": "EV/EBITDA",
        },
        height=550,
        size_max=50,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(26,29,39,0.8)",
        font_color="#fafafa",
        coloraxis_colorbar=dict(title="1Y Return %"),
        margin=dict(l=10, r=10, t=50, b=30),
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Showing {len(scatter_df)} of {len(df)} positions (excluded positions with missing valuation data)")


def render_performance_chart(df: pd.DataFrame):
    """Bar chart of 1Y return for top 20 holdings."""
    perf_df = df.dropna(subset=["1Y Return %"]).head(20).copy()
    perf_df = perf_df.sort_values("1Y Return %", ascending=True)

    if perf_df.empty:
        st.info("No LTM performance data available.")
        return

    colors = ["#00c48c" if v >= 0 else "#ff4b4b" for v in perf_df["1Y Return %"]]

    fig = go.Figure(go.Bar(
        x=perf_df["1Y Return %"],
        y=perf_df["Company"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in perf_df["1Y Return %"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>1Y Return: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title="LTM Stock Price Return — Top 20 Holdings",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        height=550,
        margin=dict(l=10, r=80, t=50, b=30),
        xaxis=dict(title="1Y Return (%)", gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(tickfont=dict(size=11)),
    )
    fig.add_vline(x=0, line_color="white", line_width=1, opacity=0.5)
    st.plotly_chart(fig, use_container_width=True)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Header
    st.title("📊 13F Portfolio Analyzer")
    st.caption(
        "Analyze institutional investor portfolios from SEC 13F filings. "
        "Financial metrics sourced from Yahoo Finance."
    )

    # Initialize session state
    if "search_results" not in st.session_state:
        st.session_state["search_results"] = None
    if "selected_cik" not in st.session_state:
        st.session_state["selected_cik"] = None
    if "portfolio_loaded" not in st.session_state:
        st.session_state["portfolio_loaded"] = False

    # Sidebar
    selected_cik, api_key = render_sidebar()

    # Main content
    if not selected_cik:
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**Step 1:** Search for an institutional investor by name in the sidebar")
        with col2:
            st.info("**Step 2:** Select the investor from the search results")
        with col3:
            st.info("**Step 3:** Click 'Load Portfolio' to analyze their 13F holdings")

        st.markdown("---")
        st.markdown(
            """
            ### What is a 13F?
            Form 13F is a quarterly report filed with the SEC by institutional investment managers
            with over $100 million in qualifying assets. It discloses their US equity holdings,
            allowing investors to see what major hedge funds, mutual funds, and other institutions own.

            ### Metrics Explained
            | Metric | Description |
            |---|---|
            | **Weight %** | Position size as % of total portfolio |
            | **QoQ %** | Quarter-over-quarter change in shares held |
            | **P/E NTM** | Forward Price-to-Earnings (Next Twelve Months estimates) |
            | **EV/EBITDA** | Enterprise Value to EBITDA |
            | **ROE %** | Return on Equity (trailing twelve months) |
            | **LTM Return %** | Stock price performance over the last 12 months |
            """
        )
        return

    # Load and display portfolio
    display_df, meta = load_portfolio_data(selected_cik, api_key)

    if display_df is None or display_df.empty:
        st.error("No holdings data available for this investor.")
        return

    # Summary metrics
    render_header_metrics(meta)
    st.markdown("---")

    # Summary stats row
    col1, col2, col3, col4 = st.columns(4)
    n_positions = len(display_df)
    n_new = display_df["Is New"].sum() if "Is New" in display_df.columns else 0
    avg_pe = display_df["Forward P/E"].dropna().mean()
    avg_return = display_df["1Y Return %"].dropna().mean()

    col1.metric("Positions", n_positions)
    col2.metric("New Positions (QoQ)", int(n_new))
    col3.metric(
        "Avg Forward P/E",
        f"{avg_pe:.1f}×" if pd.notna(avg_pe) else "N/A"
    )
    col4.metric(
        "Avg LTM Return",
        f"{avg_return:.1f}%" if pd.notna(avg_return) else "N/A",
        delta_color="normal",
    )

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Holdings Table",
        "🥧 Portfolio Composition",
        "💹 Performance",
        "📐 Valuation",
    ])

    with tab1:
        render_holdings_table(display_df)

    with tab2:
        render_composition_chart(display_df)

    with tab3:
        render_performance_chart(display_df)

    with tab4:
        render_valuation_chart(display_df)

    # Footer note
    st.markdown("---")
    st.caption(
        "⚠️ Data is sourced from SEC EDGAR (13F filings) and Yahoo Finance. "
        "Financial metrics may be missing for some positions (e.g., options, foreign securities, recently delisted stocks). "
        "This tool is for informational purposes only and does not constitute investment advice."
    )


if __name__ == "__main__":
    main()
