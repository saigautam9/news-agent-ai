"""
Gemini client. Runs a single Gemini call, optionally with Google Search
grounding (live web access), and counts it against the daily cost cap first.
"""

from __future__ import annotations

import json
import re
import time

from google import genai
from google.genai import types

from app import config
from app.usage import record


# Transient errors (5xx, "UNAVAILABLE", "high demand") are retried with
# exponential backoff. A per-MINUTE 429 rate-limit is also retried briefly
# (news loads fire a few grounded calls at once and can trip it); a genuine
# daily-quota 429 with a long/absent retry hint is NOT retried.
_TRANSIENT_STATUS = re.compile(r"\b(500|502|503|504)\b")
_TRANSIENT_PHRASES = ("unavailable", "high demand", "internal server error", "bad gateway")
_RETRY_DELAY_RE = re.compile(r"retrydelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I)


def _is_transient(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if _TRANSIENT_STATUS.search(msg):
        return True
    return any(phrase in msg for phrase in _TRANSIENT_PHRASES)


def _is_rate_limit(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "rate limit" in msg


def _retry(call, attempts: int = 4, base_delay: float = 1.5):
    for i in range(attempts):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            if i == attempts - 1:
                raise
            if _is_rate_limit(exc):
                m = _RETRY_DELAY_RE.search(str(exc))
                wait = float(m.group(1)) if m else min(3 * (2**i), 20)
                if wait > 30:  # looks like a hard/daily quota — don't spin on it
                    raise
                time.sleep(wait + 0.5)
                continue
            if not _is_transient(exc):
                raise
            time.sleep(base_delay * (2**i))

# Two free-tier Gemini models, each with a focused role in the pipeline.
MODEL_FLASH = config.GEMINI_MODEL
MODEL_LITE = config.GEMINI_LITE_MODEL

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if not config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a free key at "
            "https://aistudio.google.com/apikey and add it to .env.local."
        )
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def run_gemini(
    system: str,
    prompt: str,
    model: str | None = None,
    grounding: bool = False,
) -> dict:
    """
    Run one Gemini call. With grounding on, Gemini searches the live web first
    and we return the cited sources. Returns {"text": str, "sources": [...]}.
    """
    record("gemini")  # raises UsageLimitError if the daily cap is reached
    client = _get_client()

    # Grounding cannot be combined with a JSON response schema, so when it's off
    # we ask Gemini for raw JSON output; when it's on we parse the text.
    if grounding:
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    else:
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
        )

    res = _retry(
        lambda: client.models.generate_content(
            model=model or MODEL_FLASH,
            contents=prompt,
            config=cfg,
        )
    )

    text = res.text or ""
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response. Try again in a moment.")

    sources: list[dict] = []
    seen: set[str] = set()
    try:
        chunks = res.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        chunks = []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        url = getattr(web, "uri", None) if web else None
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": getattr(web, "title", None) or url, "url": url})

    return {"text": text, "sources": sources}


def extract_json(text: str):
    """Pull a JSON value out of a model response, tolerating fences and prose."""
    t = text.strip()

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()

    first_obj = t.find("{")
    first_arr = t.find("[")
    if first_arr != -1 and (first_obj == -1 or first_arr < first_obj):
        start, end = first_arr, t.rfind("]")
    else:
        start, end = first_obj, t.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not find JSON in the model response.")

    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("The model response was not valid JSON. Try again.") from exc


def err_message(exc: object) -> str:
    return str(exc) if isinstance(exc, Exception) else str(exc)
