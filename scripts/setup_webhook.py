"""
Registers (or removes) the Telegram webhook so the bot can receive messages.

    python scripts/setup_webhook.py set https://your-app.vercel.app
    python scripts/setup_webhook.py status
    python scripts/setup_webhook.py delete

Run this once after deploying. Reads TELEGRAM_BOT_TOKEN and
TELEGRAM_WEBHOOK_SECRET from .env.local automatically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app import config  # noqa: E402


def main() -> None:
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set — add it to .env.local.")

    api = f"https://api.telegram.org/bot{token}"
    action = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()

    if action == "set":
        if len(sys.argv) < 3:
            sys.exit("Usage: python scripts/setup_webhook.py set https://your-app.vercel.app")
        url = sys.argv[2].rstrip("/")
        body = {
            "url": f"{url}/api/telegram",
            "allowed_updates": ["message", "callback_query"],
        }
        if config.TELEGRAM_WEBHOOK_SECRET:
            body["secret_token"] = config.TELEGRAM_WEBHOOK_SECRET
        res = httpx.post(f"{api}/setWebhook", json=body, timeout=20.0).json()
        print(f"✅ Webhook set → {body['url']}" if res.get("ok") else "❌ Failed:", res)
        if not config.TELEGRAM_WEBHOOK_SECRET:
            print("⚠️  TELEGRAM_WEBHOOK_SECRET not set — add one to .env.local and re-run.")
    elif action == "delete":
        res = httpx.get(f"{api}/deleteWebhook", timeout=20.0).json()
        print("✅ Webhook removed." if res.get("ok") else "❌ Failed:", res)
    else:
        res = httpx.get(f"{api}/getWebhookInfo", timeout=20.0).json()
        print(json.dumps(res.get("result", res), indent=2))


if __name__ == "__main__":
    main()
