"""
SEC EDGAR API integration for 13F portfolio analysis.

Handles:
- Searching institutional investors by name
- Fetching 13F-HR filings for a given CIK
- Parsing the 13F XML information table
- Computing portfolio weights and QoQ position changes
"""

import time
import re
import requests
import pandas as pd
from lxml import etree
import streamlit as st

EDGAR_HEADERS = {
    "User-Agent": "13F Portfolio Analyzer / research tool contact@example.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}

# Rate limiting: max 8 requests/sec (SEC allows 10, we use 8 for safety)
_last_request_time = 0.0


def _rate_limited_get(url: str, timeout: int = 20, **kwargs) -> requests.Response:
    """GET with rate limiting and retries for SEC EDGAR."""
    global _last_request_time
    headers = kwargs.pop("headers", EDGAR_HEADERS)
    retries = 3
    for attempt in range(retries):
        elapsed = time.time() - _last_request_time
        if elapsed < 0.125:
            time.sleep(0.125 - elapsed)
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            _last_request_time = time.time()
            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                raise
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except requests.Timeout:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"Failed to GET {url} after {retries} attempts")


@st.cache_data(ttl=86400, show_spinner=False)
def load_company_tickers() -> pd.DataFrame:
    """
    Fetch the SEC company tickers JSON and return a DataFrame.
    Columns: cik_str (10-digit padded), ticker, title.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = _rate_limited_get(url)
    data = resp.json()
    rows = []
    for entry in data.values():
        cik_padded = str(entry["cik_str"]).zfill(10)
        rows.append({
            "cik_str": cik_padded,
            "ticker": entry.get("ticker", ""),
            "title": entry.get("title", "").upper(),
        })
    return pd.DataFrame(rows)


def _search_efts(query: str) -> list[dict]:
    """Search SEC EFTS full-text search for 13F-HR filers."""
    url = "https://efts.sec.gov/LATEST/search-index"
    params = {
        "q": f'"{query}"',
        "forms": "13F-HR",
        "dateRange": "custom",
        "startdt": "2020-01-01",
    }
    try:
        resp = _rate_limited_get(url, params=params)
        hits = resp.json().get("hits", {}).get("hits", [])
        results = []
        seen = set()
        for h in hits:
            src = h.get("_source", {})
            entity = src.get("entity_name", src.get("display_names", [""])[0] if src.get("display_names") else "")
            cik_raw = src.get("file_num", "") or ""
            # Try entity_id field
            entity_id = src.get("entity_id", "")
            if not entity_id:
                continue
            cik_padded = str(entity_id).zfill(10)
            if cik_padded not in seen and entity:
                seen.add(cik_padded)
                results.append({"name": entity.upper(), "cik": cik_padded})
        return results
    except Exception:
        return []


def search_filers(query: str) -> list[dict]:
    """
    Search for 13F institutional investors by name.

    Stage 1: Filter company_tickers.json (fast, local)
    Stage 2: EFTS API call if fewer than 3 results

    Returns list of {"name": str, "cik": str (10-digit padded)}
    """
    if not query or len(query.strip()) < 2:
        return []

    query_upper = query.upper().strip()
    df = load_company_tickers()
    mask = df["title"].str.contains(query_upper, na=False, regex=False)
    stage1 = [
        {"name": row["title"], "cik": row["cik_str"]}
        for _, row in df[mask].head(20).iterrows()
    ]

    results = stage1
    if len(results) < 3:
        stage2 = _search_efts(query)
        existing_ciks = {r["cik"] for r in results}
        for r in stage2:
            if r["cik"] not in existing_ciks:
                results.append(r)
                existing_ciks.add(r["cik"])

    return results[:20]


@st.cache_data(ttl=3600, show_spinner=False)
def get_submissions(cik_padded: str) -> dict:
    """
    Fetch the SEC submissions JSON for a given CIK.
    Returns the raw JSON dict with filing metadata.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp = _rate_limited_get(url)
    return resp.json()


