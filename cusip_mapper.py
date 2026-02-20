"""
CUSIP to ticker symbol mapping via OpenFIGI API.

Features:
- Persistent disk cache (cusip_cache.json) that survives app restarts
- Batch requests (25 CUSIPs per call without API key)
- US equity exchange preference filtering
- Exponential backoff on rate limit errors
"""

import json
import os
import time
import tempfile
import requests

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
CACHE_FILE = "cusip_cache.json"

# US equity exchange codes preferred for ticker selection
US_EQUITY_EXCHANGES = {"US", "UN", "UA", "UQ", "UR", "UT", "UW"}


def _load_disk_cache() -> dict:
    """Load the CUSIP cache from disk. Returns {} if not found or malformed."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_disk_cache(cache: dict) -> None:
    """Atomically write cache to disk using temp file + rename."""
    try:
        dir_name = os.path.dirname(os.path.abspath(CACHE_FILE))
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as f:
            json.dump(cache, f)
            tmp_path = f.name
        os.replace(tmp_path, CACHE_FILE)
    except OSError:
        pass  # Non-fatal: cache will just not persist this run


def _select_best_ticker(figi_results: list[dict]) -> str | None:
    """
    Select the best US equity ticker from a list of FIGI mapping results.
    Priority: US exchange + Equity market sector > any result > None
    """
    if not figi_results:
        return None

    # Filter to equity securities on US exchanges
    us_equity = [
        r for r in figi_results
        if r.get("exchCode") in US_EQUITY_EXCHANGES
        and r.get("marketSecDes", "").lower() == "equity"
    ]

    # Priority: NYSE > NASDAQ > AMEX > others
    exchange_priority = {"UN": 1, "UQ": 2, "UA": 3, "US": 4, "UW": 5, "UR": 6, "UT": 7}
    if us_equity:
        us_equity.sort(key=lambda r: exchange_priority.get(r.get("exchCode", ""), 99))
        ticker = us_equity[0].get("ticker")
        return ticker if ticker else None

    # Fallback: any result with a ticker
    for r in figi_results:
        ticker = r.get("ticker")
        if ticker:
            return ticker

    return None


def _post_openfigi_batch(cusip_batch: list[str], api_key: str | None) -> list[dict | None]:
    """
    POST a single batch of CUSIPs to OpenFIGI.
    Returns a list of raw result items (one per CUSIP), or None on failure.
    """
    payload = [
        {"idType": "ID_CUSIP", "idValue": cusip, "marketSecDes": "Equity"}
        for cusip in cusip_batch
    ]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    for attempt in range(4):
        try:
            resp = requests.post(
                OPENFIGI_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            if resp.status_code == 400:
                # Bad request — return None for all in batch
                return [None] * len(cusip_batch)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            if attempt < 3:
                time.sleep(2 ** attempt)
            else:
                return [None] * len(cusip_batch)

    return [None] * len(cusip_batch)


def map_cusips_to_tickers(
    cusips: list[str],
    api_key: str | None = None,
) -> dict[str, str | None]:
    """
    Map a list of CUSIP strings to ticker symbols.

    Returns dict: {"CUSIP": "TICKER" or None}
    None means no ticker found (options, warrants, foreign securities, etc.)

    Uses disk cache for previously resolved CUSIPs.
    Batches unknowns to OpenFIGI (25 per request without API key).
    """
    if not cusips:
        return {}

    cache = _load_disk_cache()
    result = {}
    unknowns = []

    for cusip in cusips:
        if cusip in cache:
            result[cusip] = cache[cusip]
        else:
            unknowns.append(cusip)

    if not unknowns:
        return result

    # Batch size: 25 without API key, 100 with key
    batch_size = 100 if api_key else 25

    for i in range(0, len(unknowns), batch_size):
        batch = unknowns[i: i + batch_size]
        raw_results = _post_openfigi_batch(batch, api_key)

        for cusip, raw in zip(batch, raw_results):
            if raw is None or "warning" in raw or "error" in raw:
                ticker = None
            else:
                data = raw.get("data", [])
                ticker = _select_best_ticker(data)

            result[cusip] = ticker
            cache[cusip] = ticker

        # Small delay between batches to respect rate limits
        if i + batch_size < len(unknowns):
            time.sleep(0.5)

    _save_disk_cache(cache)
    return result
