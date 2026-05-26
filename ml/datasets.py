"""
Dataset loaders for the NewsAgent AI ML module.

Two sources:
  - AG News        — 120k public, labelled news articles (4 topic classes).
  - Signal corpus  — the stories NewsAgent AI collects + labels itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
AGNEWS_DIR = ROOT / "data" / "agnews"
CORPUS_CSV = ROOT / "data" / "corpus.csv"
LOG_JSON = ROOT.parent / "data" / "log.json"

# AG News ships integer labels 1-4.
AGNEWS_LABELS = {1: "World", 2: "Sports", 3: "Business", 4: "Sci/Tech"}


def _read_agnews_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=["label", "title", "description"])
    df["title"] = df["title"].fillna("")
    df["description"] = df["description"].fillna("")
    df["text"] = (df["title"] + ". " + df["description"]).str.strip()
    df["label"] = df["label"].map(AGNEWS_LABELS)
    return df[["text", "label"]].dropna()


def load_agnews() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train_df, test_df) for AG News. Each has columns: text, label."""
    if not (AGNEWS_DIR / "train.csv").exists():
        raise SystemExit(
            "AG News not found — run `python ml/download_data.py` first."
        )
    return _read_agnews_csv(AGNEWS_DIR / "train.csv"), _read_agnews_csv(
        AGNEWS_DIR / "test.csv"
    )


def load_signal_corpus() -> pd.DataFrame:
    """
    NewsAgent AI's own labelled stories, merged from ml/data/corpus.csv and
    data/log.json. Columns: text, domain, severity, urgency (urgency may be NaN
    for stories that came from the log, which doesn't record it).
    """
    frames: list[pd.DataFrame] = []

    if CORPUS_CSV.exists():
        frames.append(pd.read_csv(CORPUS_CSV))

    if LOG_JSON.exists():
        entries = json.loads(LOG_JSON.read_text()).get("entries", [])
        if entries:
            frames.append(pd.DataFrame(entries))

    if not frames:
        return pd.DataFrame(columns=["text", "domain", "severity", "urgency"])

    df = pd.concat(frames, ignore_index=True)
    for col in ("headline", "summary", "why"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    df["text"] = (df["headline"] + " " + df["summary"] + " " + df["why"]).str.strip()
    if "urgency" not in df.columns:
        df["urgency"] = pd.NA
    df["urgency"] = pd.to_numeric(df["urgency"], errors="coerce")

    df = df[df["text"].str.len() > 0]
    df = df.dropna(subset=["domain", "severity"])
    df = df.drop_duplicates(subset="text").reset_index(drop=True)
    return df[["text", "domain", "severity", "urgency"]]
