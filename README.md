# 🛰 NewsAgent AI

### 🔗 Live app → **[deep-signal-mu.vercel.app](https://deep-signal-mu.vercel.app)**

**The news, actually explained.** NewsAgent AI isn't a feed — it's a multi-agent
intelligence pipeline. For every story it investigates *why* it happened, what it
echoes from history, who quietly wins and loses, and what it changes next — then
explains all of it in plain English.

It ships as a **FastAPI web app**, an **interactive Telegram bot**, a set of
**self-scheduling briefing jobs**, and a **scikit-learn ML module** — and it runs
**free, forever** on free-tier infrastructure.

---

## What it does

- **Web app** — today's important news, grouped by desk (Geopolitics, Markets,
  Technology, Health, Climate, Society). Each story expands into a *Deep Dive*
  (root causes, butterfly chain, winners/losers, historical parallels, a
  contrarian view) and a *Multi-Agent View* (five analysts who each think
  differently, then a debate-room synthesis).
- **Assistant chatbot** — ask about any topic from the website; NewsAgent AI
  investigates it and replies with its own analysis, opinion, a proposed
  solution, and predicted outcomes.
- **Telegram bot** — `/news` sends today's stories, then tap a story for NewsAgent AI's take; or send any topic for a full investigation.
- **Always-on automation** — scheduled briefings + a breaking-news monitor run
  on GitHub Actions and push alerts to Telegram.
- **ML module** — scikit-learn classifiers that categorise and score news
  offline (see [`ml/`](ml/)).

## Architecture — the multi-agent pipeline

Each agent does one focused job on a free model; independent agents run in
parallel.

| Agent | Model | Job |
|---|---|---|
| Fetcher | Gemini Flash (Google-Search grounded) | Pull live news from multiple outlets |
| Classifier | Gemini Flash-Lite | Domain + urgency + severity |
| Analyst | Gemini Flash (grounded) | Causes, connect-the-dots, narratives |
| Impact Mapper | Gemini Flash-Lite | Winners / losers / impact matrix |
| Historian | Groq Llama 4 Scout | Historical patterns, blind spots, contrarian view |
| Synthesis | Groq Llama 4 Scout | Debate — where the analysts agree vs clash |
| Verdict | Groq Llama 4 Scout | NewsAgent AI's own opinion, solution, outcomes |
| Rewriter | Groq Llama 4 Scout | Final plain-English rewrite with everyday analogies |

```
                    ┌──────────── FastAPI app ────────────┐
   Web UI  ──────►   │  /api/news  /api/search  /api/chat   │
   Telegram ─────►   │  /api/analyze  /api/agents           │  ──►  multi-agent
   GitHub Actions ►  │  /api/telegram (webhook)             │       pipeline
                    └──────────────────────────────────────┘
   scikit-learn ML module  ◄── trains on the corpus the pipeline collects
```

### Data flow (ETL)

Under the hood NewsAgent AI is a scheduled **ETL + inference pipeline**:

| Stage | What happens | Tech |
| --- | --- | --- |
| **Extract** | Grounded Gemini calls pull live stories from multiple outlets with cited sources; the web UI and Telegram webhook are the on-demand triggers, GitHub Actions cron is the scheduled one | Gemini Flash + Google-Search grounding |
| **Transform** | Seven specialised agents classify (domain / severity / urgency), analyse causes & impact, add historical context, debate, and rewrite into plain English — every LLM call returns schema-validated JSON | Gemini Flash / Flash-Lite · Groq Llama 4 Scout |
| **Load** | Structured results persist to `data/log.json` and append to the ML training corpus (`ml/data/corpus.csv`); daily API usage is metered against free-tier caps | JSON store · Git-committed data |
| **Serve** | FastAPI serves the web app + JSON API; GitHub Actions delivers briefings to Telegram; the scikit-learn module retrains on the growing corpus | FastAPI · GitHub Actions · scikit-learn |

**Production hardening:** transient `5xx`/`UNAVAILABLE` errors retry with
exponential backoff; daily API usage is hard-capped so a runaway loop can't blow
the free tier; and the two data-writing workflows share a concurrency lock so
their commits never race.

📊 Model evaluation metrics live in [`ml/README.md`](ml/README.md#evaluation-results)
— the AG News topic classifier scores **92.1%** accuracy (0.921 macro-F1).

## Tech stack

- **Backend** — Python · FastAPI · Uvicorn
- **Frontend** — server-rendered Jinja2 + vanilla JS/CSS (no build step)
- **AI** — Google Gemini Flash (grounded) · Groq Llama 4 Scout
- **ML** — scikit-learn · pandas (TF-IDF classifiers + a regressor)
- **Automation** — GitHub Actions (cron) · Telegram Bot API
- **Deploy** — Vercel (Python serverless)

---

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local        # then fill in your keys — see SETUP.md
uvicorn app.server:app --reload   # open http://localhost:8000
```

You need three **free** keys (full walkthrough in [SETUP.md](./SETUP.md)):
Gemini (<https://aistudio.google.com/apikey>), Groq
(<https://console.groq.com/keys>), and a Telegram bot via
[@BotFather](https://t.me/BotFather).

Run a briefing or the monitor by hand:

```bash
python scripts/briefing.py morning     # morning | afternoon | evening | weekly
python scripts/monitor.py              # one breaking-news scan
```

## Deploy — free, forever

1. **Web app → Vercel.** Import the repo; add `GEMINI_API_KEY`, `GROQ_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `APP_URL`
   as environment variables. `vercel.json` handles the Python serverless config.
2. **Telegram bot.** After deploy:
   `python scripts/setup_webhook.py set https://your-app.vercel.app`
3. **Automation → GitHub Actions.** Add the API keys as repo *Secrets* and
   `APP_URL` as a repo *Variable*, then enable workflows. Set
   **Settings → Actions → Workflow permissions → Read and write** so the jobs
   can commit `data/` back.

## Cost & limitations

Total cost is **$0** — every provider is free-tier only.

- Gemini's free tier allows **20 requests/day per model**. The schedule
  (~18 calls/day) is designed to fit inside it; `MAX_GEMINI_CALLS` /
  `MAX_GROQ_CALLS` are hard caps that stop a job cleanly if reached.
- Every API call is counted; at 80% of a cap you get a one-time Telegram
  heads-up. If a cap is hit, the system pauses and resumes the next day.

## Project structure

```
app/        FastAPI application
  server.py        routes · /api/chat · Telegram webhook (inline keyboard)
  pipeline.py      the 8-agent orchestration
  gemini.py · groq_client.py · prompts.py
  usage.py (caps) · store.py (dedup log) · telegram.py · briefing.py
  templates/ · static/   the web UI
api/        index.py     Vercel serverless entry point
scripts/    briefing.py · monitor.py · collect_corpus.py · setup_webhook.py
ml/         scikit-learn news classifiers — train.py · predict.py
.github/    workflows/scheduled.yml · workflows/monitor.yml
data/       usage.json · log.json   (the free JSON "database")
```