def get_13f_filings(submissions: dict) -> list[dict]:
    """
    Extract 13F-HR filings from a submissions dict, sorted newest first.
    Returns list of {"accessionNumber": str, "filingDate": str, "primaryDocument": str}
    """
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    docs = recent.get("primaryDocument", [])

    filings = []
    for i, form in enumerate(forms):
        if form == "13F-HR":
            filings.append({
                "accessionNumber": accessions[i],
                "filingDate": dates[i],
                "primaryDocument": docs[i] if i < len(docs) else "",
            })

    # Sort newest first
    filings.sort(key=lambda x: x["filingDate"], reverse=True)
    return filings


def _get_filing_index(cik_padded: str, accession_number: str) -> list[dict]:
    """
    Fetch the filing index JSON to find the XML information table document.
    Returns list of document dicts from the EDGAR filing index.
    """
    cik_int = str(int(cik_padded))
    accn_nodash = accession_number.replace("-", "")
    url = f"https://data.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/{accession_number}-index.json"
    try:
        resp = _rate_limited_get(url)
        return resp.json().get("documents", [])
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_13f_xml(cik_padded: str, accession_number: str) -> str:
    """
    Fetch the XML information table for a given 13F-HR filing.
    Returns raw XML string.
    """
    cik_int = str(int(cik_padded))
    accn_nodash = accession_number.replace("-", "")
    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accn_nodash}/"

    # Try to find the XML document via filing index
    docs = _get_filing_index(cik_padded, accession_number)
    xml_url = None
    for doc in docs:
        doc_type = doc.get("type", "").upper()
        filename = doc.get("filename", "")
        if "INFORMATION TABLE" in doc_type or filename.lower().endswith(".xml"):
            if "primary_doc" not in filename.lower():
                xml_url = base_url + filename
                break

    # Fallback: try common filenames
    if not xml_url:
        for candidate in ["infotable.xml", "informationtable.xml", "form13fInfoTable.xml"]:
            candidate_url = base_url + candidate
            try:
                resp = _rate_limited_get(candidate_url)
                if resp.status_code == 200:
                    xml_url = candidate_url
                    break
            except Exception:
                continue

    if not xml_url:
        raise ValueError(f"Could not find XML information table for accession {accession_number}")

    resp = _rate_limited_get(xml_url)
    return resp.text


