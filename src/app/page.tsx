"use client";

import { useState } from "react";
import type {
  AgentTake,
  DeepDive,
  Severity,
  Source,
  StoriesResponse,
  Story,
  Synthesis,
} from "@/lib/types";

// ---------------------------------------------------------------- constants

const QUICK_BRIEFS = [
  "US-China relations",
  "AI regulation",
  "Global markets",
  "Climate policy",
  "Middle East",
];

const SEVERITY: Record<Severity, { label: string; color: string; dot: string }> = {
  CRITICAL: { label: "CRITICAL", color: "#ef4444", dot: "🔴" },
  HIGH: { label: "HIGH", color: "#f59e0b", dot: "🟠" },
  MEDIUM: { label: "MEDIUM", color: "#eab308", dot: "🟡" },
  LOW: { label: "LOW", color: "#64748b", dot: "⚪" },
};

const SIGNAL_COLOR: Record<string, string> = {
  bullish: "#22c55e",
  bearish: "#ef4444",
  tension: "#f59e0b",
  watch: "#38bdf8",
};

// ---------------------------------------------------------------- types

interface ResultSet {
  key: string;
  label: string;
  stories: Story[];
  sources: Source[];
}

interface Detail {
  open: "deep" | "agents" | null;
  loading: "deep" | "agents" | null;
  error?: string;
  deep?: DeepDive;
  deepSources?: Source[];
  agents?: AgentTake[];
  synthesis?: Synthesis;
  agentSources?: Source[];
}

// ---------------------------------------------------------------- helpers

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data as T;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data as T;
}

// ================================================================ page

