"""
ETL job — build the DuckDB analytics warehouse from the news the pipeline
collects (data/log.json + ml/data/corpus.csv) and print a summary.

    python scripts/etl.py

Run it after briefings to refresh the warehouse that powers /api/stats and the
dashboard. It's cheap and idempotent — safe to run on every scheduled job.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analytics import build_warehouse, get_stats  # noqa: E402


def main() -> None:
    res = build_warehouse()
    print(f"[etl] warehouse loaded → {res['store']}  ({res['rows']} stories)")

    # Keep the semantic-memory embeddings current (skips silently if no API key).
    try:
        from app.memory import backfill_embeddings

        emb = backfill_embeddings()
        if emb.get("embedded"):
            print(f"[etl] embedded {emb['embedded']} new stories into pgvector")
    except Exception as exc:  # noqa: BLE001
        print(f"[etl] embedding step skipped: {exc}")

    s = get_stats()
    if not s.get("total"):
        print("[etl] no stories yet — warehouse is empty.")
        return

    print(f"[etl] date range      : {s['date_range'][0]} → {s['date_range'][1]}")
    print(f"[etl] high/critical   : {s['high_or_critical']}/{s['total']}")
    if s["urgency"]["labelled"]:
        print(f"[etl] avg urgency     : {s['urgency']['avg']} (n={s['urgency']['labelled']})")
    print("[etl] by domain       : " + ", ".join(f"{d['domain']}={d['count']}" for d in s["by_domain"]))
    print("[etl] by severity     : " + ", ".join(f"{d['severity']}={d['count']}" for d in s["by_severity"]))


if __name__ == "__main__":
    main()
