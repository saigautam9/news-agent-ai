"""
Analytics warehouse for NewsAgent AI — Neon **Postgres**.

The stories the multi-agent pipeline collects are persisted to a managed cloud
Postgres database (Neon). This module owns the schema, the ETL/migration that
loads the JSON story log + the ML corpus into Postgres, and the aggregate
analytics (volume, domain / severity mix, urgency, daily trend) served by the
`/api/stats` endpoint and the dashboard.

If `DATABASE_URL` is unset (pure local dev with no DB), the functions degrade
gracefully and report an empty warehouse instead of crashing.

Run the ETL:  python scripts/etl.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from app import config

ROOT = Path(__file__).resolve().parent.parent
LOG_JSON = ROOT / "data" / "log.json"
CORPUS_CSV = ROOT / "ml" / "data" / "corpus.csv"

SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    fp            TEXT PRIMARY KEY,
    date          DATE,
    domain        TEXT,
    severity      TEXT,
    severity_rank INT,
    urgency       DOUBLE PRECISION,
    mode          TEXT,
    headline      TEXT NOT NULL,
    summary       TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stories_date   ON stories (date);
CREATE INDEX IF NOT EXISTS idx_stories_domain ON stories (domain);
"""


def _connect():
    """Open a Postgres connection, or None if no DATABASE_URL is configured."""
    if not config.DATABASE_URL:
        return None
    import psycopg  # imported lazily so local-only dev needs no driver

    return psycopg.connect(config.DATABASE_URL)


def init_schema() -> bool:
    con = _connect()
    if con is None:
        return False
    with con:
        con.execute(_SCHEMA)
    con.close()
    return True


# --- EXTRACT + TRANSFORM (pure Python, no pandas) ---
def _extract() -> list[dict]:
    rows: list[dict] = []
    if LOG_JSON.exists():
        try:
            rows.extend(json.loads(LOG_JSON.read_text()).get("entries", []) or [])
        except json.JSONDecodeError:
            pass
    if CORPUS_CSV.exists():
        with open(CORPUS_CSV, newline="", encoding="utf-8") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def _transform(rows: list[dict]) -> list[tuple]:
    out: list[tuple] = []
    seen: set[str] = set()
    for r in rows:
        headline = str(r.get("headline") or "").strip()
        if not headline:
            continue
        fp = str(r.get("fp") or headline.lower())
        if fp in seen:
            continue
        seen.add(fp)

        severity = str(r.get("severity") or "MEDIUM").upper()
        if severity not in SEVERITY_RANK:
            severity = "MEDIUM"

        raw_urg = r.get("urgency")
        try:
            urgency = float(raw_urg) if raw_urg not in (None, "", "nan", "NaN") else None
        except (TypeError, ValueError):
            urgency = None

        d = str(r.get("date") or "")
        date = d if _DATE_RE.match(d) else None

        out.append((
            fp, date, str(r.get("domain") or "Unknown"),
            severity, SEVERITY_RANK[severity], urgency,
            str(r.get("mode") or "live"), headline, str(r.get("summary") or ""),
        ))
    return out


def log_story(entry: dict) -> None:
    """Upsert a single story into Postgres (called live by the pipeline)."""
    con = _connect()
    if con is None:
        return
    row = _transform([entry])
    if row:
        with con:
            con.execute(
                "INSERT INTO stories (fp,date,domain,severity,severity_rank,"
                "urgency,mode,headline,summary) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (fp) DO NOTHING",
                row[0],
            )
    con.close()


def migrate() -> dict:
    """ETL: load the JSON log + ML corpus into Postgres (idempotent upsert)."""
    con = _connect()
    if con is None:
        return {"rows": 0, "store": "none (DATABASE_URL not set)"}
    with con:
        con.execute(_SCHEMA)
        rows = _transform(_extract())
        if rows:
            con.cursor().executemany(
                "INSERT INTO stories (fp,date,domain,severity,severity_rank,"
                "urgency,mode,headline,summary) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (fp) DO NOTHING",
                rows,
            )
        total = con.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    con.close()
    return {"rows": total, "store": "neon-postgres"}


# `build_warehouse` kept as an alias so scripts/etl.py reads naturally.
build_warehouse = migrate


def get_stats() -> dict:
    """Aggregate analytics over the Postgres `stories` warehouse."""
    con = _connect()
    empty = {"total": 0, "by_domain": [], "by_severity": [], "daily_volume": []}
    if con is None:
        return empty
    with con:
        con.execute(_SCHEMA)
        total = con.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        if total == 0:
            con.close()
            return empty

        def q(sql):
            return con.execute(sql).fetchall()

        dmin, dmax = con.execute(
            "SELECT MIN(date), MAX(date) FROM stories WHERE date IS NOT NULL"
        ).fetchone()
        urg = con.execute(
            "SELECT AVG(urgency), MAX(urgency), COUNT(urgency) FROM stories"
        ).fetchone()

        stats = {
            "total": total,
            "date_range": [str(dmin) if dmin else None, str(dmax) if dmax else None],
            "high_or_critical": con.execute(
                "SELECT COUNT(*) FROM stories WHERE severity_rank >= 3"
            ).fetchone()[0],
            "urgency": {
                "avg": round(float(urg[0]), 2) if urg[0] is not None else None,
                "max": urg[1],
                "labelled": urg[2],
            },
            "by_domain": [
                {"domain": d, "count": c}
                for d, c in q(
                    "SELECT domain, COUNT(*) c FROM stories GROUP BY domain ORDER BY c DESC"
                )
            ],
            "by_severity": [
                {"severity": s, "count": c}
                for s, c, _ in q(
                    "SELECT severity, COUNT(*) c, MAX(severity_rank) r "
                    "FROM stories GROUP BY severity ORDER BY r DESC"
                )
            ],
            "daily_volume": [
                {"date": str(d), "count": c}
                for d, c in q(
                    "SELECT date, COUNT(*) c FROM stories "
                    "WHERE date IS NOT NULL GROUP BY date ORDER BY date"
                )
            ],
            "domain_severity": [
                {"domain": d, "severity": s, "count": c}
                for d, s, c in q(
                    "SELECT domain, severity, COUNT(*) c FROM stories "
                    "GROUP BY domain, severity ORDER BY c DESC LIMIT 12"
                )
            ],
        }
    con.close()
    return stats
