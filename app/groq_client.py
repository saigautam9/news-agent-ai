"""
Groq client. Runs a single Groq (Llama 4 Scout) call in JSON mode — used for
historical reasoning, debate synthesis, the verdict, and the plain-English
rewrite step. Counted against the daily cost cap first.
"""

from __future__ import annotations

from groq import Groq

from app import config
from app.gemini import _retry  # shared transient-error retry helper
from app.usage import record

GROQ_MODEL = config.GROQ_MODEL

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Create a free key at "
            "https://console.groq.com/keys and add it to .env.local."
        )
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def run_groq(system: str, prompt: str) -> str:
    """Run one Groq call in JSON mode and return the raw JSON string."""
    record("groq")  # raises UsageLimitError if the daily cap is reached

    res = _retry(
        lambda: _get_client().chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
    )

    content = res.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("Groq returned an empty response. Try again in a moment.")
    return content
