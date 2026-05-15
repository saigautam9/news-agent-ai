// Registers (or removes) the Telegram webhook so the bot can receive messages.
//
//   npm run webhook -- set https://your-app.vercel.app   point Telegram at your app
//   npm run webhook -- status                            show the current webhook
//   npm run webhook -- delete                            stop receiving messages
//
// Run this once after deploying. It reads TELEGRAM_BOT_TOKEN and
// TELEGRAM_WEBHOOK_SECRET from .env.local automatically.

import { promises as fs } from "node:fs";
import path from "node:path";

// --- Load .env.local (this standalone script isn't run by Next.js) ---
async function loadEnv(): Promise<void> {
  try {
    const raw = await fs.readFile(
      path.join(process.cwd(), ".env.local"),
      "utf8",
    );
    for (const line of raw.split("\n")) {
      const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
      if (m && !process.env[m[1]]) {
        process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
      }
    }
  } catch {
    /* no .env.local — rely on the real environment */
  }
}

async function main(): Promise<void> {
  await loadEnv();

  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    console.error("TELEGRAM_BOT_TOKEN is not set — add it to .env.local.");
    process.exit(1);
  }
  const api = `https://api.telegram.org/bot${token}`;
  const action = (process.argv[2] || "status").toLowerCase();

  if (action === "set") {
    const url = process.argv[3];
    if (!url) {
      console.error("Usage: npm run webhook -- set https://your-app.vercel.app");
      process.exit(1);
    }
    const body: Record<string, unknown> = {
      url: `${url.replace(/\/$/, "")}/api/telegram`,
      allowed_updates: ["message"],
    };
    const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
    if (secret) body.secret_token = secret;

    const res = await fetch(`${api}/setWebhook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    console.log(json.ok ? `✅ Webhook set → ${body.url}` : "❌ Failed:", json);
    if (!secret) {
      console.log(
        "⚠️  TELEGRAM_WEBHOOK_SECRET not set — anyone who learns the URL " +
          "could POST to it. Add one to .env.local and re-run.",
      );
    }
  } else if (action === "delete") {
    const res = await fetch(`${api}/deleteWebhook`);
    const json = await res.json();
    console.log(json.ok ? "✅ Webhook removed." : "❌ Failed:", json);
  } else {
    const res = await fetch(`${api}/getWebhookInfo`);
    const json = await res.json();
    console.log(JSON.stringify(json.result ?? json, null, 2));
  }
}

main();
