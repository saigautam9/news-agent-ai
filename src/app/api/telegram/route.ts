// Telegram webhook — lets you *chat* with Deep Signal.
//
// Telegram POSTs every message your bot receives to this route. Send the bot a
// topic ("US tariffs", "what's happening with OpenAI?") and it runs the live
// pipeline and replies right there in the chat.
//
// Setup (after deploying):  npm run webhook -- set https://your-app.vercel.app
// See README.md ("Chat with the bot").

import { NextResponse } from "next/server";
import { fetchStories, buildVerdict } from "@/lib/pipeline";
import { sendTelegram, sanitizeMarkdown } from "@/lib/telegram";
import { formatTopicReply, formatVerdictReply } from "@/lib/briefing";
import { errMessage } from "@/lib/gemini";

export const runtime = "nodejs";
export const maxDuration = 60;
export const dynamic = "force-dynamic";

const HELP = [
  "🛰 *Deep Signal*",
  "",
  "Send me any topic or question and I'll run the live multi-agent",
  "pipeline and reply with the stories that actually matter:",
  "",
  "• `US tariffs`",
  "• `what's happening with OpenAI?`",
  "• `India monsoon`",
  "",
  "_Analysis runs on Gemini 2.5 Flash (Google-Search grounded) +",
  "Flash-Lite, with Groq Llama 4 Scout for the plain-English rewrite._",
].join("\n");

interface TgUpdate {
  message?: {
    chat?: { id?: number | string };
    text?: string;
  };
}

export async function POST(req: Request) {
  // 1. Verify the request really came from Telegram (shared secret token).
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
  if (
    secret &&
    req.headers.get("x-telegram-bot-api-secret-token") !== secret
  ) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  let update: TgUpdate;
  try {
    update = (await req.json()) as TgUpdate;
  } catch {
    return NextResponse.json({ ok: true }); // ignore malformed updates
  }

  const chatId = update.message?.chat?.id;
  const text = (update.message?.text || "").trim();
  if (!chatId || !text) return NextResponse.json({ ok: true });

  // 2. Owner-only — anyone could find a public bot, and every reply spends
  //    free-tier API quota. Only the configured chat gets answered.
  const owner = process.env.TELEGRAM_CHAT_ID;
  if (owner && String(chatId) !== String(owner)) {
    await sendTelegram({
      chatId,
      text: "Sorry — this is a private Deep Signal bot.",
    }).catch(() => {});
    return NextResponse.json({ ok: true });
  }

  // 3. Commands.
  if (text === "/start" || text === "/help") {
    await sendTelegram({ chatId, text: HELP }).catch(() => {});
    return NextResponse.json({ ok: true });
  }

  // 4. Treat anything else as a topic to investigate.
  const appUrl = process.env.APP_URL || "http://localhost:3000";
  try {
    await sendTelegram({
      chatId,
      text: `🛰 Investigating *${sanitizeMarkdown(text)}* and forming my take — one moment…`,
    }).catch(() => {});

    const { stories } = await fetchStories(text);
    if (stories.length === 0) {
      await sendTelegram({ chatId, text: formatTopicReply(text, stories, appUrl) });
    } else {
      const [top, ...others] = stories;
      const verdict = await buildVerdict(text, top);
      await sendTelegram({
        chatId,
        text: formatVerdictReply(text, top, verdict, others, appUrl),
      });
    }
  } catch (e) {
    await sendTelegram({
      chatId,
      text: `Sorry — that didn't work: ${sanitizeMarkdown(errMessage(e))}`,
    }).catch(() => {});
  }

  return NextResponse.json({ ok: true });
}
