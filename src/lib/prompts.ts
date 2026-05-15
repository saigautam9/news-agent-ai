import type { RawStory, Story } from "./types";

// Stable persona shared across the research agents. The goal is UNDERSTANDING,
// not headlines — investigate, compare sides, and explain it plainly.
const PERSONA =
  "You are part of Deep Signal — an intelligence system whose goal is UNDERSTANDING, " +
  "not headlines. You never just summarize; you investigate. You search several outlets " +
  "across the spectrum (e.g. Reuters, Bloomberg, Al Jazeera, South China Morning Post, " +
  "and local sources), compare how different sides frame the same event, and read between " +
  "the lines. You write in plain, simple English — like a smart friend explaining things " +
  "over chai: short sentences, no jargon, everyday analogies. You ALWAYS reply with a " +
  "single valid JSON value and nothing else — no markdown fences, no commentary.";

export const FETCH_SYSTEM = PERSONA;
export const ANALYZE_SYSTEM = PERSONA;
export const PERSPECTIVES_SYSTEM = PERSONA;
export const MONITOR_SYSTEM = PERSONA;

export const CLASSIFY_SYSTEM =
  "You are a precise news classifier. You reply with valid JSON only.";

export const HISTORY_SYSTEM =
  "You are a history professor and strategic analyst. You connect today's events to the " +
  "patterns of history, and you are willing to argue against the crowd. You reply with " +
  "valid JSON only.";

export const SYNTHESIS_SYSTEM =
  "You are a synthesis analyst who runs a debate room. You find where other analysts " +
  "agree, where they clash, and what the crowd is getting wrong. You reply with valid " +
  "JSON only.";

export const REWRITE_SYSTEM =
  "You are an expert editor. You turn dense analysis into plain, simple English that " +
  "anyone understands instantly, using everyday analogies. You reply with valid JSON only.";

// ---- AGENT 1: News Fetcher (Gemini 2.5 Flash, grounded) ----

const FETCH_SCHEMA =
  '{"stories":[{"headline":"short, clear headline",' +
  '"summary":"2-3 sentences explaining what happened",' +
  '"why":"one sentence on why it matters"}]}';

export function newsFetchPrompt(date: string): string {
  return (
    `Today is ${date}. Search across several news outlets and political perspectives for ` +
    `the most significant news happening right now. Choose the 5 stories with the largest ` +
    `real-world impact — judge by consequences for people, economies and the future, not ` +
    `by how loud the coverage is. Put the most important first.\n\n` +
    `Return ONLY this JSON:\n${FETCH_SCHEMA}`
  );
}

export function searchFetchPrompt(query: string, date: string): string {
  return (
    `Today is ${date}. The user wants to understand: "${query}". Search several outlets ` +
    `and perspectives for the latest, most relevant developments and return the 5 most ` +
    `important angles or stories on it. Put the most important first.\n\n` +
    `Return ONLY this JSON:\n${FETCH_SCHEMA}`
  );
}

// ---- AGENT 2: Classifier (Gemini 2.5 Flash Lite) ----

export function classifyPrompt(raw: RawStory[]): string {
  const list = raw
    .map((s, i) => `${i + 1}. ${s.headline} — ${s.summary}`)
    .join("\n");
  return (
    `Classify each news story below.\n\n${list}\n\n` +
    `For each story give three things:\n` +
    `- domain: exactly one of Geopolitics, Markets, Technology, Health, Climate, Society.\n` +
    `- urgency: an integer 1-10 for how much it genuinely matters.\n` +
    `- severity: exactly one of CRITICAL, HIGH, MEDIUM, LOW, using these rules:\n` +
    `    CRITICAL — wars, market crashes, major policy changes, natural disasters, major tech breakthroughs.\n` +
    `    HIGH — elections, trade deals, regulation changes, big company earnings.\n` +
    `    MEDIUM — trends, studies, slow-moving stories.\n` +
    `    LOW — celebrity news, minor updates.\n\n` +
    `Return ONLY this JSON, one item per story in the same order:\n` +
    `{"items":[{"domain":"...","urgency":0,"severity":"..."}]}`
  );
}

// ---- AGENT 3: Analyst — investigation + connect the dots (Gemini Flash, grounded) ----

export function analyzePrompt(story: Pick<Story, "headline" | "summary">): string {
  return (
    `Investigate this news story — do NOT just summarize it. Search several outlets across ` +
    `the spectrum and compare how different sides frame it.\n\n` +
    `STORY: ${story.headline}\n${story.summary}\n\n` +
    `Return ONLY this JSON:\n` +
    `{"rootCauses":{` +
    `"trigger":"the immediate event that set this off",` +
    `"buildup":"the medium-term pressures that built up",` +
    `"deepForce":"the deep structural force underneath it all"},` +
    `"butterflyChain":[{"event":"an earlier event from a SEEMINGLY UNRELATED field",` +
    `"detail":"how it quietly led toward this"}],` +
    `"connectDots":{` +
    `"fiveYearsAgo":"what happened around 5 years ago that made this almost inevitable",` +
    `"differentField":"something from a completely different field (tech, climate, culture) that contributed",` +
    `"hiddenBeneficiary":"who quietly benefits from this that almost nobody is talking about",` +
    `"officialVsReality":"the official story versus what is most likely actually going on",` +
    `"counterfactual1990":"how this would have played out differently in 1990, and why",` +
    `"sixMonthsOut":"a consequence about 6 months away that almost nobody sees coming"},` +
    `"narratives":[{"side":"e.g. Western media / Chinese media / the government / independent experts",` +
    `"framing":"how that side frames or spins this event"}]}\n` +
    `Give 3-4 items in butterflyChain and 3-4 in narratives, covering genuinely different sides.`
  );
}