def parse_13f_xml(xml_content: str) -> pd.DataFrame:
    """
    Parse 13F XML information table into a DataFrame.

    Returns DataFrame with columns:
    [name, cusip, value_usd, shares, share_type, put_call]

    Aggregates duplicate CUSIPs by summing value_usd and shares.
    """
    try:
        root = etree.fromstring(xml_content.encode("utf-8"))
    except etree.XMLSyntaxError:
        # Try stripping BOM or encoding declaration
        cleaned = re.sub(r'<\?xml[^>]+\?>', '', xml_content).strip()
        root = etree.fromstring(cleaned.encode("utf-8"))

    # Handle namespace
    ns_match = re.search(r'xmlns="([^"]+)"', xml_content)
    ns = {"t": ns_match.group(1)} if ns_match else {}

    def find_text(element, tag):
        """Find text in element with or without namespace."""
        if ns:
            el = element.find(f"t:{tag}", ns)
        else:
            el = element.find(tag)
        # Try case variations
        if el is None:
            for child in element:
                local = etree.QName(child.tag).localname.lower()
                if local == tag.lower():
                    el = child
                    break
        return el.text.strip() if el is not None and el.text else ""

    def find_nested(element, parent_tag, child_tag):
        if ns:
            parent = element.find(f"t:{parent_tag}", ns)
        else:
            parent = element.find(parent_tag)
        if parent is None:
            for child in element:
                if etree.QName(child.tag).localname.lower() == parent_tag.lower():
                    parent = child
                    break
        if parent is None:
            return ""
        return find_text(parent, child_tag)

    rows = []
    # Find all infoTable elements regardless of namespace
    all_elements = root.iter()
    info_tables = [el for el in all_elements if etree.QName(el.tag).localname == "infoTable"]

    for info in info_tables:
        name = find_text(info, "nameOfIssuer")
        cusip = find_text(info, "cusip")
        value_str = find_text(info, "value")
        shares_str = find_nested(info, "shrsOrPrnAmt", "sshPrnamt")
        share_type = find_nested(info, "shrsOrPrnAmt", "sshPrnamtType")
        put_call = find_text(info, "putCall")

        try:
            value_usd = float(value_str.replace(",", "")) if value_str else 0.0
        except ValueError:
            value_usd = 0.0

        try:
            shares = float(shares_str.replace(",", "")) if shares_str else 0.0
        except ValueError:
            shares = 0.0

        if cusip:
            rows.append({
                "name": name,
                "cusip": cusip,
                "value_usd": value_usd,
                "shares": shares,
                "share_type": share_type,
                "put_call": put_call,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Normalize values: detect if reported in thousands
    # (pre-2023 SEC format was in $thousands)
    avg_value = df["value_usd"].mean()
    if avg_value < 50_000 and avg_value > 0:
        df["value_usd"] = df["value_usd"] * 1000

    # Aggregate duplicate CUSIPs (same security reported multiple times)
    agg = df.groupby("cusip").agg(
        name=("name", "first"),
        value_usd=("value_usd", "sum"),
        shares=("shares", "sum"),
        share_type=("share_type", "first"),
        put_call=("put_call", "first"),
    ).reset_index()

    return agg


def build_portfolio(cik_padded: str) -> tuple[pd.DataFrame, dict]:
    """
    Orchestrate fetching and parsing of the two most recent 13F-HR filings.

    Returns:
        portfolio_df: DataFrame with columns:
            [cusip, name, value_usd, shares, share_type, put_call,
             weight_pct, qoq_pct, is_new]
        meta: dict with filer_name, filing_date, total_value_usd, prev_filing_date
    """
    submissions = get_submissions(cik_padded)
    filer_name = submissions.get("name", "Unknown")
    filings = get_13f_filings(submissions)

    if not filings:
        raise ValueError(f"No 13F-HR filings found for {filer_name}")

    # Fetch current filing
    current_filing = filings[0]
    xml_current = fetch_13f_xml(cik_padded, current_filing["accessionNumber"])
    current_df = parse_13f_xml(xml_current)

    if current_df.empty:
        raise ValueError(f"Could not parse holdings from the latest 13F filing for {filer_name}")

    total_value = current_df["value_usd"].sum()
    if total_value == 0:
        raise ValueError("Portfolio total value is zero — filing may be malformed")

    current_df["weight_pct"] = (current_df["value_usd"] / total_value) * 100

    # Fetch previous filing for QoQ comparison
    prev_filing_date = None
    if len(filings) >= 2:
        prev_filing = filings[1]
        prev_filing_date = prev_filing["filingDate"]
        try:
            xml_prev = fetch_13f_xml(cik_padded, prev_filing["accessionNumber"])
            prev_df = parse_13f_xml(xml_prev)
            if not prev_df.empty:
                prev_df = prev_df[["cusip", "shares"]].rename(columns={"shares": "shares_prev"})
                merged = current_df.merge(prev_df, on="cusip", how="left")
                merged["is_new"] = merged["shares_prev"].isna()
                merged["qoq_pct"] = (
                    (merged["shares"] - merged["shares_prev"]) / merged["shares_prev"] * 100
                ).where(~merged["is_new"])
                current_df = merged
            else:
                current_df["qoq_pct"] = None
                current_df["is_new"] = False
        except Exception:
            current_df["qoq_pct"] = None
            current_df["is_new"] = False
    else:
        current_df["qoq_pct"] = None
        current_df["is_new"] = False

    meta = {
        "filer_name": filer_name,
        "filing_date": current_filing["filingDate"],
        "total_value_usd": total_value,
        "prev_filing_date": prev_filing_date,
    }

    # Sort by weight descending
    current_df = current_df.sort_values("weight_pct", ascending=False).reset_index(drop=True)
    return current_df, meta
