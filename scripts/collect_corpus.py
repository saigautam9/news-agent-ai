"""
Builds the training corpus for the ML module (ml/).

Runs NewsAgent AI's own fetch + classify pipeline across many topics, so every
story comes back already labelled with a domain, urgency score and severity.
The labelled rows are written to ml/data/corpus.csv.

    python scripts/collect_corpus.py

Note: Gemini's free tier allows 20 requests/day — a full run needs more, so
expect it to stop early on the daily quota and resume tomorrow. New rows are
appended to any existing corpus.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.pipeline import fetch_stories  # noqa: E402

TOPICS = [
    "US China relations", "Russia Ukraine war", "Middle East conflict",
    "India foreign policy", "European Union politics", "North Korea tensions",
    "stock market movements", "inflation and interest rates", "cryptocurrency markets",
    "global oil prices", "international trade tariffs", "big tech company earnings",
    "artificial intelligence", "semiconductor industry", "electric vehicles",
    "space exploration", "cybersecurity threats", "social media regulation",
    "global disease outbreaks", "healthcare policy", "mental health crisis",
    "pharmaceutical industry", "climate change impact", "renewable energy transition",
    "extreme weather events", "environmental policy", "education reform",
    "immigration policy", "labor market and jobs", "global housing crisis",
]

FIELDS = ["headline", "summary", "why", "domain", "urgency", "severity"]


def main() -> None:
    out_dir = config.ROOT / "ml" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "corpus.csv"

    rows: list[dict] = []
    seen: set[str] = set()

    # Keep any rows already collected so the corpus grows across runs.
    if out_file.exists():
        with out_file.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = row["headline"].lower()[:60]
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        print(f"[collect] starting from {len(rows)} existing rows")

    for topic in TOPICS:
        try:
            stories = fetch_stories(topic)["stories"]
            added = 0
            for st in stories:
                key = st["headline"].lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                rows.append({f: st[f] for f in FIELDS})
                added += 1
            print(f"[collect] {topic} → +{added} (corpus: {len(rows)})")
        except Exception as exc:  # noqa: BLE001
            print(f"[collect] {topic} failed: {exc}")
            if "quota" in str(exc).lower() or "exhausted" in str(exc).lower():
                print("[collect] daily quota reached — stopping; resume tomorrow.")
                break

    with out_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[collect] done — {len(rows)} labelled rows → {out_file}")


if __name__ == "__main__":
    main()
