"""
Builds the Telegram messages (Markdown). All dynamic text is run through
sanitize_markdown so it can't break Telegram's parser.
"""

from __future__ import annotations

from datetime import date

from app.telegram import sanitize_markdown as _s

SEV_EMOJI = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "⚪"}

PIPELINE_LINE = "_Pipeline: Gemini 2.5 Flash + Flash-Lite · Groq Llama 4 Scout_"


def _today() -> str:
    return date.today().strftime("%A, %-d %B")


def _footer(app_url: str) -> str:
    return f"{PIPELINE_LINE}\n[Open Deep Signal →]({app_url})"


def _story_block(story: dict) -> str:
    emoji = SEV_EMOJI.get(story["severity"], "🟡")
    return (
        f"{emoji} *{_s(story['headline'])}*\n"
        f"{_s(story['summary'])}\n"
        f"_Why it matters: {_s(story['why'])}_"
    )


def format_briefing(title: str, stories: list[dict], app_url: str) -> str:
    """Morning briefing / afternoon update — a list of important stories."""
    blocks = "\n\n".join(_story_block(s) for s in stories)
    return (
        f"*🛰 Deep Signal — {_s(title)}*\n_{_today()}_\n\n"
        f"{blocks}\n\n{_footer(app_url)}"
    )


def format_roundup(important: list[dict], mediums: list[dict], app_url: str) -> str:
    """Evening roundup — important stories plus a bundled list of MEDIUM ones."""
    head = (
        "\n\n".join(_story_block(s) for s in important)
        if important
        else "_A quiet day — nothing critical or high-priority broke._"
    )
    radar = ""
    if mediums:
        bullets = "\n".join(f"• {_s(m['headline'])}" for m in mediums[:6])
        radar = f"\n\n🟡 *Also on the radar*\n{bullets}"
    return (
        f"*🛰 Deep Signal — Evening Roundup*\n_{_today()}_\n\n"
        f"{head}{radar}\n\n{_footer(app_url)}"
    )


def format_breaking(items: list[dict], app_url: str) -> str:
    """Immediate alert from the every-2-hours monitor."""
    blocks = "\n\n".join(
        f"🔴 *{_s(it['headline'])}*\n{_s(it['summary'])}\n"
        f"_Why this is critical: {_s(it['why'])}_"
        for it in items
    )
    return f"🚨 *Deep Signal — Breaking*\n\n{blocks}\n\n[Open Deep Signal →]({app_url})"


def format_weekly(entries: list[dict], app_url: str) -> str:
    """Weekly roundup of the slower MEDIUM-severity stories."""
    blocks = "\n\n".join(
        f"🟡 *{_s(e['headline'])}*\n{_s(e['summary'])}" for e in entries[:12]
    )
    return (
        f"*🛰 Deep Signal — Weekly Roundup*\n"
        f"_The slower-moving stories from the past week_\n\n"
        f"{blocks}\n\n[Open Deep Signal →]({app_url})"
    )


def format_usage_warning(u: dict) -> str:
    """Cost-protection warning sent once when usage crosses the threshold."""
    return (
        f"⚠️ *Deep Signal — API usage warning*\n\n"
        f"Today's calls so far: Gemini {u['gemini']}/{u['maxGemini']}, "
        f"Groq {u['groq']}/{u['maxGroq']}.\n\n"
        f"If a daily cap is reached the system pauses and resumes tomorrow — "
        f"it stays free either way."
    )


def format_topic_reply(query: str, stories: list[dict], app_url: str) -> str:
    """Reply to a topic/question asked interactively via the Telegram bot."""
    if not stories:
        return (
            f"🛰 *Deep Signal*\n\n"
            f"I couldn't find anything solid on _{_s(query)}_ right now — "
            f"try rephrasing it."
        )
    blocks = "\n\n".join(_story_block(s) for s in stories)
    return f"*🛰 Deep Signal — {_s(query)}*\n\n{blocks}\n\n{_footer(app_url)}"


def format_news_list(title: str, stories: list[dict]) -> str:
    """Numbered list of today's stories — sent before the 'my take?' buttons."""
    lines = []
    for i, s in enumerate(stories, 1):
        emoji = SEV_EMOJI.get(s["severity"], "🟡")
        lines.append(
            f"{emoji} *{i}. {_s(s['headline'])}*\n"
            f"{_s(s['summary'])}\n"
            f"_{_s(s.get('domain', ''))} · why it matters: {_s(s['why'])}_"
        )
    body = "\n\n".join(lines)
    return (
        f"*🛰 Deep Signal — {_s(title)}*\n_{_today()}_\n\n{body}\n\n"
        f"👇 Want my take? Tap a story number below — or *All* for every story."
    )


def format_verdict_reply(
    topic: str, story: dict, verdict: dict, others: list[dict], app_url: str
) -> str:
    """The bot's full answer: the key story + Deep Signal's verdict."""
    sections: list[str] = []
    if verdict.get("analysis"):
        sections.append(f"🧠 *My read*\n{_s(verdict['analysis'])}")
    if verdict.get("opinion"):
        sections.append(f"💬 *My take*\n{_s(verdict['opinion'])}")
    if verdict.get("solution"):
        sections.append(f"🛠 *What should happen*\n{_s(verdict['solution'])}")
    if verdict.get("outcomes"):
        lines = "\n".join(
            f"• _{_s(o['horizon'])}_ — {_s(o['outcome'])}" for o in verdict["outcomes"]
        )
        sections.append(f"🔮 *Likely outcomes*\n{lines}")

    related = ""
    if others:
        related = "\n\n📌 *Related angles*\n" + "\n".join(
            f"• {_s(o['headline'])}" for o in others[:4]
        )

    emoji = SEV_EMOJI.get(story["severity"], "🟡")
    body = "\n\n".join(sections)
    return (
        f"*🛰 Deep Signal — {_s(topic)}*\n\n"
        f"{emoji} *{_s(story['headline'])}*\n{_s(story['summary'])}\n\n"
        f"{body}{related}\n\n{_footer(app_url)}"
    )