// ---- AGENT 4: Impact Mapper (Gemini 2.5 Flash Lite) ----

export function impactPrompt(story: Pick<Story, "headline" | "summary">): string {
  return (
    `Map the ripple effects of this news story across society.\n\n` +
    `STORY: ${story.headline}\n${story.summary}\n\n` +
    `Return ONLY this JSON:\n` +
    `{"impacts":[{"domain":"one of: Markets, Geopolitics, Technology, Health, Climate, Society",` +
    `"impact":"the concrete effect","signal":"exactly one of: bullish, bearish, tension, watch"}],` +
    `"winners":["who quietly benefits"],"losers":["who quietly loses"]}\n` +
    `Give 4 impacts, 3 winners and 3 losers.`
  );
}

// ---- AGENT 5: Historian + contrarian check (Groq Llama 4 Scout) ----

export function historyPrompt(story: Pick<Story, "headline" | "summary">): string {
  return (
    `Think like a history professor. A news story is below.\n\n` +
    `STORY: ${story.headline}\n${story.summary}\n\n` +
    `Return ONLY this JSON:\n` +
    `{"historicalPattern":{` +
    `"parallel":"a specific similar event from history",` +
    `"lesson":"what that history teaches us about now",` +
    `"divergence":"the key way this time is genuinely different"},` +
    `"blindSpots":["an important angle that mainstream coverage keeps missing"],` +
    `"predictions":[{"horizon":"e.g. 3 months / 1 year","prediction":"what is likely to happen"}],` +
    `"contrarianView":"argue AGAINST the mainstream opinion on this story — if almost ` +
    `everyone believes one thing, make the strongest honest case for the opposite"}\n` +
    `Give 3 blindSpots and 3 predictions.`
  );
}

// ---- Multi-Agent View: 5 analysts, each thinking differently (Gemini Flash, grounded) ----

export function perspectivesPrompt(
  story: Pick<Story, "headline" | "summary">,
): string {
  return (
    `Five expert analysts each examine this story. Each MUST think in their own distinct ` +
    `way — not generic commentary. Search the web for context.\n\n` +
    `STORY: ${story.headline}\n${story.summary}\n\n` +
    `The analysts and how each one thinks:\n` +
    `1. Geopolitics Analyst (🌍) — thinks like a diplomat: who gains power, who loses it.\n` +
    `2. Markets Analyst (📈) — thinks like a hedge fund manager: where the money flows.\n` +
    `3. Technology Analyst (💻) — thinks like a Silicon Valley founder: what gets disrupted.\n` +
    `4. Society Analyst (👥) — thinks like a public health researcher: how real people are affected.\n` +
    `5. Historian (📜) — thinks like a professor: what pattern from history is repeating.\n\n` +
    `Return ONLY this JSON:\n` +
    `{"agents":[{"role":"Geopolitics Analyst","emoji":"🌍","lens":"Thinks like a diplomat",` +
    `"take":"their distinct perspective — what THEY specifically see and why this happened",` +
    `"historicalConnection":"a historical event or pattern they connect it to",` +
    `"prediction":"what they expect to happen next"}]}\n` +
    `Include all five analysts in the order above, each clearly thinking in their own style.`
  );
}

// ---- Debate Mode: synthesis of the 5 analysts (Groq Llama 4 Scout) ----

export function synthesisPrompt(takesJson: string): string {
  return (
    `Below are five analysts' views on the same story, as JSON. Act as the synthesis ` +
    `analyst running the debate room.\n\n${takesJson}\n\n` +
    `Return ONLY this JSON:\n` +
    `{"agreement":"the key thing all or most analysts agree on",` +
    `"tension":"where the analysts most clearly DISAGREE with each other, and why that ` +
    `disagreement itself is the real insight",` +
    `"contrarian":"the strongest honest case against the mainstream view of this story"}`
  );
}

// ---- Continuous monitor: lightweight breaking-news scan (Gemini Flash, grounded) ----

export function monitorPrompt(date: string): string {
  return (
    `Today is ${date}. Search the web for major breaking news from the last few hours.\n` +
    `Decide if anything is CRITICAL — an outbreak of war or a sharp military escalation, a ` +
    `market crash, a major natural disaster, a major government or policy change, or a ` +
    `major technology breakthrough. Ordinary or slow-moving news is NOT critical.\n\n` +
    `Return ONLY this JSON:\n` +
    `{"critical":true or false,"items":[{"headline":"",` +
    `"summary":"what happened","why":"why this is genuinely critical"}]}\n` +
    `If nothing is genuinely critical, return {"critical":false,"items":[]}.`
  );
}

// ---- AGENT 6: Rewriter — plain English, chai-friend tone (Groq Llama 4 Scout) ----

export function rewritePrompt(label: string, json: string): string {
  return (
    `Below is a JSON object containing a ${label}. Rewrite every piece of text inside it ` +
    `into plain, simple English — the way a smart friend explains things to you over chai. ` +
    `Short sentences. No jargon. When something is technical, use an everyday analogy ` +
    `(for example: "bond yields are like the interest rate on a country's credit card"). ` +
    `The reader should feel SMARTER after reading it.\n\n` +
    `Strict rules:\n` +
    `- Keep every JSON key exactly the same.\n` +
    `- Keep the same structure and the same number of items in every array.\n` +
    `- Do not add, remove, merge or reorder items.\n` +
    `- Only rewrite the text values so they are clearer and simpler.\n` +
    `Return ONLY the rewritten JSON.\n\nJSON:\n${json}`
  );
}
