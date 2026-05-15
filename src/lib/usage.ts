// Cost protection. Tracks how many API calls each provider has made today and
// enforces a hard daily cap so the app can never run up a bill.
//
// The scheduled scripts call hydrate() at the start of a run and persist() at
// the end, keeping the count in data/usage.json (committed back to the repo by
// GitHub Actions). The interactive web app skips hydrate/persist — its counter
// just lives for the process lifetime, which is naturally bounded by the user.

import { promises as fs } from "fs";

const MAX_GEMINI = Number(process.env.MAX_GEMINI_CALLS || 20);
const MAX_GROQ = Number(process.env.MAX_GROQ_CALLS || 20);
const WARN_THRESHOLD = Number(process.env.USAGE_WARN_THRESHOLD || 0.8);

export type Provider = "gemini" | "groq";

interface UsageData {
  date: string;
  gemini: number;
  groq: number;
  warned: boolean;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fresh(): UsageData {
  return { date: today(), gemini: 0, groq: 0, warned: false };
}

let state: UsageData = fresh();

/** Thrown when a provider's daily cap is reached. The scripts catch this and
 *  stop gracefully until the next day. */
export class UsageLimitError extends Error {
  constructor(provider: Provider) {
    super(
      `Daily ${provider} API call limit reached — stopping until tomorrow to stay free.`,
    );
    this.name = "UsageLimitError";
  }
}

/** Load today's counters from disk (resetting if the file is from a past day). */
export async function hydrate(file: string): Promise<void> {
  try {
    const raw = JSON.parse(await fs.readFile(file, "utf8")) as UsageData;
    state = raw.date === today() ? { ...fresh(), ...raw, date: today() } : fresh();
  } catch {
    state = fresh();
  }
}

/** Write the current counters back to disk. */
export async function persist(file: string): Promise<void> {
  await fs.writeFile(file, JSON.stringify(state, null, 2) + "\n");
}

/** Record one API call. Throws UsageLimitError if the cap is already reached. */
export function record(provider: Provider): void {
  if (state.date !== today()) state = fresh();
  const max = provider === "gemini" ? MAX_GEMINI : MAX_GROQ;
  if (state[provider] >= max) throw new UsageLimitError(provider);
  state[provider] += 1;
}

export interface UsageSnapshot extends UsageData {
  maxGemini: number;
  maxGroq: number;
}

export function snapshot(): UsageSnapshot {
  return { ...state, maxGemini: MAX_GEMINI, maxGroq: MAX_GROQ };
}

/** True once either provider crosses the warning threshold (default 80%). */
export function nearLimit(): boolean {
  return (
    state.gemini >= MAX_GEMINI * WARN_THRESHOLD ||
    state.groq >= MAX_GROQ * WARN_THRESHOLD
  );
}

export function alreadyWarned(): boolean {
  return state.warned;
}

export function markWarned(): void {
  state.warned = true;
}
