"""Sends notifications to a Telegram chat via the Telegram Bot API."""

from __future__ import annotations

import re

import httpx

from app import config


def sanitize_markdown(text: str) -> str:
    """
    Remove characters that would break Telegram's legacy Markdown parser.
    Legacy Markdown has no escape syntax, so dynamic text (headlines, summaries)
    must be stripped of these before being placed inside a message.
    """
    text = re.sub(r"[_*`\[\]]", "", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _api(method: str, payload: dict) -> httpx.Response:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set.")
    return httpx.post(
        f"https://api.telegram.org/bot{token}/{method}",
        json=payload,
        timeout=20.0,
    )


def send_telegram(
    text: str,
    chat_id: str | int | None = None,
    reply_markup: dict | None = None,
) -> None:
    """
    Send a Markdown message. Defaults to TELEGRAM_CHAT_ID (the owner); the
    interactive bot passes the chat that messaged it so it can reply there.
    `reply_markup` attaches an inline keyboard.
    """
    to = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
    if not to:
        raise RuntimeError("TELEGRAM_CHAT_ID must be set.")

    payload: dict = {
        "chat_id": to,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    res = _api("sendMessage", payload)
    if res.status_code != 200:
        detail = str(res.status_code)
        try:
            body = res.json()
            if body.get("description"):
                detail = body["description"]
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"Telegram sendMessage failed: {detail}")


def answer_callback(callback_query_id: str, text: str = "") -> None:
    """Acknowledge an inline-keyboard tap so Telegram stops the loading spinner."""
    try:
        _api("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except Exception:  # noqa: BLE001
        pass


def inline_keyboard(buttons: list[list[dict]]) -> dict:
    """Build an inline-keyboard reply markup from rows of {text, callback_data}."""
    return {"inline_keyboard": buttons}
