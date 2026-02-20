"""
Stock Deck — Minimalist Stock Presentation App
Revenue analysis with CAGR, YoY growth, and year range selection.
"""

import streamlit as st
import plotly.graph_objects as go
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Deck",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #050505 !important;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stToolbar"] { display: none; }

    .block-container {
        padding: 2.5rem 3.5rem 4rem 3.5rem !important;
        max-width: 1440px;
    }

    /* ── Ticker input ─────────────────────────────────────────────── */
    [data-testid="stTextInput"] input {
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid #1e1e1e !important;
        border-radius: 0 !important;
        color: #ffffff !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.12em !important;
        padding: 0.4rem 0 0.6rem 0 !important;
        text-transform: uppercase !important;
        caret-color: #3b82f6;
    }
    [data-testid="stTextInput"] input:focus {
        border-bottom-color: #3b82f6 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] input::placeholder {
        color: #222 !important;
    }
    [data-testid="stTextInput"] label { display: none !important; }

    /* ── Slider ───────────────────────────────────────────────────── */
    [data-testid="stSelectSlider"] label { display: none !important; }
    [data-testid="stSlider"] label { display: none !important; }

    /* ── Buttons ──────────────────────────────────────────────────── */
    .stFormSubmitButton button, .stButton button {
        background: transparent !important;
        border: 1px solid #1e1e1e !important;
        color: #4a4a4a !important;
        border-radius: 6px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.05em !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    .stFormSubmitButton button:hover, .stButton button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
        background: transparent !important;
    }

    /* ── Dividers ─────────────────────────────────────────────────── */
    hr {
        border: none !important;
        border-top: 1px solid #111 !important;
        margin: 1.5rem 0 !important;
    }

    /* ── Popover / Expander ───────────────────────────────────────── */
    [data-testid="stPopover"] button {
        background: transparent !important;
        border: 1px solid #111 !important;
        color: #333 !important;
        border-radius: 6px !important;
        font-size: 0.9rem !important;
        padding: 0.3rem 0.7rem !important;
    }
    [data-testid="stPopover"] button:hover {
        border-color: #333 !important;
        color: #555 !important;
    }

    /* ── Scrollbar ────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 3px; height: 3px; }
    ::-webkit-scrollbar-track { background: #050505; }
    ::-webkit-scrollbar-thumb { background: #1a1a1a; border-radius: 2px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Helper Functions ──────────────────────────────────────────────────────────

def fmt(value: float, currency: str = "USD") -> str:
    """Format a financial value to a short, human-readable string."""
    sym = "$" if currency in ("USD", "usd") else f"{currency} "
    if abs(value) >= 1e12:
        return f"{sym}{value / 1e12:.2f}T"
    if abs(value) >= 1e9:
        return f"{sym}{value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"{sym}{value / 1e6:.2f}M"
    return f"{sym}{value:,.0f}"


def cagr(start: float, end: float, years: int) -> float | None:
    """Compound Annual Growth Rate."""
    if years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


# ─── Data Fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_yf(ticker: str) -> dict | None:
    """Fetch revenue + company info from Yahoo Finance (last ~4 years)."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # Validate ticker
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return None

        income = t.income_stmt
        if income is None or income.empty:
            return None
        if "Total Revenue" not in income.index:
            return None

        rev_series = income.loc["Total Revenue"].dropna()
        revenue = {
            int(pd.to_datetime(dt).year): float(val)
            for dt, val in rev_series.items()
            if float(val) > 0
        }
        if not revenue:
            return None

        return {
            "revenue": revenue,
            "name": info.get("longName", ticker.upper()),
            "sector": info.get("sector", ""),
            "currency": info.get("financialCurrency", "USD"),
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_fmp(ticker: str, api_key: str) -> dict | None:
    """Fetch revenue from Financial Modeling Prep API (up to 15 years)."""
    try:
        url = (
            f"https://financialmodelingprep.com/api/v3/income-statement/"
            f"{ticker}?limit=15&apikey={api_key}"
        )
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        revenue = {
            int(item["date"][:4]): float(item["revenue"])
            for item in data
            if item.get("revenue", 0) > 0
        }
        return {"revenue": revenue} if revenue else None
    except Exception:
        return None


def load_data(ticker: str, fmp_key: str = "") -> dict | None:
    """Load stock data, using FMP for history if key provided."""
    ticker = ticker.upper().strip()
    if not ticker:
        return None

    yf_data = _fetch_yf(ticker)

    if fmp_key:
        fmp_data = _fetch_fmp(ticker, fmp_key)
        if fmp_data and fmp_data.get("revenue"):
            merged = dict(fmp_data["revenue"])
            if yf_data and yf_data.get("revenue"):
                merged.update(yf_data["revenue"])  # yf overwrites with fresher data
            return {
                "revenue": merged,
                "name": (yf_data or {}).get("name", ticker),
                "sector": (yf_data or {}).get("sector", ""),
                "currency": (yf_data or {}).get("currency", "USD"),
            }

    return yf_data


# ─── Session State ─────────────────────────────────────────────────────────────

for _k, _v in [
    ("stock_data", None),
    ("current_ticker", "AAPL"),
    ("last_loaded", ""),
    ("fmp_key", ""),
    ("load_error", ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─── Top Bar ──────────────────────────────────────────────────────────────────

col_logo, _, col_gear = st.columns([3, 8, 1])

with col_logo:
    st.markdown(
        '<span style="font-size:0.6rem; letter-spacing:0.35em; color:#252525; '
        'font-weight:600; text-transform:uppercase;">◈ STOCK DECK</span>',
        unsafe_allow_html=True,
    )

with col_gear:
    with st.popover("⚙", use_container_width=False):
        st.markdown(
            '<p style="font-size:0.65rem; letter-spacing:0.2em; color:#333; '
            'text-transform:uppercase; margin:0 0 1rem 0;">API SETTINGS</p>',
            unsafe_allow_html=True,
        )
        new_key = st.text_input(
            "FMP API Key",
            value=st.session_state["fmp_key"],
            type="password",
            placeholder="Optional — unlocks 10-year history",
            help="Get a free key at financialmodelingprep.com",
        )
        st.markdown(
            '<p style="font-size:0.65rem; color:#252525; margin-top:0.5rem;">'
            "Without key: ~4 years via Yahoo Finance<br>"
            "With free key: up to 10 years via FMP</p>",
            unsafe_allow_html=True,
        )
        if new_key != st.session_state["fmp_key"]:
            st.session_state["fmp_key"] = new_key
            st.session_state["stock_data"] = None
            st.session_state["last_loaded"] = ""
            _fetch_yf.clear()
            _fetch_fmp.clear()

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Ticker Search Form ────────────────────────────────────────────────────────

with st.form("ticker_form", clear_on_submit=False):
    fcol1, fcol2, fcol3 = st.columns([4, 1, 7])
    with fcol1:
        ticker_input = st.text_input(
            "ticker",
            value=st.session_state["current_ticker"],
            placeholder="AAPL",
            label_visibility="collapsed",
            max_chars=10,
        )
    with fcol2:
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Load →", use_container_width=False)

if submitted:
    clean_ticker = ticker_input.upper().strip()
    if clean_ticker:
        with st.spinner(""):
            result = load_data(clean_ticker, st.session_state["fmp_key"])
        if result:
            st.session_state["stock_data"] = result
            st.session_state["current_ticker"] = clean_ticker
            st.session_state["last_loaded"] = clean_ticker
            st.session_state["load_error"] = ""
        else:
            st.session_state["load_error"] = clean_ticker

# Auto-load AAPL on first visit
if st.session_state["stock_data"] is None and not st.session_state["load_error"]:
    with st.spinner(""):
        result = load_data("AAPL", st.session_state["fmp_key"])
    if result:
        st.session_state["stock_data"] = result
        st.session_state["current_ticker"] = "AAPL"
        st.session_state["last_loaded"] = "AAPL"

# Show error if load failed
if st.session_state["load_error"]:
    st.markdown(
        f'<p style="color:#ef4444; font-size:0.8rem; margin-top:0.5rem;">'
        f'No data found for <strong>{st.session_state["load_error"]}</strong>. '
        f"Check the ticker and try again.</p>",
        unsafe_allow_html=True,
    )

data = st.session_state["stock_data"]
if not data:
    st.stop()

# ─── Prepare Revenue Data ──────────────────────────────────────────────────────

currency = data.get("currency", "USD")
company_name = data.get("name", st.session_state["current_ticker"])
sector = data.get("sector", "")
ticker_label = st.session_state["current_ticker"]

current_year = datetime.now().year
min_year = current_year - 10

revenue_all = {
    yr: val
    for yr, val in data["revenue"].items()
    if min_year <= yr <= current_year
}

if len(revenue_all) < 2:
    st.warning(
        f"Not enough revenue data for **{ticker_label}** (need at least 2 years). "
        "Try a different ticker."
    )
    st.stop()

sorted_years = sorted(revenue_all.keys())

# ─── Company Header ────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)

subtitle_parts = [ticker_label]
if sector:
    subtitle_parts.append(sector)
subtitle_parts.append("Revenue")

st.markdown(
    f'<div style="font-size:3rem; font-weight:900; letter-spacing:-0.04em; '
    f'color:#f5f5f5; line-height:1; margin-bottom:0.4rem;">{company_name}</div>'
    f'<div style="font-size:0.65rem; color:#252525; letter-spacing:0.25em; '
    f'text-transform:uppercase; margin-bottom:2.5rem;">'
    f'{"  ·  ".join(subtitle_parts)}</div>',
    unsafe_allow_html=True,
)

# ─── Year Range Selector ───────────────────────────────────────────────────────

st.markdown(
    '<div style="font-size:0.6rem; color:#252525; letter-spacing:0.25em; '
    'text-transform:uppercase; margin-bottom:0.4rem;">PERIOD</div>',
    unsafe_allow_html=True,
)

if len(sorted_years) == 1:
    start_yr = end_yr = sorted_years[0]
    st.markdown(
        f'<span style="font-size:0.9rem; color:#555;">{start_yr}</span>',
        unsafe_allow_html=True,
    )
else:
    year_range = st.select_slider(
        "period",
        options=sorted_years,
        value=(sorted_years[0], sorted_years[-1]),
        label_visibility="collapsed",
    )
    start_yr, end_yr = year_range

sel_years = [y for y in sorted_years if start_yr <= y <= end_yr]
sel_revs = [revenue_all[y] for y in sel_years]

if len(sel_years) < 2:
    st.info("Select a range of at least 2 years.")
    st.stop()

# ─── Layout: Chart + CAGR ─────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
col_chart, col_metrics = st.columns([4, 1], gap="large")

# ── Right column: CAGR + Latest YoY ──────────────────────────────────────────
with col_metrics:
    n_years = end_yr - start_yr
    period_cagr = cagr(sel_revs[0], sel_revs[-1], n_years)

    # CAGR card
    if period_cagr is not None:
        cagr_pct = period_cagr * 100
        cagr_color = "#4ade80" if cagr_pct >= 0 else "#f87171"
        cagr_sign = "+" if cagr_pct >= 0 else ""
        cagr_display = f"{cagr_sign}{cagr_pct:.1f}%"
    else:
        cagr_color = "#333"
        cagr_display = "—"

    start_rev_str = fmt(sel_revs[0], currency)
    end_rev_str = fmt(sel_revs[-1], currency)

    st.markdown(
        f"""
        <div style="
            background:#0c0c0c;
            border:1px solid #131313;
            border-radius:12px;
            padding:2rem 1.5rem;
            text-align:center;
            margin-bottom:0.75rem;
        ">
            <div style="font-size:0.6rem; letter-spacing:0.25em; color:#252525;
                text-transform:uppercase; margin-bottom:1.2rem;">CAGR</div>
            <div style="font-size:3rem; font-weight:900; color:{cagr_color};
                line-height:1; letter-spacing:-0.04em;">{cagr_display}</div>
            <div style="font-size:0.65rem; color:#1e1e1e; margin-top:0.6rem;
                letter-spacing:0.05em;">{start_yr} – {end_yr}</div>
            <div style="
                font-size:0.6rem; color:#1a1a1a;
                margin-top:1.2rem; padding-top:1rem;
                border-top:1px solid #111;
                line-height:1.8;
            ">
                {start_rev_str}<br>↓<br>{end_rev_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Latest YoY card
    prev_rev, last_rev = sel_revs[-2], sel_revs[-1]
    latest_yoy = (last_rev - prev_rev) / prev_rev * 100 if prev_rev else 0
    yoy_color = "#4ade80" if latest_yoy >= 0 else "#f87171"
    yoy_sign = "+" if latest_yoy >= 0 else ""

    st.markdown(
        f"""
        <div style="
            background:#0c0c0c;
            border:1px solid #131313;
            border-radius:12px;
            padding:1.5rem;
            text-align:center;
        ">
            <div style="font-size:0.6rem; letter-spacing:0.25em; color:#252525;
                text-transform:uppercase; margin-bottom:1rem;">LATEST YoY</div>
            <div style="font-size:2.2rem; font-weight:800; color:{yoy_color};
                line-height:1; letter-spacing:-0.03em;">
                {yoy_sign}{latest_yoy:.1f}%
            </div>
            <div style="font-size:0.6rem; color:#1e1e1e; margin-top:0.5rem;">
                {sel_years[-2]} → {sel_years[-1]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Left column: Bar chart ────────────────────────────────────────────────────
with col_chart:
    # Bar colors: first bar neutral, rest based on YoY direction
    bar_colors = []
    for i, rev in enumerate(sel_revs):
        if i == 0:
            bar_colors.append("#1c1c1c")
        else:
            growth = (rev - sel_revs[i - 1]) / sel_revs[i - 1] if sel_revs[i - 1] else 0
            bar_colors.append("#22c55e" if growth >= 0 else "#ef4444")

    # Normalise for y-axis readability
    max_rev = max(sel_revs)
    if max_rev >= 1e12:
        unit, unit_label = 1e12, "Revenue (USD Trillions)"
    elif max_rev >= 1e9:
        unit, unit_label = 1e9, "Revenue (USD Billions)"
    else:
        unit, unit_label = 1e6, "Revenue (USD Millions)"

    rev_norm = [r / unit for r in sel_revs]
    bar_labels = [fmt(r, currency) for r in sel_revs]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=sel_years,
            y=rev_norm,
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=bar_labels,
            textposition="outside",
            textfont=dict(size=10, color="#333", family="Inter"),
            hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            width=0.52,
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#444"),
        height=380,
        margin=dict(l=0, r=10, t=40, b=10),
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False,
            tickvals=sel_years,
            ticktext=[str(y) for y in sel_years],
            tickfont=dict(size=12, color="#444"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#0f0f0f",
            gridwidth=1,
            showline=False,
            zeroline=False,
            tickfont=dict(size=10, color="#2a2a2a"),
            title=dict(
                text=unit_label,
                font=dict(size=9, color="#1e1e1e"),
            ),
        ),
        bargap=0.35,
        showlegend=False,
        title=dict(
            text="ANNUAL REVENUE",
            font=dict(size=9, color="#1e1e1e", family="Inter"),
            x=0,
            xanchor="left",
            y=0.99,
            yanchor="top",
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ─── YoY Growth Chips ─────────────────────────────────────────────────────────

st.markdown(
    '<div style="font-size:0.6rem; color:#1e1e1e; letter-spacing:0.25em; '
    'text-transform:uppercase; margin:0.25rem 0 1rem 0;">YEAR-OVER-YEAR GROWTH</div>',
    unsafe_allow_html=True,
)

chips = []
for i in range(1, len(sel_years)):
    pct = (
        (sel_revs[i] - sel_revs[i - 1]) / sel_revs[i - 1] * 100
        if sel_revs[i - 1]
        else 0
    )
    is_pos = pct >= 0
    color = "#4ade80" if is_pos else "#f87171"
    sign = "+" if is_pos else ""
    chips.append(
        f'<div style="background:#0c0c0c; border:1px solid #131313; '
        f'border-radius:8px; padding:10px 18px; text-align:center; min-width:80px;">'
        f'<div style="font-size:0.55rem; color:#1e1e1e; letter-spacing:0.15em; '
        f'text-transform:uppercase; margin-bottom:5px;">{sel_years[i]}</div>'
        f'<div style="font-size:1rem; font-weight:700; color:{color}; '
        f'letter-spacing:-0.01em;">{sign}{pct:.1f}%</div>'
        f"</div>"
    )

st.markdown(
    f'<div style="display:flex; flex-wrap:wrap; gap:8px;">{"".join(chips)}</div>',
    unsafe_allow_html=True,
)

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:0.55rem; color:#151515; text-align:right; '
    'letter-spacing:0.15em; text-transform:uppercase;">'
    "DATA: YAHOO FINANCE · FINANCIAL MODELING PREP</div>",
    unsafe_allow_html=True,
)
