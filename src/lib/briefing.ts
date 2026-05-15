// Builds the Telegram briefing messages (Markdown). All dynamic text is run
// through sanitizeMarkdown so it can't break Telegram's parser.

import { sanitizeMarkdown } from "./telegram";
import type { LogEntry } from "./store";
import type { ScanItem, Severity, Story } from "./types";
import type { UsageSnapshot } from "./usage";

const SEV_EMOJI: Record<Severity, string> = {
  CRITICAL: "🔴",
  HIGH: "🟠",
  MEDIUM: "🟡",
  LOW: "⚪",
};

const PIPELINE_LINE =
  "_Pipeline: Gemini 2.5 Flash + Flash-Lite · Groq Llama 4 Scout_";

function s(text: string): string {
  return sanitizeMarkdown(text);
}

function today(): string {
  return new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function footer(appUrl: string): string {
  return `${PIPELINE_LINE}\n[Open Deep Signal →](${appUrl})`;
}

function storyBlock(story: Story): string {
  return (
    `${SEV_EMOJI[story.severity]} *${s(story.headline)}*\n` +
    `${s(story.summary)}\n` +
    `_Why it matters: ${s(story.why)}_`
  );
}

/** Morning briefing / afternoon update — a list of important stories. */
export function formatBriefing(
  title: string,
  stories: Story[],
  appUrl: string,
): string {
  const blocks = stories.map(storyBlock).join("\n\n");
  return (
    `*🛰 Deep Signal — ${s(title)}*\n_${today()}_\n\n` +
    `${blocks}\n\n${footer(appUrl)}`
  );
}

/** Evening roundup — important stories plus a bundled list of slower MEDIUM ones. */
export function formatRoundup(
  important: Story[],
  mediums: Story[],
  appUrl: string,
): string {
  const head =
    important.length > 0
      ? important.map(storyBlock).join("\n\n")
      : "_A quiet day — nothing critical or high-priority broke._";

  let radar = "";
  if (mediums.length > 0) {
    const bullets = mediums
      .slice(0, 6)
      .map((m) => `• ${s(m.headline)}`)
      .join("\n");
    radar = `\n\n🟡 *Also on the radar*\n${bullets}`;
  }

  return (
    `*🛰 Deep Signal — Evening Roundup*\n_${today()}_\n\n` +
    `${head}${radar}\n\n${footer(appUrl)}`
  );
}

/** Immediate alert from the every-2-hours monitor. */
export function formatBreaking(items: ScanItem[], appUrl: string): string {
  const blocks = items
    .map(
      (it) =>
        `🔴 *${s(it.headline)}*\n${s(it.summary)}\n` +
        `_Why this is critical: ${s(it.why)}_`,
    )
    .join("\n\n");
  return (
    `🚨 *Deep Signal — Breaking*\n\n${blocks}\n\n` +
    `[Open Deep Signal →](${appUrl})`
  );
}

/** Weekly roundup of the slower MEDIUM-severity stories. */
export function formatWeekly(entries: LogEntry[], appUrl: string): string {
  const blocks = entries
    .slice(0, 12)
    .map((e) => `🟡 *${s(e.headline)}*\n${s(e.summary)}`)
    .join("\n\n");
  return (
    `*🛰 Deep Signal — Weekly Roundup*\n` +
    `_The slower-moving stories from the past week_\n\n` +
    `${blocks}\n\n[Open Deep Signal →](${appUrl})`
  );
}

/** Reply to a topic/question asked interactively via the Telegram bot. */
export function formatTopicReply(
  query: string,
  stories: Story[],
  appUrl: string,
): string {
  if (stories.length === 0) {
    return (
      `🛰 *Deep Signal*\n\n` +
      `I couldn't find anything solid on _${s(query)}_ right now — ` +
      `try rephrasing it.`
    );
  }
  const blocks = stories.map(storyBlock).join("\n\n");
  return `*🛰 Deep Signal — ${s(query)}*\n\n${blocks}\n\n${footer(appUrl)}`;
}

/** Cost-protection warning sent once when usage crosses the threshold. */
export function formatUsageWarning(u: UsageSnapshot): string {
  return (
    `⚠️ *Deep Signal — API usage warning*\n\n` +
    `Today's calls so far: Gemini ${u.gemini}/${u.maxGemini}, ` +
    `Groq ${u.groq}/${u.maxGroq}.\n\n` +
    `If a daily cap is reached the system pauses and resumes tomorrow — ` +
    `it stays free either way.`
  );
}
