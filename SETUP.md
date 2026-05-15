# Setup — get your free keys

Deep Signal needs three things, all **free**. This takes about 10 minutes.
Copy `.env.example` to `.env.local` first, then fill in each value below.

```bash
cp .env.example .env.local
```

---

## 1. Google Gemini API key (free)

Powers the Fetcher, Analyst, Classifier, and Impact Mapper.

1. Go to **<https://aistudio.google.com/apikey>** and sign in with a Google account.
2. Click **Create API key** (you can use a new project).
3. Copy the key — it starts with `AI...`.
4. Put it in `.env.local`:
   ```
   GEMINI_API_KEY=AIxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

The free tier is generous and includes Google Search grounding. No card needed.

---

## 2. Groq API key (free)

Powers the Historian, the debate Synthesis, and the plain-English Rewriter.

1. Go to **<https://console.groq.com/keys>** and sign in (Google/GitHub works).
2. Click **Create API Key**, give it any name.
3. Copy the key — it starts with `gsk_`. **You only see it once.**
4. Put it in `.env.local`:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 3. Telegram bot (free)

This is how briefings reach your phone and laptop.

### a) Create the bot → get the token

1. Open Telegram and search for **@BotFather** (the one with the blue checkmark).
2. Send `/newbot`.
3. Give it a name (e.g. `My Deep Signal`) and a username ending in `bot`
   (e.g. `my_deep_signal_bot`).
4. BotFather replies with a **token** like `123456789:AAE...`. Copy it:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### b) Get your chat id

1. **Open a chat with your new bot** and send it any message (e.g. `hi`).
   This step matters — the bot can't message you until you message it first.
2. In a browser, open (paste your token in):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":123456789` — that number is your chat id:
   ```
   TELEGRAM_CHAT_ID=123456789
   ```
   *(Alternative: message **@userinfobot** on Telegram and it tells you your id.)*

---

## 4. Finish up

Set `APP_URL` to where the web app runs (keep the default for local use):

```
APP_URL=http://localhost:3000
```

That's it. Test everything:

```bash
npm install
npm run dev          # open http://localhost:3000, click "Today's Important News"
npm run monitor      # should print a scan result; sends Telegram only if critical
npm run briefing -- morning   # sends a morning briefing to your Telegram
```

If `npm run briefing -- morning` puts a message in your Telegram chat, you're done.
Next, see **[README.md](./README.md)** to deploy it free on Vercel + GitHub Actions
so it runs every day on its own.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | You're missing `.env.local` or the key line. |
| Telegram: `chat not found` | Send your bot a message first, then re-check the chat id. |
| Telegram: `bot was blocked` | Unblock the bot in Telegram. |
| `Daily ... limit reached` | Cost cap hit — it resumes tomorrow, or raise `MAX_GEMINI_CALLS`. |
| Empty / invalid model response | Free tiers can be momentarily busy — just try again. |
