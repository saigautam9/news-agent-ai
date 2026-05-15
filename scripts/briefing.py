"""
Scheduled briefing job — run by GitHub Actions (and runnable locally).

    python scripts/briefing.py morning     full briefing, always sent
    python scripts/briefing.py afternoon   update, only if new important news
    python scripts/briefing.py evening     roundup of the day
    python scripts/briefing.py weekly      roundup of the slower MEDIUM stories

It tracks API usage and dedupes against data/log.json so it never spams or
runs up a cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, usage  # noqa: E402
from app.briefing import (  # noqa: E402
    format_briefing,
    format_roundup,
    format_usage_warning,
    format_weekly,
)
from app.pipeline import fetch_stories  # noqa: E402
from app.store import (  # noqa: E402
    load_log,
    log_story,
    medium_last_week,
    save_log,
    seen_recently,
)
from app.telegram import send_telegram  # noqa: E402
from app.usage import UsageLimitError  # noqa: E402

DATA = config.ROOT / "data"
USAGE_FILE = DATA / "usage.json"
LOG_FILE = DATA / "log.json"

MODES = {"morning", "afternoon", "evening", "weekly"}


def parse_mode() -> str:
    raw = (sys.argv[1] if len(sys.argv) > 1 else "morning").lower().strip()
    return raw if raw in MODES else "morning"


def is_important(story: dict) -> bool:
    return story["severity"] in ("CRITICAL", "HIGH")


def main() -> None:
    mode = parse_mode()
    print(f"[briefing] mode={mode}")

    usage.hydrate(USAGE_FILE)
    log = load_log(LOG_FILE)

    try:
        if mode == "weekly":
            mediums = medium_last_week(log)
            if mediums:
                send_telegram(format_weekly(mediums, config.APP_URL))
                print(f"[briefing] weekly roundup sent ({len(mediums)} stories)")
            else:
                print("[briefing] weekly: nothing to report")
        else:
            stories = fetch_stories()["stories"]
            fresh = [s for s in stories if not seen_recently(log, s["headline"], 2)]

            for st in stories:
                log_story(
                    log,
                    {
                        "headline": st["headline"],
                        "summary": st["summary"],
                        "why": st["why"],
                        "domain": st["domain"],
                        "severity": st["severity"],
                        "mode": mode,
                    },
                )

            important = [s for s in stories if is_important(s)]

            if mode == "morning":
                picks = important if important else stories[:5]
                send_telegram(format_briefing("Morning Briefing", picks, config.APP_URL))
                print(f"[briefing] morning briefing sent ({len(picks)} stories)")
            elif mode == "afternoon":
                fresh_important = [s for s in fresh if is_important(s)]
                if fresh_important:
                    send_telegram(
                        format_briefing("Afternoon Update", fresh_important, config.APP_URL)
                    )
                    print(f"[briefing] afternoon update sent ({len(fresh_important)} new)")
                else:
                    print("[briefing] afternoon: nothing new — staying silent")
            else:  # evening
                mediums = [s for s in stories if s["severity"] == "MEDIUM"]
                send_telegram(format_roundup(important, mediums, config.APP_URL))
                print("[briefing] evening roundup sent")
    except UsageLimitError as exc:
        print(f"[briefing] {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[briefing] failed: {exc}")
        sys.exit(1)

    # Cost-protection warning — sent at most once per day.
    if usage.near_limit() and not usage.already_warned():
        try:
            send_telegram(format_usage_warning(usage.snapshot()))
            usage.mark_warned()
            print("[briefing] usage warning sent")
        except Exception as exc:  # noqa: BLE001
            print(f"[briefing] could not send usage warning: {exc}")

    usage.persist(USAGE_FILE)
    save_log(LOG_FILE, log)

    u = usage.snapshot()
    print(
        f"[briefing] usage today — Gemini {u['gemini']}/{u['maxGemini']}, "
        f"Groq {u['groq']}/{u['maxGroq']}"
    )


if __name__ == "__main__":
    main()
