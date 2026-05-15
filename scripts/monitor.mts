// Continuous monitor — run by GitHub Actions every 2 hours.
//
//   npm run monitor
//
// One cheap grounded Gemini call scans for breaking news. If something CRITICAL
// is happening it sends an immediate Telegram alert; otherwise it stays silent.

import path from "node:path";
import { quickScan } from "../src/lib/pipeline";
import { sendTelegram } from "../src/lib/telegram";
import { formatBreaking, formatUsageWarning } from "../src/lib/briefing";
import {
  hydrate,
  persist,
  snapshot,
  nearLimit,
  alreadyWarned,
  markWarned,
  UsageLimitError,
} from "../src/lib/usage";
import { loadLog, saveLog, seenRecently, logStory } from "../src/lib/store";

const DATA = path.join(process.cwd(), "data");
const USAGE_FILE = path.join(DATA, "usage.json");
const LOG_FILE = path.join(DATA, "log.json");
const APP_URL = process.env.APP_URL || "http://localhost:3000";

async function main(): Promise<void> {
  console.log("[monitor] scanning for breaking news");

  await hydrate(USAGE_FILE);
  const log = await loadLog(LOG_FILE);

  try {
    const scan = await quickScan();

    if (!scan.critical || scan.items.length === 0) {
      console.log("[monitor] nothing critical — staying silent");
    } else {
      // Skip anything already alerted on today.
      const fresh = scan.items.filter(
        (it) => !seenRecently(log, it.headline, 1),
      );
      if (fresh.length === 0) {
        console.log("[monitor] critical items already alerted earlier today");
      } else {
        await sendTelegram({ text: formatBreaking(fresh, APP_URL) });
        for (const it of fresh) {
          logStory(log, {
            headline: it.headline,
            summary: it.summary,
            why: it.why,
            domain: "Breaking",
            severity: "CRITICAL",
            mode: "monitor",
          });
        }
        console.log(`[monitor] breaking alert sent (${fresh.length} items)`);
      }
    }
  } catch (err) {
    if (err instanceof UsageLimitError) {
      console.log(`[monitor] ${err.message}`);
    } else {
      console.error("[monitor] failed:", err);
      process.exitCode = 1;
    }
  }

  // Cost-protection warning — sent at most once per day.
  if (nearLimit() && !alreadyWarned()) {
    try {
      await sendTelegram({ text: formatUsageWarning(snapshot()) });
      markWarned();
      console.log("[monitor] usage warning sent");
    } catch (e) {
      console.error("[monitor] could not send usage warning:", e);
    }
  }

  await persist(USAGE_FILE);
  await saveLog(LOG_FILE, log);

  const u = snapshot();
  console.log(
    `[monitor] usage today — Gemini ${u.gemini}/${u.maxGemini}, Groq ${u.groq}/${u.maxGroq}`,
  );
}

main();
