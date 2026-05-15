"""
Deep Signal — ML inference.

Loads the trained models and analyses a news headline instantly and offline —
no API calls. Reports the topic (AG News model) and, when the Deep Signal
models have been trained, the domain, severity and urgency score.

Usage:
    python ml/predict.py "Central bank raises interest rates to fight inflation"
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib

MODELS = Path(__file__).resolve().parent / "models"


def _load(name: str):
    path = MODELS / name
    return joblib.load(path) if path.exists() else None


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python ml/predict.py "a news headline or summary"')

    text = " ".join(sys.argv[1:]).strip()
    topic = _load("topic_clf.joblib")
    if topic is None:
        raise SystemExit("No trained models — run `python ml/train.py` first.")

    print(f'\nText:     "{text}"')
    print(f"Topic:    {topic.predict([text])[0]}   (AG News model)")

    domain = _load("domain_clf.joblib")
    severity = _load("severity_clf.joblib")
    urgency = _load("urgency_reg.joblib")

    if domain is not None:
        print(f"Domain:   {domain.predict([text])[0]}")
    if severity is not None:
        print(f"Severity: {severity.predict([text])[0]}")
    if urgency is not None:
        print(f"Urgency:  {float(urgency.predict([text])[0]):.1f} / 10")

    if domain is None:
        print("\n(Deep Signal domain/severity/urgency models not trained yet.)")
    print()


if __name__ == "__main__":
    main()
