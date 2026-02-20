"""
Financial metrics via yfinance.

Fetches per-ticker:
- Forward P/E (NTM)
- EV/EBITDA
- ROE
- LTM price performance (1-year total return)

Uses concurrent.futures.ThreadPoolExecutor for parallel fetching.
All metrics gracefully fall back to None when unavailable.
"""

import concurrent.futures
import pandas as pd
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_metrics(ticker: str) -> dict:
    """
    Fetch financial metrics for a single ticker symbol.

    Returns:
        {
            "ticker": str,
            "company_name": str | None,
            "forward_pe": float | None,
            "ev_ebitda": float | None,
            "roe": float | None,       # already multiplied by 100 (percentage)
            "ltm_perf": float | None,  # percentage
            "error": str | None
        }
    """
    base = {
        "ticker": ticker,
        "company_name": None,
        "forward_pe": None,
        "ev_ebitda": None,
        "roe": None,
        "ltm_perf": None,
        "error": None,
    }

    if not ticker or ticker == "N/A":
        base["error"] = "No ticker"
        return base

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        if not info or info.get("quoteType") == "NONE":
            base["error"] = "Delisted / Not found"
            return base

        base["company_name"] = info.get("longName") or info.get("shortName")

        raw_pe = info.get("forwardPE")
        if raw_pe and isinstance(raw_pe, (int, float)) and raw_pe > 0:
            base["forward_pe"] = round(float(raw_pe), 1)

        raw_ev = info.get("enterpriseToEbitda")
        if raw_ev and isinstance(raw_ev, (int, float)) and raw_ev > 0:
            base["ev_ebitda"] = round(float(raw_ev), 1)

        raw_roe = info.get("returnOnEquity")
        if raw_roe is not None and isinstance(raw_roe, (int, float)):
            base["roe"] = round(float(raw_roe) * 100, 1)

        base["ltm_perf"] = _compute_ltm_performance(ticker)

    except Exception as e:
        base["error"] = f"Fetch error: {type(e).__name__}"

    return base


def _compute_ltm_performance(ticker: str) -> float | None:
    """
    Compute 1-year (LTM) total return for a ticker.

    Returns (last_close / first_close - 1) * 100, or None if insufficient data.
    Uses auto_adjust=True to account for splits and dividends.
    """
    try:
        hist = yf.download(
            ticker,
            period="1y",
            progress=False,
            auto_adjust=True,
            actions=False,
        )
        if hist is None or hist.empty or len(hist) < 5:
            return None

        # Handle multi-level columns from yf.download
        if isinstance(hist.columns, pd.MultiIndex):
            close_col = ("Close", ticker)
            if close_col not in hist.columns:
                # Try first Close column
                close_cols = [c for c in hist.columns if c[0] == "Close"]
                if not close_cols:
                    return None
                close_col = close_cols[0]
            prices = hist[close_col].dropna()
        else:
            if "Close" not in hist.columns:
                return None
            prices = hist["Close"].dropna()

        if len(prices) < 5:
            return None

        first = float(prices.iloc[0])
        last = float(prices.iloc[-1])
        if first <= 0:
            return None

        return round((last / first - 1) * 100, 1)
    except Exception:
        return None


def fetch_all_metrics(tickers: list[str]) -> dict[str, dict]:
    """
    Concurrently fetch metrics for all tickers.

    Uses ThreadPoolExecutor with up to 8 workers.
    Returns: {"AAPL": {metrics_dict}, "MSFT": {metrics_dict}, ...}
    """
    if not tickers:
        return {}

    unique_tickers = [t for t in set(tickers) if t and t != "N/A"]
    max_workers = min(8, len(unique_tickers)) if unique_tickers else 1

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_ticker_metrics, t): t
            for t in unique_tickers
        }
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                results[ticker] = future.result()
            except Exception as e:
                results[ticker] = {
                    "ticker": ticker,
                    "company_name": None,
                    "forward_pe": None,
                    "ev_ebitda": None,
                    "roe": None,
                    "ltm_perf": None,
                    "error": str(e),
                }

    return results


def build_display_dataframe(
    portfolio_df: pd.DataFrame,
    ticker_map: dict[str, str | None],
    metrics: dict[str, dict],
) -> pd.DataFrame:
    """
    Merge portfolio data with financial metrics into the final display DataFrame.

    portfolio_df columns: [cusip, name, value_usd, shares, weight_pct, qoq_pct, is_new, ...]
    ticker_map: {cusip: ticker or None}
    metrics: {ticker: metrics_dict}

    Returns DataFrame sorted by weight_pct descending, with columns:
    [Company, Ticker, Weight %, QoQ %, Forward P/E, EV/EBITDA, ROE %, 1Y Return %, Value ($M)]
    """
    rows = []
    for _, row in portfolio_df.iterrows():
        cusip = row["cusip"]
        ticker = ticker_map.get(cusip)
        put_call = row.get("put_call", "")

        # Build company display name
        company_name = row["name"]
        if put_call and put_call.strip():
            company_name = f"{company_name} ({put_call.upper()})"

        # Get financial metrics
        m = metrics.get(ticker, {}) if ticker else {}
        yahoo_name = m.get("company_name")
        display_name = yahoo_name if yahoo_name else company_name

        qoq = row.get("qoq_pct")
        is_new = row.get("is_new", False)

        rows.append({
            "Company": display_name,
            "Ticker": ticker if ticker else "N/A",
            "Weight %": round(row["weight_pct"], 2),
            "QoQ %": round(float(qoq), 1) if pd.notna(qoq) and qoq is not None else None,
            "Is New": bool(is_new),
            "Forward P/E": m.get("forward_pe"),
            "EV/EBITDA": m.get("ev_ebitda"),
            "ROE %": m.get("roe"),
            "1Y Return %": m.get("ltm_perf"),
            "Value ($M)": round(row["value_usd"] / 1_000_000, 1),
            "CUSIP": cusip,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("Weight %", ascending=False).reset_index(drop=True)
    return df
