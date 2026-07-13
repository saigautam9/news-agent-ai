"""
Configuration and environment loading.

For local development this reads .env.local (and .env) so the scripts and the
web app just work. In production (Vercel, GitHub Actions) the real environment
variables are already set and take precedence.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(name: str) -> None:
    path = ROOT / name
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Real environment variables always win over the file.
        os.environ.setdefault(key, value)


_load_env_file(".env.local")
_load_env_file(".env")


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


# --- API keys ---
GEMINI_API_KEY = _get("GEMINI_API_KEY")
GROQ_API_KEY = _get("GROQ_API_KEY")

# Neon Postgres — cloud warehouse for the story log + analytics (optional:
# falls back to the local JSON store when unset, so local dev still works).
# .strip() guards against a stray newline/space when the value is pasted into
# a hosting dashboard (e.g. "sslmode=require\n").
DATABASE_URL = _get("DATABASE_URL").strip()

# --- Models (overridable) ---
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_LITE_MODEL = _get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest")
GROQ_MODEL = _get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# --- Telegram ---
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")
TELEGRAM_WEBHOOK_SECRET = _get("TELEGRAM_WEBHOOK_SECRET")

# --- App ---
APP_URL = _get("APP_URL", "http://localhost:8000")

# --- Cost protection ---
MAX_GEMINI_CALLS = int(_get("MAX_GEMINI_CALLS", "20") or "20")
MAX_GROQ_CALLS = int(_get("MAX_GROQ_CALLS", "20") or "20")
USAGE_WARN_THRESHOLD = float(_get("USAGE_WARN_THRESHOLD", "0.8") or "0.8")
