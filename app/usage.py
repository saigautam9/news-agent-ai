"""
Cost protection. Tracks how many API calls each provider has made today and
enforces a hard daily cap so the app can never run up a bill.

The scheduled scripts call hydrate() at the start of a run and persist() at the
end, keeping the count in data/usage.json. The web app skips hydrate/persist —
its counter just lives for the process lifetime.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app import config

Provider = str  # "gemini" | "groq"


class UsageLimitError(Exception):
    """Raised when a provider's daily cap is reached."""

    def __init__(self, provider: Provider) -> None:
        super().__init__(
            f"Daily {provider} API call limit reached — "
            f"stopping until tomorrow to stay free."
        )


def _today() -> str:
    return date.today().isoformat()


def _fresh() -> dict:
    return {"date": _today(), "gemini": 0, "groq": 0, "warned": False}


_state: dict = _fresh()


def hydrate(file: str | Path) -> None:
    """Load today's counters from disk (resetting if the file is from a past day)."""
    global _state
    try:
        raw = json.loads(Path(file).read_text())
        if raw.get("date") == _today():
            _state = {**_fresh(), **raw, "date": _today()}
        else:
            _state = _fresh()
    except (OSError, json.JSONDecodeError):
        _state = _fresh()


def persist(file: str | Path) -> None:
    """Write the current counters back to disk."""
    Path(file).write_text(json.dumps(_state, indent=2) + "\n")


def record(provider: Provider) -> None:
    """Record one API call. Raises UsageLimitError if the cap is already reached."""
    global _state
    if _state["date"] != _today():
        _state = _fresh()
    cap = config.MAX_GEMINI_CALLS if provider == "gemini" else config.MAX_GROQ_CALLS
    if _state[provider] >= cap:
        raise UsageLimitError(provider)
    _state[provider] += 1


def snapshot() -> dict:
    return {
        **_state,
        "maxGemini": config.MAX_GEMINI_CALLS,
        "maxGroq": config.MAX_GROQ_CALLS,
    }


def near_limit() -> bool:
    """True once either provider crosses the warning threshold (default 80%)."""
    return (
        _state["gemini"] >= config.MAX_GEMINI_CALLS * config.USAGE_WARN_THRESHOLD
        or _state["groq"] >= config.MAX_GROQ_CALLS * config.USAGE_WARN_THRESHOLD
    )


def already_warned() -> bool:
    return bool(_state["warned"])


def mark_warned() -> None:
    _state["warned"] = True
