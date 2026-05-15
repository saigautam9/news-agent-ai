# 🛰 Deep Signal

**The news, actually explained.** Deep Signal isn't a feed — it's a multi-agent
intelligence pipeline. For every story it investigates *why* it happened, what it
echoes from history, who quietly wins and loses, and what it changes next — then
explains all of it in plain English, like a smart friend talking it through over chai.

It runs itself **for free, forever**: scheduled briefings + a breaking-news monitor
on GitHub Actions, with alerts pushed to Telegram.

---

## What it does

- **Today's briefing** — the 5 stories that genuinely matter right now, ranked.
- **Deep Dive** — root causes, the butterfly chain, "connect the dots" (what made
  this inevitable, the hidden beneficiary, official story vs reality, a 1990
  counterfactual, what's coming in 6 months), how different sides spin it, an
  impact map, historical parallels, blind spots, predictions, and a contrarian view.
- **Multi-Agent View** — five analysts who each *think differently* (a diplomat, a
  hedge-fund manager, a Silicon Valley founder, a public-health researcher, a
  historian), then a debate-room synthesis that surfaces where they clash.
- **Always-on monitoring** — decides what is worth your attention by severity, so
  it never spams you.

## The multi-agent pipeline

Each agent does one focused job, on a free model:

| Agent | Model | Job |
|---|---|---|
| Fetcher | Gemini 2.5 Flash (Google Search grounded) | Pull live news from multiple outlets |
| Classifier | Gemini 2.5 Flash Lite | Domain + urgency + severity |
| Analyst | Gemini 2.5 Flash (grounded) | Causes, connect-the-dots, narratives |
| Impact Mapper | Gemini 2.5 Flash Lite | Winners / losers / impact matrix |
| Historian | Groq Llama 4 Scout | Historical patterns, blind spots, contrarian view |
| Synthesis | Groq Llama 4 Scout | Debate — where the analysts agree vs clash |
| Rewriter | Groq Llama 4 Scout | Final plain-English rewrite with everyday analogies |

## How the notifications work

It is **not** three fixed pings a day — it decides:

| When | What happens |
|---|---|
| **08:00** | Full morning briefing — always sent |
| **every 2 hours** | Silent breaking-news scan — pings you *only* if something CRITICAL breaks |
| **14:00** | Afternoon update — sent *only* if new important stories emerged |
| **20:00** | Evening roundup of the day |
| **Sun 20:30** | Weekly roundup of the slower-moving stories |

Severity decides what reaches you: **CRITICAL/HIGH** → notified; **MEDIUM** → bundled
into roundups; **LOW** → skipped. Most days that's 2-3 messages. Quiet days, maybe
just the morning briefing.

---

## Quick start (local)

```bash
npm install
cp .env.example .env.local     # then fill in your keys — see SETUP.md
npm run dev                    # open http://localhost:3000
```

You need three **free** keys (full walkthrough in **[SETUP.md](./SETUP.md)**):

1. **Gemini** — <https://aistudio.google.com/apikey>
2. **Groq** — <https://console.groq.com/keys>
3. **Telegram bot** — via [@BotFather](https://t.me/BotFather)

Run a briefing or the monitor by hand:

```bash
npm run briefing -- morning      # morning | afternoon | evening | weekly
npm run monitor                  # one breaking-news scan
```

---

## Deploy — free, forever

### 1. The web app → Vercel

Push this folder to a GitHub repo, import it at [vercel.com](https://vercel.com),
and add `GEMINI_API_KEY` + `GROQ_API_KEY` as environment variables. Vercel's free
tier is enough. Copy the deployed URL.

### 2. The automation → GitHub Actions

The scheduled briefings and the 2-hour monitor run as GitHub Actions — free for
public repos (and 2,000 free minutes/month for private ones). In your repo:

**Settings → Secrets and variables → Actions → Secrets**, add:

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | your Gemini key |
| `GROQ_API_KEY` | your Groq key |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHAT_ID` | your chat id |

**Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
|---|---|
| `APP_URL` | your Vercel URL (for the "Open Deep Signal" link) |
| `MAX_GEMINI_CALLS` | optional — defaults to `20` |
| `MAX_GROQ_CALLS` | optional — defaults to `20` |

Then open the **Actions** tab and enable workflows. Use **Run workflow** on
*Deep Signal — Scheduled Briefings* to test it immediately.

> The jobs commit `data/usage.json` and `data/log.json` back to the repo — that's
> the free "database" for cost tracking and deduplication. They need write access:
> **Settings → Actions → General → Workflow permissions → Read and write**.

### Adjusting the schedule (timezone)

GitHub Actions cron is **UTC**. Edit the `cron:` lines in
[`.github/workflows/scheduled.yml`](./.github/workflows/scheduled.yml) to your
timezone — `UTC = local time − your offset`:

| You want 8am in… | UTC cron |
|---|---|
| UK (UTC+0) | `0 8 * * *` |
| India (UTC+5:30) | `30 2 * * *` |
| US Eastern (UTC−5) | `0 13 * * *` |
| US Pacific (UTC−8) | `0 16 * * *` |

(If you change a time, also update the matching line in the workflow's
`Pick mode from schedule` step.)

---

## Cost protection

Total cost is **$0** — every provider is free-tier only. On top of that:

- Hard daily caps (`MAX_GEMINI_CALLS`, `MAX_GROQ_CALLS`, default 20 each). If a cap
  is hit, the job stops cleanly and resumes the next day.
- Every API call is logged to `data/usage.json`.
- At 80% of a cap you get a one-time Telegram heads-up.

The schedule uses ~18 Gemini calls/day (12 monitor scans + 3 briefings), which
fits inside the default cap. If you add lots of manual runs, raise the caps — the
free tiers allow far more than 20/day.

## Project structure

```
src/lib/      pipeline.ts (orchestration) · gemini.ts · groq.ts · prompts.ts
              usage.ts (cost caps) · store.ts (dedup log) · telegram.ts · briefing.ts
src/app/      page.tsx (UI) · api/{news,search,analyze,agents}/route.ts
scripts/      briefing.mts · monitor.mts        (run by GitHub Actions)
.github/      workflows/scheduled.yml · workflows/monitor.yml
data/         usage.json · log.json             (the free JSON "database")
```

## Notes

- A deep dive runs ~4 model calls and takes 15-30s; the news list ~20s. The API
  routes allow 60s.
- Free tiers have rate limits — fine for personal use. If Groq renames the Llama 4
  Scout model, set `GROQ_MODEL` in your env.
- Telegram messages use Markdown; dynamic text is sanitized so it can't break.
