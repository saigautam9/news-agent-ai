// The multi-agent pipeline. Each agent uses one model for one focused task:
//
//   1. Fetcher       Gemini 2.5 Flash (grounded)   live news, multi-source
//   2. Classifier    Gemini 2.5 Flash Lite          domain + urgency + severity
//   3. Analyst       Gemini 2.5 Flash (grounded)    causes, connect-the-dots, narratives
//   4. Impact Mapper Gemini 2.5 Flash Lite          winners/losers + impact matrix
//   5. Historian     Groq Llama 4 Scout             history, blind spots, contrarian view
//   6. Synthesis     Groq Llama 4 Scout             debate: agreement vs tension
//   7. Rewriter      Groq Llama 4 Scout             final plain-English rewrite
//
// The exported orchestrators wire these agents together; the API routes and the
// scheduled scripts call the orchestrators.

import { runGemini, extractJson, MODEL_FLASH, MODEL_LITE } from "./gemini";
import { runGroq } from "./groq";
import * as P from "./prompts";
import type {
  AgentTake,
  DeepDive,
  QuickScan,
  RawStory,
  Severity,
  Source,
  Story,
  Synthesis,
} from "./types";

type StoryRef = Pick<Story, "headline" | "summary">;

function clampUrgency(n: unknown): number {
  const v = Math.round(Number(n));
  if (!Number.isFinite(v)) return 5;
  return Math.max(1, Math.min(10, v));
}

function normalizeSeverity(s: unknown): Severity {
  const v = String(s ?? "").toUpperCase();
  return v === "CRITICAL" || v === "HIGH" || v === "MEDIUM" || v === "LOW"
    ? v
    : "MEDIUM";
}

// --- AGENT 1: News Fetcher — Gemini 2.5 Flash + Google Search grounding ---
async function agentFetch(
  query?: string,
): Promise<{ raw: RawStory[]; sources: Source[] }> {
  const date = new Date().toISOString().slice(0, 10);
  const prompt = query?.trim()
    ? P.searchFetchPrompt(query.trim(), date)
    : P.newsFetchPrompt(date);

  const { text, sources } = await runGemini({
    system: P.FETCH_SYSTEM,
    prompt,
    model: MODEL_FLASH,
    grounding: true,
  });

  const parsed = extractJson<{ stories: RawStory[] }>(text);
  const raw: RawStory[] = (parsed.stories || []).slice(0, 5).map((s) => ({
    headline: String(s.headline ?? "Untitled"),
    summary: String(s.summary ?? ""),
    why: String(s.why ?? ""),
  }));
  if (raw.length === 0) {
    throw new Error("The fetcher agent returned no stories. Try again.");
  }
  return { raw, sources };
}

// --- AGENT 2: Classifier — Gemini 2.5 Flash Lite ---
async function agentClassify(
  raw: RawStory[],
): Promise<{ domain: string; urgency: number; severity: Severity }[]> {
  const { text } = await runGemini({
    system: P.CLASSIFY_SYSTEM,
    prompt: P.classifyPrompt(raw),
    model: MODEL_LITE,
  });
  const parsed = extractJson<{
    items: { domain: string; urgency: number; severity: string }[];
  }>(text);
  return (parsed.items || []).map((it) => ({
    domain: String(it.domain || "Society"),
    urgency: clampUrgency(it.urgency),
    severity: normalizeSeverity(it.severity),
  }));
}

// --- AGENT 3: Analyst — Gemini 2.5 Flash + grounding ---
async function agentAnalyze(story: StoryRef): Promise<{
  part: Pick<
    DeepDive,
    "rootCauses" | "butterflyChain" | "connectDots" | "narratives"
  >;
  sources: Source[];
}> {
  const { text, sources } = await runGemini({
    system: P.ANALYZE_SYSTEM,
    prompt: P.analyzePrompt(story),
    model: MODEL_FLASH,
    grounding: true,
  });
  const part = extractJson<
    Pick<DeepDive, "rootCauses" | "butterflyChain" | "connectDots" | "narratives">
  >(text);
  return { part, sources };
}

// --- AGENT 4: Impact Mapper — Gemini 2.5 Flash Lite ---
async function agentImpact(
  story: StoryRef,
): Promise<Pick<DeepDive, "impacts" | "winners" | "losers">> {
  const { text } = await runGemini({
    system: P.ANALYZE_SYSTEM,
    prompt: P.impactPrompt(story),
    model: MODEL_LITE,
  });
  return extractJson<Pick<DeepDive, "impacts" | "winners" | "losers">>(text);
}

// --- AGENT 5: Historian + contrarian — Groq Llama 4 Scout ---
async function agentHistory(
  story: StoryRef,
): Promise<
  Pick<DeepDive, "historicalPattern" | "blindSpots" | "predictions" | "contrarianView">
> {
  const text = await runGroq({
    system: P.HISTORY_SYSTEM,
    prompt: P.historyPrompt(story),
  });
  return extractJson<
    Pick<
      DeepDive,
      "historicalPattern" | "blindSpots" | "predictions" | "contrarianView"
    >
  >(text);
}