export default function Home() {
  const [result, setResult] = useState<ResultSet | null>(null);
  const [history, setHistory] = useState<ResultSet[]>([]);
  const [details, setDetails] = useState<Record<string, Detail>>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patchDetail(id: string, patch: Partial<Detail>) {
    setDetails((d) => {
      const prev: Detail = d[id] ?? { open: null, loading: null };
      return { ...d, [id]: { ...prev, ...patch } };
    });
  }

  async function runStories(label: string, url: string, body?: unknown) {
    setLoading(true);
    setError(null);
    try {
      const data = body
        ? await postJson<StoriesResponse>(url, body)
        : await getJson<StoriesResponse>(url);
      const rs: ResultSet = {
        key: `${Date.now()}`,
        label,
        stories: data.stories,
        sources: data.sources,
      };
      setResult(rs);
      setHistory((h) =>
        [rs, ...h.filter((x) => x.label !== label)].slice(0, 8),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const loadToday = () => runStories("Today's Briefing", "/api/news");
  const search = (q: string) => {
    const term = q.trim();
    if (term) runStories(`“${term}”`, "/api/search", { query: term });
  };

  async function toggleDeep(story: Story) {
    const cur = details[story.id];
    if (cur?.open === "deep") return patchDetail(story.id, { open: null });
    if (cur?.deep) return patchDetail(story.id, { open: "deep" });
    patchDetail(story.id, { open: "deep", loading: "deep", error: undefined });
    try {
      const data = await postJson<{ analysis: DeepDive; sources: Source[] }>(
        "/api/analyze",
        { story: { headline: story.headline, summary: story.summary } },
      );
      patchDetail(story.id, {
        loading: null,
        deep: data.analysis,
        deepSources: data.sources,
      });
    } catch (e) {
      patchDetail(story.id, {
        loading: null,
        error: e instanceof Error ? e.message : "Analysis failed.",
      });
    }
  }

  async function toggleAgents(story: Story) {
    const cur = details[story.id];
    if (cur?.open === "agents") return patchDetail(story.id, { open: null });
    if (cur?.agents) return patchDetail(story.id, { open: "agents" });
    patchDetail(story.id, {
      open: "agents",
      loading: "agents",
      error: undefined,
    });
    try {
      const data = await postJson<{
        agents: AgentTake[];
        synthesis: Synthesis;
        sources: Source[];
      }>("/api/agents", {
        story: { headline: story.headline, summary: story.summary },
      });
      patchDetail(story.id, {
        loading: null,
        agents: data.agents,
        synthesis: data.synthesis,
        agentSources: data.sources,
      });
    } catch (e) {
      patchDetail(story.id, {
        loading: null,
        error: e instanceof Error ? e.message : "Analysis failed.",
      });
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-5 py-10">
      {/* ---- header ---- */}
      <header className="mb-8">
        <div className="flex items-center gap-2 font-mono text-xs tracking-[0.3em] text-[#f5a623]">
          <span className="signal-pulse">●</span> DEEP SIGNAL
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-[#e8eef6]">
          The news, actually explained.
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-[#6b7a8d]">
          Not a feed. A multi-agent intelligence pipeline that investigates why
          something happened, what it echoes from history, who quietly wins, and
          what it changes next — in plain English.
        </p>
      </header>

      {/* ---- controls ---- */}
      <section className="rounded-xl border border-[#1f2933] bg-[#121821] p-4">
        <button
          onClick={loadToday}
          disabled={loading}
          className="w-full rounded-lg bg-[#f5a623] py-3 text-sm font-semibold text-[#0a0e14] transition hover:bg-[#ffb733] disabled:opacity-50"
        >
          ▸ Today&apos;s Important News
        </button>

        <div className="mt-3 flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search(query)}
            placeholder="Investigate any topic — “Fed policy”, “Taiwan”…"
            className="min-w-0 flex-1 rounded-lg border border-[#1f2933] bg-[#0a0e14] px-3 py-2 text-sm text-[#c9d4e3] outline-none placeholder:text-[#46566a] focus:border-[#f5a623]"
          />
          <button
            onClick={() => search(query)}
            disabled={loading}
            className="rounded-lg border border-[#2d3a48] px-4 text-sm text-[#c9d4e3] transition hover:border-[#f5a623] disabled:opacity-50"
          >
            Search
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {QUICK_BRIEFS.map((q) => (
            <button
              key={q}
              onClick={() => search(q)}
              disabled={loading}
              className="rounded-full border border-[#1f2933] px-3 py-1 font-mono text-xs text-[#6b7a8d] transition hover:border-[#f5a623] hover:text-[#c9d4e3] disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      {/* ---- history ---- */}
      {history.length > 1 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[#46566a]">
            Session
          </span>
          {history.map((h) => (
            <button
              key={h.key}
              onClick={() => setResult(h)}
              className={`rounded px-2 py-0.5 font-mono text-xs transition ${
                result?.key === h.key
                  ? "bg-[#1f2933] text-[#f5a623]"
                  : "text-[#6b7a8d] hover:text-[#c9d4e3]"
              }`}
            >
              {h.label}
            </button>
          ))}
        </div>
      )}

      {/* ---- status ---- */}
      {loading && (
        <p className="mt-6 font-mono text-sm text-[#f5a623]">
          <span className="signal-pulse">●</span> Agents working — fetch → classify
          → rewrite…
        </p>
      )}
      {error && (
        <p className="mt-6 rounded-lg border border-[#ef4444]/40 bg-[#ef4444]/10 px-4 py-3 text-sm text-[#fca5a5]">
          {error}
        </p>
      )}

      {/* ---- results ---- */}
      {result && !loading && (
        <section className="mt-6">
          <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-[#6b7a8d]">
            {result.label} — {result.stories.length} stories
          </h2>
          <div className="space-y-3">
            {result.stories.map((s) => (
              <StoryCard
                key={s.id}
                story={s}
                detail={details[s.id]}
                onDeep={() => toggleDeep(s)}
                onAgents={() => toggleAgents(s)}
              />
            ))}
          </div>
          <SourceList sources={result.sources} label="Fetched from" />
        </section>
      )}

      {/* ---- empty state ---- */}
      {!result && !loading && !error && <AutomationCard />}

      <footer className="mt-12 border-t border-[#1f2933] pt-5 font-mono text-[11px] leading-relaxed text-[#46566a]">
        <p>
          Pipeline · Gemini 2.5 Flash + Flash-Lite (fetch, classify, analyze) ·
          Groq Llama 4 Scout (history, debate, plain-English rewrite)
        </p>
        <p className="mt-1">
          Runs itself free via GitHub Actions — morning / afternoon / evening
          briefings, a breaking-news scan every 2 hours, alerts to Telegram.
        </p>
      </footer>
    </main>
  );
}

// ================================================================ story card

function StoryCard({
  story,
  detail,
  onDeep,
  onAgents,
}: {
  story: Story;
  detail?: Detail;
  onDeep: () => void;
  onAgents: () => void;
}) {
  const sev = SEVERITY[story.severity] ?? SEVERITY.MEDIUM;
  const d = detail ?? { open: null, loading: null };

  return (
    <article className="rounded-xl border border-[#1f2933] bg-[#121821] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-wider"
          style={{ color: sev.color, border: `1px solid ${sev.color}55` }}
        >
          {sev.dot} {sev.label}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[#6b7a8d]">
          {story.domain}
        </span>
        <span className="font-mono text-[10px] text-[#46566a]">
          urgency {story.urgency}/10
        </span>
      </div>

      <h3 className="mt-2 text-base font-semibold leading-snug text-[#e8eef6]">
        {story.headline}
      </h3>
      <p className="mt-1.5 text-sm leading-relaxed text-[#aab7c7]">
        {story.summary}
      </p>
      <p className="mt-2 border-l-2 border-[#f5a623]/50 pl-2.5 text-sm italic text-[#8b97a8]">
        Why it matters: {story.why}
      </p>

      <div className="mt-3 flex gap-2">
        <DetailButton
          active={d.open === "deep"}
          loading={d.loading === "deep"}
          onClick={onDeep}
          label="Deep Dive"
        />
        <DetailButton
          active={d.open === "agents"}
          loading={d.loading === "agents"}
          onClick={onAgents}
          label="Multi-Agent View"
        />
      </div>

      {d.loading && (
        <p className="mt-3 font-mono text-xs text-[#f5a623]">
          <span className="signal-pulse">●</span>{" "}
          {d.loading === "deep"
            ? "Investigating — causes, dots, narratives, history…"
            : "Five analysts debating this story…"}
        </p>
      )}
      {d.error && (
        <p className="mt-3 text-xs text-[#fca5a5]">{d.error}</p>
      )}

      {d.open === "deep" && d.deep && (
        <DeepDivePanel deep={d.deep} sources={d.deepSources ?? []} />
      )}
      {d.open === "agents" && d.agents && (
        <AgentsPanel
          agents={d.agents}
          synthesis={d.synthesis}
          sources={d.agentSources ?? []}
        />
      )}
    </article>
  );
}

function DetailButton({
  active,
  loading,
  onClick,
  label,
}: {
  active: boolean;
  loading: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition disabled:opacity-50 ${
        active
          ? "border-[#f5a623] text-[#f5a623]"
          : "border-[#2d3a48] text-[#c9d4e3] hover:border-[#f5a623]"
      }`}
    >
      {active ? "▾ " : "▸ "}
      {label}
    </button>
  );
}

// ================================================================ deep dive

function DeepDivePanel({
  deep,
  sources,
}: {
  deep: DeepDive;
  sources: Source[];
}) {
  return (
    <div className="mt-4 space-y-4 border-t border-[#1f2933] pt-4">
      <Section title="Why it happened">
        <Row k="Trigger" v={deep.rootCauses?.trigger} />
        <Row k="Build-up" v={deep.rootCauses?.buildup} />
        <Row k="Deep force" v={deep.rootCauses?.deepForce} />
      </Section>

      {deep.butterflyChain?.length > 0 && (
        <Section title="Butterfly chain">
          <ol className="space-y-2">
            {deep.butterflyChain.map((b, i) => (
              <li key={i} className="text-sm">
                <span className="font-mono text-xs text-[#f5a623]">
                  {String(i + 1).padStart(2, "0")}
                </span>{" "}
                <span className="text-[#e8eef6]">{b.event}</span>
                <span className="block pl-6 text-[#8b97a8]">{b.detail}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {deep.connectDots && (
        <Section title="Connecting the dots">
          <Row k="5 years ago" v={deep.connectDots.fiveYearsAgo} />
          <Row k="From another field" v={deep.connectDots.differentField} />
          <Row k="Hidden beneficiary" v={deep.connectDots.hiddenBeneficiary} />
          <Row k="Official vs reality" v={deep.connectDots.officialVsReality} />
          <Row k="If this were 1990" v={deep.connectDots.counterfactual1990} />
          <Row k="6 months out" v={deep.connectDots.sixMonthsOut} />
        </Section>
      )}

      {deep.narratives?.length > 0 && (
        <Section title="Who's saying what">
          {deep.narratives.map((n, i) => (
            <Row key={i} k={n.side} v={n.framing} />
          ))}
        </Section>
      )}

      {deep.impacts?.length > 0 && (
        <Section title="Impact map">
          <div className="space-y-1.5">
            {deep.impacts.map((im, i) => {
              const c = SIGNAL_COLOR[im.signal?.toLowerCase()] ?? "#6b7a8d";
              return (
                <div key={i} className="flex gap-2 text-sm">
                  <span
                    className="mt-0.5 h-fit rounded px-1.5 py-0.5 font-mono text-[10px] uppercase"
                    style={{ color: c, border: `1px solid ${c}55` }}
                  >
                    {im.signal}
                  </span>
                  <span className="text-[#aab7c7]">
                    <span className="text-[#e8eef6]">{im.domain}:</span>{" "}
                    {im.impact}
                  </span>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {deep.winners?.length > 0 && (
          <Section title="Quiet winners">
            <List items={deep.winners} bullet="▲" color="#22c55e" />
          </Section>
        )}
        {deep.losers?.length > 0 && (
          <Section title="Quiet losers">
            <List items={deep.losers} bullet="▼" color="#ef4444" />
          </Section>
        )}
      </div>

      {deep.historicalPattern && (
        <Section title="Historical pattern">
          <Row k="Parallel" v={deep.historicalPattern.parallel} />
          <Row k="Lesson" v={deep.historicalPattern.lesson} />
          <Row k="But different" v={deep.historicalPattern.divergence} />
        </Section>
      )}

      {deep.blindSpots?.length > 0 && (
        <Section title="What coverage misses">
          <List items={deep.blindSpots} bullet="◇" color="#38bdf8" />
        </Section>
      )}

      {deep.predictions?.length > 0 && (
        <Section title="What happens next">
          {deep.predictions.map((p, i) => (
            <Row key={i} k={p.horizon} v={p.prediction} />
          ))}
        </Section>
      )}

      {deep.contrarianView && (
        <Section title="Contrarian check">
          <p className="rounded-lg border border-[#f5a623]/30 bg-[#f5a623]/5 p-3 text-sm leading-relaxed text-[#d8b878]">
            {deep.contrarianView}
          </p>
        </Section>
      )}

      <SourceList sources={sources} label="Investigated via" />
    </div>
  );
}

// ================================================================ agents

function AgentsPanel({
  agents,
  synthesis,
  sources,
}: {
  agents: AgentTake[];
  synthesis?: Synthesis;
  sources: Source[];
}) {
  return (
    <div className="mt-4 space-y-3 border-t border-[#1f2933] pt-4">
      {agents.map((a, i) => (
        <div
          key={i}
          className="rounded-lg border border-[#1f2933] bg-[#0d131b] p-3"
        >
          <div className="flex items-baseline gap-2">
            <span className="text-base">{a.emoji}</span>
            <span className="text-sm font-semibold text-[#e8eef6]">
              {a.role}
            </span>
            <span className="font-mono text-[10px] text-[#f5a623]">
              {a.lens}
            </span>
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-[#aab7c7]">
            {a.take}
          </p>
          <p className="mt-1.5 text-xs text-[#8b97a8]">
            <span className="text-[#6b7a8d]">History rhymes with:</span>{" "}
            {a.historicalConnection}
          </p>
          <p className="mt-1 text-xs text-[#8b97a8]">
            <span className="text-[#6b7a8d]">Expects:</span> {a.prediction}
          </p>
        </div>
      ))}

      {synthesis && (
        <div className="rounded-lg border border-[#f5a623]/30 bg-[#f5a623]/5 p-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#f5a623]">
            Debate room
          </div>
          <Row k="They agree" v={synthesis.agreement} />
          <Row k="They clash" v={synthesis.tension} />
          <Row k="Contrarian" v={synthesis.contrarian} />
        </div>
      )}

      <SourceList sources={sources} label="Researched via" />
    </div>
  );
}

// ================================================================ shared bits

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-[#f5a623]">
        {title}
      </h4>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v?: string }) {
  if (!v) return null;
  return (
    <p className="mt-1 text-sm leading-relaxed text-[#aab7c7]">
      <span className="text-[#6b7a8d]">{k}:</span> {v}
    </p>
  );
}

function List({
  items,
  bullet,
  color,
}: {
  items: string[];
  bullet: string;
  color: string;
}) {
  return (
    <ul className="space-y-1">
      {items.map((it, i) => (
        <li key={i} className="text-sm leading-relaxed text-[#aab7c7]">
          <span style={{ color }}>{bullet}</span> {it}
        </li>
      ))}
    </ul>
  );
}

function SourceList({
  sources,
  label,
}: {
  sources: Source[];
  label: string;
}) {
  if (!sources?.length) return null;
  return (
    <div className="mt-4">
      <span className="font-mono text-[10px] uppercase tracking-widest text-[#46566a]">
        {label}
      </span>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
        {sources.slice(0, 12).map((s, i) => (
          <a
            key={i}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="truncate text-xs text-[#6b7a8d] underline decoration-dotted hover:text-[#f5a623]"
            style={{ maxWidth: "14rem" }}
          >
            {s.title}
          </a>
        ))}
      </div>
    </div>
  );
}

function AutomationCard() {
  const rows = [
    ["08:00", "Full morning briefing — always sent"],
    ["every 2h", "Silent scan — pings only if something critical breaks"],
    ["14:00", "Afternoon update — only if new important news emerged"],
    ["20:00", "Evening roundup of the day"],
  ];
  return (
    <section className="mt-6 rounded-xl border border-[#1f2933] bg-[#121821] p-5">
      <h2 className="font-mono text-xs uppercase tracking-widest text-[#f5a623]">
        Always on — and free
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-[#8b97a8]">
        Deep Signal runs itself on GitHub Actions. It decides what is worth your
        attention by severity, so it never spams you:
      </p>
      <div className="mt-3 space-y-1.5">
        {rows.map(([t, d]) => (
          <div key={t} className="flex gap-3 text-sm">
            <span className="w-20 shrink-0 font-mono text-xs text-[#f5a623]">
              {t}
            </span>
            <span className="text-[#aab7c7]">{d}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-sm text-[#6b7a8d]">
        Briefings land in Telegram. Hit{" "}
        <span className="text-[#c9d4e3]">Today&apos;s Important News</span>{" "}
        above to run the pipeline live right now.
      </p>
    </section>
  );
}
