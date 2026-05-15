"""
Download the AG News dataset — 120,000 labelled news articles across four
topic classes (World, Sports, Business, Sci/Tech).

Usage:  python ml/download_data.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

AGNEWS_DIR = Path(__file__).resolve().parent / "data" / "agnews"
BASE = (
    "https://raw.githubusercontent.com/mhjabreel/CharCnn_Keras/"
    "master/data/ag_news_csv"
)


def main() -> None:
    AGNEWS_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("train.csv", "test.csv"):
        dest = AGNEWS_DIR / name
        if dest.exists():
            print(f"{name} already present ({dest.stat().st_size // 1024} KB)")
            continue
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(f"{BASE}/{name}", dest)
        print(f"  saved {dest} ({dest.stat().st_size // 1024} KB)")
    print("done.")


if __name__ == "__main__":
    main()