// --- Multi-Agent View: 5 analyst perspectives — Gemini 2.5 Flash + grounding ---
async function agentPerspectives(
  story: StoryRef,
): Promise<{ agents: AgentTake[]; sources: Source[] }> {
  const { text, sources } = await runGemini({
    system: P.PERSPECTIVES_SYSTEM,
    prompt: P.perspectivesPrompt(story),
    model: MODEL_FLASH,
    grounding: true,
  });
  const parsed = extractJson<{ agents: AgentTake[] }>(text);
  return { agents: parsed.agents || [], sources };
}

// --- AGENT 6: Debate synthesis — Groq Llama 4 Scout ---
async function agentSynthesis(agents: AgentTake[]): Promise<Synthesis> {
  const text = await runGroq({
    system: P.SYNTHESIS_SYSTEM,
    prompt: P.synthesisPrompt(JSON.stringify({ agents })),
  });
  return extractJson<Synthesis>(text);
}

// --- AGENT 7: Rewriter — Groq Llama 4 Scout ---
// Rewrites every text value into plain English while keeping the JSON shape.
// If the rewrite drifts or fails, the original data is returned unchanged.
async function agentRewrite<T>(label: string, data: T): Promise<T> {
  try {
    const text = await runGroq({
      system: P.REWRITE_SYSTEM,
      prompt: P.rewritePrompt(label, JSON.stringify(data)),
    });
    return extractJson<T>(text);
  } catch {
    return data;
  }
}

// ===================== ORCHESTRATORS =====================

/**
 * Today's important news, or the top angles on a topic when `query` is given.
 * Fetcher → (Classifier ‖ Rewriter) → merged, ranked, severity-tagged stories.
 */
export async function fetchStories(
  query?: string,
): Promise<{ stories: Story[]; sources: Source[] }> {
  const { raw, sources } = await agentFetch(query);

  const [classes, rewritten] = await Promise.all([
    agentClassify(raw),
    agentRewrite<{ stories: RawStory[] }>("set of news stories", {
      stories: raw,
    }),
  ]);

  const stamp = Date.now();
  const stories: Story[] = raw.map((r, i) => {
    const rw = rewritten.stories?.[i];
    const cls = classes[i];
    return {
      id: `s${stamp}-${i}`,
      headline: rw?.headline || r.headline,
      summary: rw?.summary || r.summary,
      why: rw?.why || r.why,
      domain: cls?.domain || "Society",
      urgency: cls?.urgency ?? 5,
      severity: cls?.severity ?? "MEDIUM",
    };
  });
  stories.sort((a, b) => b.urgency - a.urgency);

  return { stories, sources };
}

/**
 * Full deep-dive analysis of one story.
 * (Analyst ‖ Impact Mapper ‖ Historian) → merged → Rewriter.
 */
export async function buildDeepDive(
  story: StoryRef,
): Promise<{ analysis: DeepDive; sources: Source[] }> {
  const [analysis, impact, history] = await Promise.all([
    agentAnalyze(story),
    agentImpact(story),
    agentHistory(story),
  ]);

  const merged: DeepDive = {
    rootCauses: analysis.part.rootCauses,
    butterflyChain: analysis.part.butterflyChain || [],
    connectDots: analysis.part.connectDots,
    narratives: analysis.part.narratives || [],
    impacts: impact.impacts || [],
    winners: impact.winners || [],
    losers: impact.losers || [],
    historicalPattern: history.historicalPattern,
    blindSpots: history.blindSpots || [],
    predictions: history.predictions || [],
    contrarianView: history.contrarianView,
  };

  const final = await agentRewrite<DeepDive>("deep-dive analysis", merged);
  return { analysis: final, sources: analysis.sources };
}

/**
 * Five specialist analysts weigh in, then a synthesis agent finds the debate.
 * Perspectives → Synthesis → Rewriter.
 */
export async function buildAgentTakes(
  story: StoryRef,
): Promise<{ agents: AgentTake[]; synthesis: Synthesis; sources: Source[] }> {
  const { agents, sources } = await agentPerspectives(story);
  const synthesis = await agentSynthesis(agents);
  const final = await agentRewrite<{ agents: AgentTake[]; synthesis: Synthesis }>(
    "panel of analyst views and their debate",
    { agents, synthesis },
  );
  return {
    agents: final.agents || agents,
    synthesis: final.synthesis || synthesis,
    sources,
  };
}

/**
 * Lightweight breaking-news scan for the every-2-hours monitor — one grounded
 * Gemini call. Returns whether anything CRITICAL is breaking right now.
 */
export async function quickScan(): Promise<QuickScan> {
  const date = new Date().toISOString().slice(0, 10);
  const { text } = await runGemini({
    system: P.MONITOR_SYSTEM,
    prompt: P.monitorPrompt(date),
    model: MODEL_FLASH,
    grounding: true,
  });
  const parsed = extractJson<QuickScan>(text);
  return {
    critical: Boolean(parsed.critical),
    items: (parsed.items || [])
      .slice(0, 5)
      .map((it) => ({
        headline: String(it.headline ?? ""),
        summary: String(it.summary ?? ""),
        why: String(it.why ?? ""),
      }))
      .filter((it) => it.headline),
  };
}
