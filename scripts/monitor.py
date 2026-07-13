"""
Continuous monitor — run by GitHub Actions every 2 hours.

    python scripts/monitor.py

One cheap grounded Gemini call scans for breaking news. If something CRITICAL
is happening it sends an immediate Telegram alert; otherwise it stays silent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, usage  # noqa: E402
from app.briefing import format_breaking, format_usage_warning  # noqa: E402
from app.pipeline import quick_scan  # noqa: E402
from app.store import load_log, log_story, save_log, seen_recently  # noqa: E402
from app.telegram import send_telegram  # noqa: E402
from app.usage import UsageLimitError  # noqa: E402

DATA = config.ROOT / "data"
USAGE_FILE = DATA / "usage.json"
LOG_FILE = DATA / "log.json"


def main() -> None:
    print("[monitor] scanning for breaking news")

    usage.hydrate(USAGE_FILE)
    log = load_log(LOG_FILE)

    try:
        scan = quick_scan()
        if not scan["critical"] or not scan["items"]:
            print("[monitor] nothing critical — staying silent")
        else:
            fresh = [it for it in scan["items"] if not seen_recently(log, it["headline"], 1)]
            if not fresh:
                print("[monitor] critical items already alerted earlier today")
            else:
                send_telegram(format_breaking(fresh, config.APP_URL))
                for it in fresh:
                    log_story(
                        log,
                        {
                            "headline": it["headline"],
                            "summary": it["summary"],
                            "why": it["why"],
                            "domain": "Breaking",
                            "severity": "CRITICAL",
                            "mode": "monitor",
                        },
                    )
                print(f"[monitor] breaking alert sent ({len(fresh)} items)")
    except UsageLimitError as exc:
        print(f"[monitor] {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[monitor] failed: {exc}")
        sys.exit(1)

    if usage.near_limit() and not usage.already_warned():
        try:
            send_telegram(format_usage_warning(usage.snapshot()))
            usage.mark_warned()
            print("[monitor] usage warning sent")
        except Exception as exc:  # noqa: BLE001
            print(f"[monitor] could not send usage warning: {exc}")

    usage.persist(USAGE_FILE)
    save_log(LOG_FILE, log)

    try:
        from app.analytics import migrate

        migrate()
    except Exception as exc:  # noqa: BLE001
        print(f"[monitor] postgres sync skipped: {exc}")

    u = usage.snapshot()
    print(
        f"[monitor] usage today — Gemini {u['gemini']}/{u['maxGemini']}, "
        f"Groq {u['groq']}/{u['maxGroq']}"
    )


if __name__ == "__main__":
    main()
