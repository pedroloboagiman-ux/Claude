"""
Stock Deck — Minimalist Stock Presentation App
Revenue analysis with CAGR, YoY growth, year range selection,
and AI-powered revenue driver analysis from earnings transcripts / press releases.
"""

import re
import json
import streamlit as st
import plotly.graph_objects as go
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from html.parser import HTMLParser

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
        font-size: 15px !important;
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
        border-bottom: 2px solid #1e1e1e !important;
        border-radius: 0 !important;
        color: #ffffff !important;
        font-size: 2.4rem !important;
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
    [data-testid="stSelectSlider"] p { font-size: 0.85rem !important; }

    /* ── Selectbox ────────────────────────────────────────────────── */
    [data-testid="stSelectbox"] label { display: none !important; }
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: #0c0c0c !important;
        border-color: #1e1e1e !important;
        font-size: 0.9rem !important;
        color: #ccc !important;
    }

    /* ── Buttons ──────────────────────────────────────────────────── */
    .stFormSubmitButton button, .stButton button {
        background: transparent !important;
        border: 1px solid #2a2a2a !important;
        color: #999 !important;
        border-radius: 6px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.06em !important;
        padding: 0.6rem 1.8rem !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        white-space: nowrap !important;
    }
    .stFormSubmitButton button:hover, .stButton button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
        background: rgba(59,130,246,0.05) !important;
    }

    /* ── Primary analyze button ───────────────────────────────────── */
    .analyze-btn .stButton button {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
    }
    .analyze-btn .stButton button:hover {
        background: rgba(59,130,246,0.12) !important;
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
        color: #666 !important;
        border-radius: 6px !important;
        font-size: 1rem !important;
        padding: 0.3rem 0.7rem !important;
    }
    [data-testid="stPopover"] button:hover {
        border-color: #333 !important;
        color: #888 !important;
    }

    /* ── General text sizing ──────────────────────────────────────── */
    p, .stMarkdown p {
        font-size: 0.9rem !important;
        color: #aaa;
    }

    /* ── Scrollbar ────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 3px; height: 3px; }
    ::-webkit-scrollbar-track { background: #050505; }
    ::-webkit-scrollbar-thumb { background: #1a1a1a; border-radius: 2px; }

    /* ── Section label ────────────────────────────────────────────── */
    .section-label {
        font-size: 0.7rem !important;
        color: #666 !important;
        letter-spacing: 0.28em !important;
        text-transform: uppercase !important;
        margin-bottom: 0.5rem !important;
        font-weight: 600 !important;
    }

    /* ── Factor card ──────────────────────────────────────────────── */
    .factor-card {
        background: #0a0a0a;
        border-left: 2px solid #1e3a5f;
        border-radius: 0 8px 8px 0;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.6rem;
        font-size: 0.9rem;
        color: #bbb;
        line-height: 1.6;
    }
    .factor-card.positive { border-left-color: #166534; }
    .factor-card.negative { border-left-color: #7f1d1d; }
    .factor-card.neutral  { border-left-color: #1e3a5f; }
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


# ─── HTML Text Extractor ───────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip = True
        if tag in ("p", "br", "li", "div", "tr", "h1", "h2", "h3", "h4"):
            self._parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        return re.sub(r"\s+", " ", raw).strip()


def _strip_html(html_text: str) -> str:
    ext = _TextExtractor()
    ext.feed(html_text)
    return ext.get_text()


def _extract_key_sentences(text: str, n: int = 7) -> list[str]:
    """Return the top-N most revenue-relevant sentences from plain text."""
    keywords = [
        "revenue", "sales", "growth", "decline", "decreas", "increas",
        "headwind", "tailwind", "demand", "pricing", "volume", "market",
        "segment", "product", "services", "geographic", "foreign exchange",
        "currency", "supply", "launch", "customer", "adoption", "macro",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored: list[tuple[int, str]] = []
    for sent in sentences:
        low = sent.lower()
        if 60 < len(sent) < 500:
            score = sum(1 for kw in keywords if kw in low)
            if score > 0:
                scored.append((score, sent.strip()))

    scored.sort(reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for _, sent in scored:
        norm = re.sub(r"\s+", " ", sent)
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
            if len(result) >= n:
                break
    return result


# ─── Data Fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_yf(ticker: str) -> dict | None:
    """Fetch revenue + company info from Yahoo Finance (last ~4 years)."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

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
                merged.update(yf_data["revenue"])
            return {
                "revenue": merged,
                "name": (yf_data or {}).get("name", ticker),
                "sector": (yf_data or {}).get("sector", ""),
                "currency": (yf_data or {}).get("currency", "USD"),
            }

    return yf_data


# ─── Revenue Drivers — Data Layer ─────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_cik(ticker: str) -> str | None:
    """Resolve ticker → SEC EDGAR CIK (zero-padded to 10 digits)."""
    try:
        headers = {"User-Agent": "StockDeck research@stockdeck.io"}
        data = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            timeout=10, headers=headers,
        ).json()
        tu = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == tu:
                return str(entry["cik_str"]).zfill(10)
        return None
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_sec_8k_text(ticker: str, year: int) -> str | None:
    """
    Fetch the annual earnings press release (Exhibit 99.x) from an 8-K
    filed by the company around Q4 of `year` or Q1 of `year+1`.
    Returns plain text, or None if not found.
    """
    headers = {"User-Agent": "StockDeck research@stockdeck.io"}
    cik = _fetch_cik(ticker)
    if not cik:
        return None

    try:
        subs = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            timeout=10, headers=headers,
        ).json()
    except Exception:
        return None

    recent = subs.get("filings", {}).get("recent", {})
    forms       = recent.get("form", [])
    dates       = recent.get("filingDate", [])
    accessions  = recent.get("accessionNumber", [])

    # Prefer Q4 annual earnings releases (Oct–Dec of `year` or Jan–Mar of `year+1`)
    candidates: list[tuple[str, str]] = []
    for form, date, acc in zip(forms, dates, accessions):
        if form != "8-K":
            continue
        try:
            d_year = int(date[:4])
            d_month = int(date[5:7])
        except ValueError:
            continue
        if (d_year == year and d_month >= 10) or (d_year == year + 1 and d_month <= 3):
            candidates.append((date, acc))

    # Broader fallback: any 8-K in the year
    if not candidates:
        for form, date, acc in zip(forms, dates, accessions):
            if form == "8-K" and str(year) in date[:4]:
                candidates.append((date, acc))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    cik_int = int(cik)

    for _, acc in candidates[:4]:
        acc_clean = acc.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/"
        try:
            idx_resp = requests.get(f"{base}{acc_clean}-index.htm", timeout=10, headers=headers)
            # Find ex-99 exhibit href
            matches = re.findall(r'href="([^"]*ex[- _]?99[^"]*\.(htm|txt|html))"',
                                 idx_resp.text, re.IGNORECASE)
            if not matches:
                continue
            rel = matches[0][0]
            doc_url = f"https://www.sec.gov{rel}" if rel.startswith("/") else base + rel
            doc_resp = requests.get(doc_url, timeout=15, headers=headers)
            text = _strip_html(doc_resp.text)
            if len(text) > 400:
                return text[:20000]
        except Exception:
            continue

    return None


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_fmp_transcript(ticker: str, year: int, fmp_key: str) -> str | None:
    """
    Fetch the best available earnings call transcript for `year` via FMP.
    Tries Q4 → Q3 → Q2 → Q1 order (Q4 covers full-year results).
    """
    for quarter in [4, 3, 2, 1]:
        try:
            url = (
                f"https://financialmodelingprep.com/api/v3/earning_call_transcript/"
                f"{ticker}?year={year}&quarter={quarter}&apikey={fmp_key}"
            )
            data = requests.get(url, timeout=15).json()
            if isinstance(data, list) and data and data[0].get("content"):
                return data[0]["content"]
        except Exception:
            pass
    return None


def _analyze_with_claude(
    text: str,
    ticker: str,
    year: int,
    yoy_pct: float,
    anthropic_key: str,
) -> list[dict] | None:
    """
    Call Claude to extract structured revenue drivers from transcript/release.
    Returns a list of dicts: {"label": str, "direction": "positive"|"negative"|"neutral"}.
    """
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=anthropic_key)

        direction_word = "growth" if yoy_pct >= 0 else "decline"
        prompt = (
            f"You are a financial analyst. {ticker} reported revenue {direction_word} "
            f"of {yoy_pct:+.1f}% in {year}.\n\n"
            f"Based on the following earnings transcript / press release excerpt, "
            f"identify the 5-7 most important factors that drove revenue in {year}.\n\n"
            f"Return ONLY a valid JSON array. Each element must be an object with:\n"
            f'  "label": concise bullet (max 130 chars, start with a verb in past tense)\n'
            f'  "direction": "positive", "negative", or "neutral"\n\n'
            f"Example:\n"
            f'[{{"label": "iPhone unit sales grew 8% driven by strong upgrade cycle in Asia.", "direction": "positive"}}]\n\n'
            f"--- TEXT START ---\n{text[:9000]}\n--- TEXT END ---"
        )

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not match:
            return None
        factors = json.loads(match.group())
        return [
            {
                "label": str(f.get("label", "")),
                "direction": str(f.get("direction", "neutral")),
            }
            for f in factors
            if f.get("label")
        ]
    except Exception:
        return None


def get_revenue_drivers(
    ticker: str,
    year: int,
    yoy_pct: float,
    fmp_key: str,
    anthropic_key: str,
) -> dict:
    """
    Orchestrate fetching transcript/release and (optionally) AI analysis.
    Returns:
        {
          "source": str,          # "FMP Transcript" | "SEC 8-K Release" | None
          "factors": list[dict],  # [{"label": str, "direction": str}]
          "ai_powered": bool,
          "error": str | None,
        }
    """
    text: str | None = None
    source: str | None = None

    # 1. Try FMP transcript (highest quality)
    if fmp_key:
        text = _fetch_fmp_transcript(ticker, year, fmp_key)
        if text:
            source = "Earnings Call Transcript (FMP)"

    # 2. Fallback: SEC EDGAR 8-K press release (always free)
    if not text:
        text = _fetch_sec_8k_text(ticker, year)
        if text:
            source = "Earnings Press Release (SEC EDGAR)"

    if not text:
        return {"source": None, "factors": [], "ai_powered": False,
                "error": "No transcript or press release found for this year."}

    # 3. AI-powered analysis
    if anthropic_key:
        factors = _analyze_with_claude(text, ticker, year, yoy_pct, anthropic_key)
        if factors:
            return {"source": source, "factors": factors, "ai_powered": True, "error": None}

    # 4. Keyword-based fallback
    sentences = _extract_key_sentences(text)
    if not sentences:
        return {"source": source, "factors": [], "ai_powered": False,
                "error": "Could not extract key sentences from document."}

    factors = [{"label": s, "direction": "neutral"} for s in sentences]
    return {"source": source, "factors": factors, "ai_powered": False, "error": None}


# ─── Session State ─────────────────────────────────────────────────────────────

for _k, _v in [
    ("stock_data", None),
    ("current_ticker", "AAPL"),
    ("last_loaded", ""),
    ("fmp_key", ""),
    ("anthropic_key", ""),
    ("load_error", ""),
    ("analysis_year", None),
    ("analysis_result", None),
    ("analysis_ticker", ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─── Top Bar ──────────────────────────────────────────────────────────────────

col_logo, _, col_gear = st.columns([3, 8, 1])

with col_logo:
    st.markdown(
        '<span style="font-size:0.7rem; letter-spacing:0.35em; color:#555; '
        'font-weight:700; text-transform:uppercase;">◈ STOCK DECK</span>',
        unsafe_allow_html=True,
    )

with col_gear:
    with st.popover("⚙", use_container_width=False):
        st.markdown(
            '<p style="font-size:0.72rem; letter-spacing:0.2em; color:#666; '
            'text-transform:uppercase; margin:0 0 1rem 0;">API SETTINGS</p>',
            unsafe_allow_html=True,
        )

        # FMP Key
        st.markdown(
            '<p style="font-size:0.68rem; color:#555; letter-spacing:0.12em; '
            'text-transform:uppercase; margin:0 0 0.3rem 0;">Financial Modeling Prep</p>',
            unsafe_allow_html=True,
        )
        new_fmp_key = st.text_input(
            "FMP API Key",
            value=st.session_state["fmp_key"],
            type="password",
            placeholder="Optional — unlocks 10-year history + transcripts",
            help="Get a free key at financialmodelingprep.com",
            label_visibility="collapsed",
        )
        st.markdown(
            '<p style="font-size:0.68rem; color:#444; margin:0.2rem 0 1rem 0;">'
            "Without key: ~4 yrs (Yahoo Finance)<br>"
            "With key: up to 10 yrs + earnings transcripts</p>",
            unsafe_allow_html=True,
        )

        # Anthropic Key
        st.markdown(
            '<p style="font-size:0.68rem; color:#555; letter-spacing:0.12em; '
            'text-transform:uppercase; margin:0 0 0.3rem 0;">Anthropic (Claude AI)</p>',
            unsafe_allow_html=True,
        )
        new_anthropic_key = st.text_input(
            "Anthropic API Key",
            value=st.session_state["anthropic_key"],
            type="password",
            placeholder="Optional — AI analysis of revenue drivers",
            help="Get a key at console.anthropic.com",
            label_visibility="collapsed",
        )
        st.markdown(
            '<p style="font-size:0.68rem; color:#444; margin:0.2rem 0 0 0;">'
            "With key: structured AI analysis of transcripts<br>"
            "Without: keyword extraction from filings</p>",
            unsafe_allow_html=True,
        )

        if new_fmp_key != st.session_state["fmp_key"]:
            st.session_state["fmp_key"] = new_fmp_key
            st.session_state["stock_data"] = None
            st.session_state["last_loaded"] = ""
            st.session_state["analysis_result"] = None
            _fetch_yf.clear()
            _fetch_fmp.clear()

        if new_anthropic_key != st.session_state["anthropic_key"]:
            st.session_state["anthropic_key"] = new_anthropic_key
            st.session_state["analysis_result"] = None

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Ticker Search Form ────────────────────────────────────────────────────────

with st.form("ticker_form", clear_on_submit=False):
    # vertical_alignment="bottom" aligns Load button baseline with input field
    fcol1, fcol2, fcol3 = st.columns([4, 1, 6], vertical_alignment="bottom")
    with fcol1:
        ticker_input = st.text_input(
            "ticker",
            value=st.session_state["current_ticker"],
            placeholder="AAPL",
            label_visibility="collapsed",
            max_chars=10,
        )
    with fcol2:
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
            st.session_state["analysis_result"] = None
            st.session_state["analysis_year"] = None
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
        f'<p style="color:#ef4444; font-size:0.85rem; margin-top:0.5rem;">'
        f'No data found for <strong>{st.session_state["load_error"]}</strong>. '
        f"Check the ticker and try again.</p>",
        unsafe_allow_html=True,
    )

data = st.session_state["stock_data"]
if not data:
    st.stop()

# ─── Prepare Revenue Data ──────────────────────────────────────────────────────

currency     = data.get("currency", "USD")
company_name = data.get("name", st.session_state["current_ticker"])
sector       = data.get("sector", "")
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
    f'<div style="font-size:3.2rem; font-weight:900; letter-spacing:-0.04em; '
    f'color:#f5f5f5; line-height:1; margin-bottom:0.4rem;">{company_name}</div>'
    f'<div style="font-size:0.72rem; color:#555; letter-spacing:0.25em; '
    f'text-transform:uppercase; margin-bottom:2.5rem;">'
    f'{"  ·  ".join(subtitle_parts)}</div>',
    unsafe_allow_html=True,
)

# ─── Period + Year Selector row ────────────────────────────────────────────────

period_col, _, year_col = st.columns([5, 1, 3])

with period_col:
    st.markdown(
        '<div class="section-label">PERIOD</div>',
        unsafe_allow_html=True,
    )
    if len(sorted_years) == 1:
        start_yr = end_yr = sorted_years[0]
        st.markdown(
            f'<span style="font-size:0.9rem; color:#888;">{start_yr}</span>',
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

with year_col:
    st.markdown(
        '<div class="section-label">ANALYZE YEAR</div>',
        unsafe_allow_html=True,
    )
    # Will be populated after we know sel_years

sel_years = [y for y in sorted_years if start_yr <= y <= end_yr]
sel_revs  = [revenue_all[y] for y in sel_years]

if len(sel_years) < 2:
    st.info("Select a range of at least 2 years.")
    st.stop()

# Year-selector dropdown (in the already-opened column context above)
with year_col:
    # Exclude first year (no prior year to compare against)
    analyzable = list(reversed(sel_years[1:]))
    default_yr = (
        st.session_state["analysis_year"]
        if st.session_state["analysis_year"] in analyzable
        else analyzable[0]
    )
    chosen_year = st.selectbox(
        "analyze_year",
        options=analyzable,
        index=analyzable.index(default_yr),
        label_visibility="collapsed",
    )
    analyze_clicked = st.button("Analyze →", key="analyze_btn")

if analyze_clicked:
    st.session_state["analysis_year"] = chosen_year
    st.session_state["analysis_result"] = None   # clear cache on new request
    st.session_state["analysis_ticker"] = ticker_label

# ─── Layout: Chart + Metrics ───────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
col_chart, col_metrics = st.columns([4, 1], gap="large")

# ── Right column: CAGR + Latest YoY ──────────────────────────────────────────
with col_metrics:
    n_years    = end_yr - start_yr
    period_cagr = cagr(sel_revs[0], sel_revs[-1], n_years)

    if period_cagr is not None:
        cagr_pct     = period_cagr * 100
        cagr_color   = "#4ade80" if cagr_pct >= 0 else "#f87171"
        cagr_sign    = "+" if cagr_pct >= 0 else ""
        cagr_display = f"{cagr_sign}{cagr_pct:.1f}%"
    else:
        cagr_color   = "#555"
        cagr_display = "—"

    start_rev_str = fmt(sel_revs[0], currency)
    end_rev_str   = fmt(sel_revs[-1], currency)

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
            <div style="font-size:0.68rem; letter-spacing:0.25em; color:#777;
                text-transform:uppercase; margin-bottom:1.2rem;">CAGR</div>
            <div style="font-size:3rem; font-weight:900; color:{cagr_color};
                line-height:1; letter-spacing:-0.04em;">{cagr_display}</div>
            <div style="font-size:0.72rem; color:#555; margin-top:0.6rem;
                letter-spacing:0.05em;">{start_yr} – {end_yr}</div>
            <div style="
                font-size:0.68rem; color:#555;
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

    prev_rev, last_rev = sel_revs[-2], sel_revs[-1]
    latest_yoy  = (last_rev - prev_rev) / prev_rev * 100 if prev_rev else 0
    yoy_color   = "#4ade80" if latest_yoy >= 0 else "#f87171"
    yoy_sign    = "+" if latest_yoy >= 0 else ""

    st.markdown(
        f"""
        <div style="
            background:#0c0c0c;
            border:1px solid #131313;
            border-radius:12px;
            padding:1.5rem;
            text-align:center;
        ">
            <div style="font-size:0.68rem; letter-spacing:0.25em; color:#777;
                text-transform:uppercase; margin-bottom:1rem;">LATEST YoY</div>
            <div style="font-size:2.4rem; font-weight:800; color:{yoy_color};
                line-height:1; letter-spacing:-0.03em;">
                {yoy_sign}{latest_yoy:.1f}%
            </div>
            <div style="font-size:0.68rem; color:#555; margin-top:0.5rem;">
                {sel_years[-2]} → {sel_years[-1]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Left column: Bar chart + YoY chips ───────────────────────────────────────
with col_chart:
    analysis_yr = st.session_state.get("analysis_year")

    bar_colors: list[str] = []
    for i, rev in enumerate(sel_revs):
        if i == 0:
            bar_colors.append("#1c1c1c")
        else:
            growth = (rev - sel_revs[i - 1]) / sel_revs[i - 1] if sel_revs[i - 1] else 0
            bar_colors.append("#22c55e" if growth >= 0 else "#ef4444")

    # Highlight the selected analysis year
    highlight_colors = []
    for yr, col in zip(sel_years, bar_colors):
        if yr == analysis_yr:
            highlight_colors.append("#3b82f6")   # blue highlight
        else:
            highlight_colors.append(col)

    max_rev = max(sel_revs)
    if max_rev >= 1e12:
        unit, unit_label = 1e12, "Revenue (USD Trillions)"
    elif max_rev >= 1e9:
        unit, unit_label = 1e9, "Revenue (USD Billions)"
    else:
        unit, unit_label = 1e6, "Revenue (USD Millions)"

    rev_norm   = [r / unit for r in sel_revs]
    bar_labels = [fmt(r, currency) for r in sel_revs]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=sel_years,
            y=rev_norm,
            marker=dict(color=highlight_colors, line=dict(width=0)),
            text=bar_labels,
            textposition="outside",
            textfont=dict(size=11, color="#aaaaaa", family="Inter"),
            hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            width=0.52,
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#888"),
        height=400,
        margin=dict(l=0, r=10, t=40, b=10),
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False,
            tickvals=sel_years,
            ticktext=[str(y) for y in sel_years],
            tickfont=dict(size=13, color="#888"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#0f0f0f",
            gridwidth=1,
            showline=False,
            zeroline=False,
            tickfont=dict(size=11, color="#666"),
            title=dict(
                text=unit_label,
                font=dict(size=10, color="#666"),
            ),
        ),
        bargap=0.35,
        showlegend=False,
        title=dict(
            text="ANNUAL REVENUE",
            font=dict(size=10, color="#555", family="Inter"),
            x=0,
            xanchor="left",
            y=0.99,
            yanchor="top",
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── YoY Growth chips ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="section-label" style="margin-top:0.1rem;">YEAR-OVER-YEAR GROWTH</div>',
        unsafe_allow_html=True,
    )

    yoy_cols = st.columns(len(sel_years))
    for i in range(1, len(sel_years)):
        pct = (
            (sel_revs[i] - sel_revs[i - 1]) / sel_revs[i - 1] * 100
            if sel_revs[i - 1] else 0
        )
        is_pos   = pct >= 0
        color    = "#4ade80" if is_pos else "#f87171"
        sign     = "+" if is_pos else ""
        is_sel   = sel_years[i] == analysis_yr
        border   = "border:1px solid #1e3a8a;" if is_sel else "border:1px solid #131313;"
        with yoy_cols[i]:
            st.markdown(
                f'<div style="background:#0c0c0c; {border} '
                f'border-radius:8px; padding:10px 4px; text-align:center;">'
                f'<div style="font-size:0.62rem; color:#888; letter-spacing:0.15em; '
                f'text-transform:uppercase; margin-bottom:5px;">{sel_years[i]}</div>'
                f'<div style="font-size:0.95rem; font-weight:700; color:{color}; '
                f'letter-spacing:-0.01em;">{sign}{pct:.1f}%</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

# ─── Revenue Drivers Analysis ──────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

if st.session_state.get("analysis_year") is None:
    st.markdown(
        '<div style="font-size:0.78rem; color:#444; text-align:center; padding:1.5rem 0;">'
        'Select a year above and click <strong style="color:#666;">Analyze →</strong> '
        'to see revenue drivers from earnings transcripts and press releases.</div>',
        unsafe_allow_html=True,
    )
else:
    a_year  = st.session_state["analysis_year"]
    a_tick  = st.session_state.get("analysis_ticker", ticker_label)

    # Compute YoY for the analysis year
    if a_year in sel_years and sel_years.index(a_year) > 0:
        idx_a    = sel_years.index(a_year)
        a_rev    = sel_revs[idx_a]
        a_prev   = sel_revs[idx_a - 1]
        a_yoy    = (a_rev - a_prev) / a_prev * 100 if a_prev else 0
        a_sign   = "+" if a_yoy >= 0 else ""
        a_color  = "#4ade80" if a_yoy >= 0 else "#f87171"
    else:
        a_yoy   = 0.0
        a_sign  = ""
        a_color = "#888"
        a_rev   = 0.0

    # Fetch/run analysis only when explicitly requested or already cached
    result = st.session_state.get("analysis_result")
    if result is None and a_tick == ticker_label:
        with st.spinner("Fetching earnings data…"):
            result = get_revenue_drivers(
                ticker_label,
                a_year,
                a_yoy,
                st.session_state["fmp_key"],
                st.session_state["anthropic_key"],
            )
        st.session_state["analysis_result"] = result

    if result:
        # Header
        ai_badge = (
            '<span style="font-size:0.62rem; background:#1e3a5f; color:#60a5fa; '
            'border-radius:4px; padding:2px 7px; letter-spacing:0.1em; '
            'font-weight:600; margin-left:0.8rem;">AI</span>'
            if result.get("ai_powered") else ""
        )
        source_txt = result.get("source") or "—"

        st.markdown(
            f'<div style="margin-bottom:1.2rem;">'
            f'<span style="font-size:0.72rem; letter-spacing:0.25em; color:#666; '
            f'text-transform:uppercase; font-weight:700;">REVENUE DRIVERS</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:1.1rem; font-weight:800; color:#ddd;">{a_year}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:1rem; font-weight:700; color:{a_color};">'
            f'{a_sign}{a_yoy:.1f}%</span>'
            f'{ai_badge}'
            f'<div style="font-size:0.65rem; color:#3a3a3a; margin-top:0.3rem; '
            f'letter-spacing:0.1em;">SOURCE: {source_txt.upper()}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if result.get("error") and not result.get("factors"):
            st.markdown(
                f'<div style="font-size:0.82rem; color:#555; padding:1rem 0;">'
                f'{result["error"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            for factor in result.get("factors", []):
                direction = factor.get("direction", "neutral")
                css_class = {
                    "positive": "factor-card positive",
                    "negative": "factor-card negative",
                }.get(direction, "factor-card neutral")
                label = factor.get("label", "")
                icon  = {"positive": "↑", "negative": "↓", "neutral": "→"}.get(direction, "→")
                st.markdown(
                    f'<div class="{css_class}">'
                    f'<span style="color:#555; margin-right:0.5rem;">{icon}</span>'
                    f'{label}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if not result.get("ai_powered") and st.session_state["anthropic_key"] == "":
                st.markdown(
                    '<div style="font-size:0.68rem; color:#3a3a3a; margin-top:0.8rem;">'
                    'Add an Anthropic key in ⚙ settings for structured AI analysis.</div>',
                    unsafe_allow_html=True,
                )

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:0.62rem; color:#333; text-align:right; '
    'letter-spacing:0.15em; text-transform:uppercase;">'
    "DATA: YAHOO FINANCE · FINANCIAL MODELING PREP · SEC EDGAR</div>",
    unsafe_allow_html=True,
)
