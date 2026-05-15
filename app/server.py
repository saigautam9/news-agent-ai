"""
Deep Signal — FastAPI application.

Serves the web UI, the JSON API, a chat endpoint, and the Telegram webhook.
The same multi-agent pipeline powers all of them.
"""

from __future__ import annotations

import time
from pathlib import Path

import traceback

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.briefing import (
    format_news_list,
    format_topic_reply,
    format_verdict_reply,
)
from app.gemini import err_message
from app.pipeline import (
    build_agent_takes,
    build_deep_dive,
    build_verdict,
    fetch_stories,
)
from app.telegram import (
    answer_callback,
    inline_keyboard,
    sanitize_markdown,
    send_telegram,
)

BASE = Path(__file__).resolve().parent

app = FastAPI(title="Deep Signal", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

INDEX_HTML = BASE / "templates" / "index.html"

# Short-lived cache of the last news batch per chat, so the inline-keyboard
# buttons can resolve which story the user tapped. Survives within a warm
# server instance; on a cache miss the bot just asks the user to tap /news.
_news_cache: dict[str, dict] = {}


# ---------------------------------------------------------------- web UI
@app.get("/", response_class=HTMLResponse)
def home():
    """Serve the single-page UI (static HTML — no template variables)."""
    try:
        return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return PlainTextResponse(
            "Deep Signal — homepage failed to load:\n\n" + traceback.format_exc(),
            status_code=500,
        )


@app.get("/health")
def health():
    return {"ok": True}


# ---------------------------------------------------------------- JSON API
@app.get("/api/news")
def api_news():
    """Today's most important stories."""
    try:
        return fetch_stories()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": err_message(exc)}, status_code=500)


@app.post("/api/search")
async def api_search(request: Request):
    """Top angles on a topic."""
    query = str((await _json(request)).get("query") or "").strip()
    if not query:
        return JSONResponse(
            {"error": "Please provide a topic to search for."}, status_code=400
        )
    try:
        return fetch_stories(query)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": err_message(exc)}, status_code=500)


@app.post("/api/analyze")
async def api_analyze(request: Request):
    """Full deep-dive analysis of one story."""
    story = (await _json(request)).get("story") or {}
    headline = str(story.get("headline") or "")
    if not headline:
        return JSONResponse(
            {"error": "A story with a headline is required."}, status_code=400
        )
    try:
        return build_deep_dive(
            {"headline": headline, "summary": str(story.get("summary") or "")}
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": err_message(exc)}, status_code=500)


@app.post("/api/agents")
async def api_agents(request: Request):
    """Five analyst perspectives plus a debate synthesis."""
    story = (await _json(request)).get("story") or {}
    headline = str(story.get("headline") or "")
    if not headline:
        return JSONResponse(
            {"error": "A story with a headline is required."}, status_code=400
        )
    try:
        return build_agent_takes(
            {"headline": headline, "summary": str(story.get("summary") or "")}
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": err_message(exc)}, status_code=500)


@app.post("/api/chat")
async def api_chat(request: Request):
    """Website chatbot — investigates a question and returns Deep Signal's verdict."""
    message = str((await _json(request)).get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "Ask me about any topic."}, status_code=400)
    try:
        stories = fetch_stories(message)["stories"]
        if not stories:
            return {"reply": "I couldn't find anything solid on that — try rephrasing."}
        top, others = stories[0], stories[1:]
        verdict = build_verdict(message, top)
        return {"story": top, "verdict": verdict, "related": others}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": err_message(exc)}, status_code=500)


# ---------------------------------------------------------------- Telegram bot
_HELP = "\n".join(
    [
        "🛰 *Deep Signal*",
        "",
        "I investigate the news with a 7-agent AI pipeline and give you my own",
        "analysis, opinion and predicted outcomes.",
        "",
        "• /news — today's top stories, then tap one for my take",
        "• send any *topic* — e.g. `US tariffs` — for a full investigation",
    ]
)


@app.post("/api/telegram")
async def api_telegram(request: Request):
    """Telegram webhook — handles messages and inline-keyboard taps."""
    secret = config.TELEGRAM_WEBHOOK_SECRET
    if secret and request.headers.get("x-telegram-bot-api-secret-token") != secret:
        return JSONResponse({"ok": False}, status_code=401)

    update = await _json(request)

    if "callback_query" in update:
        _handle_callback(update["callback_query"])
        return {"ok": True}

    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = str(message.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True}

    # Owner-only — protects the free-tier API quota.
    owner = config.TELEGRAM_CHAT_ID
    if owner and str(chat_id) != str(owner):
        _try_send("Sorry — this is a private Deep Signal bot.", chat_id)
        return {"ok": True}

    if text in ("/start", "/help"):
        _try_send(_HELP, chat_id)
    elif text in ("/news", "news"):
        _send_news(chat_id)
    else:
        _send_topic_verdict(chat_id, text)
    return {"ok": True}


def _send_news(chat_id) -> None:
    """Send today's stories with a 'my take?' inline keyboard."""
    try:
        stories = fetch_stories()["stories"]
    except Exception as exc:  # noqa: BLE001
        _try_send(f"Sorry — couldn't fetch the news: {sanitize_markdown(err_message(exc))}", chat_id)
        return

    _news_cache[str(chat_id)] = {"stories": stories, "ts": time.time()}
    numbers = [
        {"text": str(i + 1), "callback_data": f"take:{i}"} for i in range(len(stories))
    ]
    keyboard = inline_keyboard(
        [numbers, [{"text": "🧠 My take on all", "callback_data": "take:all"}]]
    )
    try:
        send_telegram(format_news_list("Today's Briefing", stories), chat_id, keyboard)
    except Exception:  # noqa: BLE001
        pass


def _send_topic_verdict(chat_id, topic: str) -> None:
    """Investigate a free-text topic and reply with Deep Signal's verdict."""
    try:
        _try_send(
            f"🛰 Investigating *{sanitize_markdown(topic)}* and forming my take — "
            f"one moment…",
            chat_id,
        )
        stories = fetch_stories(topic)["stories"]
        if not stories:
            send_telegram(format_topic_reply(topic, stories, config.APP_URL), chat_id)
            return
        top, others = stories[0], stories[1:]
        verdict = build_verdict(topic, top)
        send_telegram(
            format_verdict_reply(topic, top, verdict, others, config.APP_URL), chat_id
        )
    except Exception as exc:  # noqa: BLE001
        _try_send(
            f"Sorry — that didn't work: {sanitize_markdown(err_message(exc))}", chat_id
        )


def _handle_callback(callback: dict) -> None:
    """A 'my take' button was tapped — send the verdict for that story."""
    cb_id = callback.get("id", "")
    data = str(callback.get("data") or "")
    chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
    answer_callback(cb_id, "On it…")
    if not chat_id or not data.startswith("take:"):
        return

    cached = _news_cache.get(str(chat_id))
    if not cached:
        _try_send("That briefing expired — send /news again to refresh.", chat_id)
        return

    stories = cached["stories"]
    target = data.split(":", 1)[1]
    picks = stories if target == "all" else (
        [stories[int(target)]] if target.isdigit() and int(target) < len(stories) else []
    )
    if not picks:
        _try_send("Couldn't find that story — send /news again.", chat_id)
        return

    for story in picks:
        try:
            verdict = build_verdict(story["headline"], story)
            send_telegram(
                format_verdict_reply(story["headline"], story, verdict, [], config.APP_URL),
                chat_id,
            )
        except Exception as exc:  # noqa: BLE001
            _try_send(
                f"Couldn't analyse that one: {sanitize_markdown(err_message(exc))}",
                chat_id,
            )
            break


# ---------------------------------------------------------------- helpers
async def _json(request: Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _try_send(text: str, chat_id) -> None:
    try:
        send_telegram(text, chat_id)
    except Exception:  # noqa: BLE001
        pass
