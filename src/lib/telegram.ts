// Sends notifications to a private Telegram chat via the Telegram Bot API.
// Set up your bot with @BotFather and put the token + chat id in .env.local.
// See README.md ("Telegram setup") for the full walkthrough.

/**
 * Removes characters that would break Telegram's legacy Markdown parser.
 * Legacy Markdown has no escape syntax, so dynamic text (headlines, summaries)
 * must be stripped of these before being placed inside the message.
 */
export function sanitizeMarkdown(text: string): string {
  return text
    .replace(/[_*`[\]]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

interface TelegramOpts {
  /** Message body, already formatted with Markdown. */
  text: string;
  /** Destination chat — defaults to TELEGRAM_CHAT_ID (the owner). The
   *  interactive bot passes the chat that messaged it so it can reply there. */
  chatId?: string | number;
}

export async function sendTelegram({ text, chatId }: TelegramOpts): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const to = chatId ?? process.env.TELEGRAM_CHAT_ID;
  if (!token || !to) {
    throw new Error(
      "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set — see README.md (Telegram setup).",
    );
  }

  const res = await fetch(
    `https://api.telegram.org/bot${token}/sendMessage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: to,
        text,
        parse_mode: "Markdown",
        disable_web_page_preview: true,
      }),
    },
  );

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { description?: string };
      if (body.description) detail = body.description;
    } catch {
      /* keep the status-line detail */
    }
    throw new Error(`Telegram sendMessage failed: ${detail}`);
  }
}
