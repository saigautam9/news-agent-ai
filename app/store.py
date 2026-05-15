"""
A tiny JSON-file "database" (data/log.json) for deduplication and history.
Committed back to the repo by GitHub Actions, so it costs nothing and lets the
app remember what it has already covered.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path


def fingerprint(headline: str) -> str:
    """A normalized fingerprint of a headline, used to detect repeat stories."""
    words = re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip().split()
    return " ".join(words[:10])


def _day(offset_days: int = 0) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def load_log(file: str | Path) -> dict:
    try:
        raw = json.loads(Path(file).read_text())
        entries = raw.get("entries", [])
        return {"entries": entries if isinstance(entries, list) else []}
    except (OSError, json.JSONDecodeError):
        return {"entries": []}


def save_log(file: str | Path, store: dict) -> None:
    """Save the log, trimmed to the last 30 days (and 400 entries) to stay small."""
    cutoff = _day(-30)
    entries = [e for e in store["entries"] if e.get("date", "") >= cutoff][-400:]
    Path(file).write_text(json.dumps({"entries": entries}, indent=2) + "\n")


def seen_recently(store: dict, headline: str, days: int = 2) -> bool:
    """True if a story with this headline was already logged in the last `days`."""
    fp = fingerprint(headline)
    cutoff = _day(-(days - 1))
    return any(
        e.get("fp") == fp and e.get("date", "") >= cutoff for e in store["entries"]
    )


def log_story(store: dict, entry: dict) -> None:
    """Add a story to the log (skipped if the same story is already logged today)."""
    entry_date = entry.get("date") or _day(0)
    fp = fingerprint(entry["headline"])
    if any(
        e.get("fp") == fp and e.get("date") == entry_date for e in store["entries"]
    ):
        return
    store["entries"].append({**entry, "fp": fp, "date": entry_date})


def medium_last_week(store: dict) -> list[dict]:
    """Unique MEDIUM-severity stories logged in the last 7 days — the weekly roundup."""
    cutoff = _day(-6)
    seen: set[str] = set()
    out: list[dict] = []
    for e in store["entries"]:
        if (
            e.get("date", "") < cutoff
            or e.get("severity") != "MEDIUM"
            or e.get("fp") in seen
        ):
            continue
        seen.add(e["fp"])
        out.append(e)
    return out
