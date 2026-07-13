"""
Backfill the news warehouse with real historical headlines from **GDELT** —
the free global news database (no API key). It walks back over time windows,
pulls major news for each window, buckets each article into a Deep Signal desk
by keyword, scores a lightweight severity/urgency, and loads it into Postgres —
so the Signal Engine + RAG memory have real, date-spread history to work with.

    python scripts/backfill_gdelt.py [days] [windows]   # default 90 days, 9 windows

Costs nothing and uses no LLM quota — pure public data + heuristics.
"""

from __future__ import annotations

import html
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import get_stats, persist_stories  # noqa: E402

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"

# One broad query covering all desks — we classify the results ourselves.
QUERY = (
    '(war OR sanctions OR military OR inflation OR "stock market" OR "interest rates" '
    'OR "artificial intelligence" OR semiconductor OR outbreak OR vaccine '
    'OR "climate change" OR wildfire OR election OR protest OR immigration) '
    'sourcelang:english'
)

DESK_KEYWORDS = {
    "Geopolitics": r"war|sanction|military|diplomacy|invasion|troops|missile|border|ceasefire|nato|nuclear",
    "Markets": r"inflation|stock|market|rate|recession|econom|fed |gdp|trade|bond|currency|tariff",
    "Technology": r"\bai\b|artificial intelligence|chip|semiconductor|software|cyber|tech|robot|data",
    "Health": r"health|disease|outbreak|vaccine|hospital|virus|pandemic|medical|drug",
    "Climate": r"climate|wildfire|flood|emission|drought|hurricane|heatwave|carbon|storm",
    "Society": r"election|protest|immigration|rights|court|vote|refugee|abortion|strike",
}
_DESK_RE = {d: re.compile(k, re.I) for d, k in DESK_KEYWORDS.items()}

_CRITICAL = re.compile(r"\b(war|attack|killed|dead|deaths|crisis|nuclear|invasion|crash|collapse|emergency|massacre)\b", re.I)
_HIGH = re.compile(r"\b(sanction|strike|surge|plunge|threat|conflict|outbreak|ban|recession|protest|shutdown|warning)\b", re.I)


def _classify(title: str) -> str:
    best, score = "Society", 0
    for desk, rx in _DESK_RE.items():
        n = len(rx.findall(title))
        if n > score:
            best, score = desk, n
    return best


def _severity(title: str) -> tuple[str, int]:
    if _CRITICAL.search(title):
        return "CRITICAL", 9
    if _HIGH.search(title):
        return "HIGH", 7
    return "MEDIUM", 5


def _fetch_window(start: datetime, end: datetime, maxrecords: int = 75) -> list[dict]:
    params = {
        "query": QUERY,
        "mode": "artlist", "format": "json", "maxrecords": maxrecords,
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    for attempt in range(3):
        try:
            r = requests.get(GDELT, params=params, timeout=45,
                             headers={"User-Agent": "deep-signal-backfill/1.0"})
            if r.status_code == 429:
                time.sleep(8 * (attempt + 1))
                continue
            r.raise_for_status()
            articles = r.json().get("articles", [])
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"    window fetch failed: {str(e)[:55]}")
                return []
            time.sleep(6)
    else:
        return []

    stories = []
    for a in articles:
        title = html.unescape(str(a.get("title", ""))).strip()
        if not title or len(title) < 12:
            continue
        try:
            date = datetime.strptime(str(a.get("seendate", ""))[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            date = start.date().isoformat()
        sev, urg = _severity(title)
        stories.append({
            "headline": title,
            "summary": f"Reported via {a.get('domain', 'news')}.",
            "domain": _classify(title), "severity": sev, "urgency": urg,
            "date": date, "mode": "backfill",
        })
    return stories


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    windows = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    step = timedelta(days=days / windows)
    print(f"[backfill] GDELT — {days} days in {windows} windows ...")
    before = get_stats().get("total", 0)

    all_stories: list[dict] = []
    now = datetime.utcnow()
    for i in range(windows):
        end = now - i * step
        start = end - step
        s = _fetch_window(start, end)
        print(f"  {start.date()} → {end.date()}  +{len(s)} articles")
        all_stories.extend(s)
        time.sleep(6)  # GDELT allows ~1 request / 5s

    persist_stories(all_stories, mode="backfill")
    after = get_stats().get("total", 0)
    print(f"\n[backfill] fetched {len(all_stories)} articles; warehouse {before} → {after} stories.")


if __name__ == "__main__":
    main()
