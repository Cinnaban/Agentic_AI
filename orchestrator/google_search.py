"""Google Programmable Search (Custom Search JSON API) as a last-resort financial records source.

Keys come from the environment only: GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID.
Disabled until both are set. Calls are cached on disk and capped per day (free tier is 100/day).
Snippets are weak evidence: values are extracted only from explicit statements and labelled unverified.
"""
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path

import requests

ENDPOINT = "https://www.googleapis.com/customsearch/v1"
CACHE_DIR = Path(os.getenv("GOOGLE_SEARCH_CACHE_DIR", "runtime/google_search"))
DAILY_LIMIT = int(os.getenv("GOOGLE_SEARCH_DAILY_LIMIT", "90"))
CACHE_TTL = 7 * 86400
LABEL = "Google search (unverified)"

_PERIOD = r"(?:quarter|three months)\s+ended\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})"
_EPS = r"(?:diluted\s+)?(?:EPS|earnings per (?:diluted )?share)[^$\d-]{0,40}\$?\s?(-?\d+\.\d{1,2})"


def configured():
    return bool(os.getenv("GOOGLE_SEARCH_API_KEY") and os.getenv("GOOGLE_SEARCH_ENGINE_ID"))


def _quota_file():
    return CACHE_DIR / "quota.json"


def _quota_used():
    try:
        data = json.loads(_quota_file().read_text())
        return data["count"] if data.get("day") == date.today().isoformat() else 0
    except (OSError, ValueError, KeyError):
        return 0


def _count_call():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _quota_file().write_text(json.dumps({"day": date.today().isoformat(), "count": _quota_used() + 1}))


def search(query, num=5):
    """List of {title, link, snippet}; [] when unconfigured, over quota, or on any failure."""
    if not configured():
        return []
    key = re.sub(r"[^a-z0-9]+", "_", query.lower())[:100] + f"_{num}"
    cached = CACHE_DIR / f"{key}.json"
    try:
        if cached.exists() and time.time() - cached.stat().st_mtime < CACHE_TTL:
            return json.loads(cached.read_text())
    except (OSError, ValueError):
        pass
    if _quota_used() >= DAILY_LIMIT:
        return []
    try:
        _count_call()
        response = requests.get(ENDPOINT, timeout=15, params={
            "key": os.environ["GOOGLE_SEARCH_API_KEY"], "cx": os.environ["GOOGLE_SEARCH_ENGINE_ID"],
            "q": query, "num": max(1, min(num, 10))})
        response.raise_for_status()
        items = [{"title": i.get("title", ""), "link": i.get("link", ""), "snippet": i.get("snippet", "")}
                 for i in response.json().get("items", [])]
    except Exception:
        return []
    try:
        cached.write_text(json.dumps(items))
    except OSError:
        pass
    return items


def _parse_date(text):
    text = text.replace(".", "")
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_quarterly_eps(items):
    """{period_end: eps} only where one snippet names the quarter end date and a per-share figure."""
    found = {}
    for item in items:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        period = re.search(_PERIOD, text)
        eps = re.search(_EPS, text, re.IGNORECASE)
        if period and eps:
            stamp = _parse_date(period.group(1))
            if stamp:
                found.setdefault(stamp, float(eps.group(1)))
    return found


def quarterly_eps(ticker):
    """Missing quarterly EPS leads for a ticker; empty unless configured and a snippet is explicit."""
    items = search(f"{ticker} quarterly results diluted earnings per share quarter ended", num=10)
    return extract_quarterly_eps(items)
