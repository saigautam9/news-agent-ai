// Scheduled briefing job — run by GitHub Actions (and runnable locally).
//
//   npm run briefing -- morning     full briefing, always sent
//   npm run briefing -- afternoon   update, only if new important news emerged
//   npm run briefing -- evening     roundup of the day
//   npm run briefing -- weekly      roundup of the slower MEDIUM stories
//
// It tracks API usage and dedupes against data/log.json so it never spams or
// runs up a cost.

import path from "node:path";
import { fetchStories } from "../src/lib/pipeline";
import { sendTelegram } from "../src/lib/telegram";
import {
  formatBriefing,
  formatRoundup,
  formatWeekly,
  formatUsageWarning,
} from "../src/lib/briefing";
import {
  hydrate,
  persist,
  snapshot,
  nearLimit,
  alreadyWarned,
  markWarned,
  UsageLimitError,
} from "../src/lib/usage";
import {
  loadLog,
  saveLog,
  seenRecently,
  logStory,
  mediumLastWeek,
} from "../src/lib/store";
import type { Story } from "../src/lib/types";

const DATA = path.join(process.cwd(), "data");
const USAGE_FILE = path.join(DATA, "usage.json");
const LOG_FILE = path.join(DATA, "log.json");
const APP_URL = process.env.APP_URL || "http://localhost:3000";

type Mode = "morning" | "afternoon" | "evening" | "weekly";

function parseMode(): Mode {
  const m = (process.argv[2] || process.env.BRIEFING_MODE || "morning")
    .toLowerCase()
    .trim();
  if (m === "afternoon" || m === "evening" || m === "weekly") return m;
  return "morning";
}

const isImportant = (s: Story): boolean =>
  s.severity === "CRITICAL" || s.severity === "HIGH";

async function main(): Promise<void> {
  const mode = parseMode();
  console.log(`[briefing] mode=${mode}`);

  await hydrate(USAGE_FILE);
  const log = await loadLog(LOG_FILE);

  try {
    if (mode === "weekly") {
      const mediums = mediumLastWeek(log);
      if (mediums.length > 0) {
        await sendTelegram({ text: formatWeekly(mediums, APP_URL) });
        console.log(`[briefing] weekly roundup sent (${mediums.length} stories)`);
      } else {
        console.log("[briefing] weekly: nothing to report");
      }
    } else {
      const { stories } = await fetchStories();

      // Genuinely new stories — not covered in the last 2 days.
      const fresh = stories.filter((s) => !seenRecently(log, s.headline, 2));

      // Record every story so later runs and the weekly job can dedupe / reuse.
      for (const st of stories) {
        logStory(log, {
          headline: st.headline,
          summary: st.summary,
          why: st.why,
          domain: st.domain,
          severity: st.severity,
          mode,
        });
      }

      const important = stories.filter(isImportant);

      if (mode === "morning") {
        // The morning briefing always goes out.
        const picks = important.length > 0 ? important : stories.slice(0, 5);
        await sendTelegram({
          text: formatBriefing("Morning Briefing", picks, APP_URL),
        });
        console.log(`[briefing] morning briefing sent (${picks.length} stories)`);
      } else if (mode === "afternoon") {
        // The afternoon update only fires if something new and important emerged.
        const freshImportant = fresh.filter(isImportant);
        if (freshImportant.length > 0) {
          await sendTelegram({
            text: formatBriefing("Afternoon Update", freshImportant, APP_URL),
          });
          console.log(
            `[briefing] afternoon update sent (${freshImportant.length} new)`,
          );
        } else {
          console.log("[briefing] afternoon: nothing new — staying silent");
        }
      } else {
        // Evening roundup of the day: important stories + bundled MEDIUM ones.
        const mediums = stories.filter((s) => s.severity === "MEDIUM");
        await sendTelegram({
          text: formatRoundup(important, mediums, APP_URL),
        });
        console.log("[briefing] evening roundup sent");
      }
    }
  } catch (err) {
    if (err instanceof UsageLimitError) {
      console.log(`[briefing] ${err.message}`);
    } else {
      console.error("[briefing] failed:", err);
      process.exitCode = 1;
    }
  }

  // Cost-protection warning — sent at most once per day.
  if (nearLimit() && !alreadyWarned()) {
    try {
      await sendTelegram({ text: formatUsageWarning(snapshot()) });
      markWarned();
      console.log("[briefing] usage warning sent");
    } catch (e) {
      console.error("[briefing] could not send usage warning:", e);
    }
  }

  await persist(USAGE_FILE);
  await saveLog(LOG_FILE, log);

  const u = snapshot();
  console.log(
    `[briefing] usage today — Gemini ${u.gemini}/${u.maxGemini}, Groq ${u.groq}/${u.maxGroq}`,
  );
}

main();
