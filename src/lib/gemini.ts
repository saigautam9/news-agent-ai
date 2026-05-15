import { GoogleGenAI } from "@google/genai";
import type { Source } from "./types";
import { record } from "./usage";

// Two free-tier Gemini models, each with a focused role in the pipeline.
export const MODEL_FLASH = process.env.GEMINI_MODEL || "gemini-2.5-flash";
export const MODEL_LITE =
  process.env.GEMINI_LITE_MODEL || "gemini-2.5-flash-lite";

let ai: GoogleGenAI | null = null;

function getClient(): GoogleGenAI {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GEMINI_API_KEY is not set. Create a free key at https://aistudio.google.com/apikey and add it to .env.local — see SETUP.md.",
    );
  }
  if (!ai) ai = new GoogleGenAI({ apiKey });
  return ai;
}

export interface GeminiResult {
  text: string;
  sources: Source[];
}

interface RunOpts {
  system: string;
  prompt: string;
  /** Which Gemini model to use — defaults to Flash. */
  model?: string;
  /** Enable Google Search grounding (live web access). Default false. */
  grounding?: boolean;
}

/**
 * Runs a single Gemini call. With grounding on, Gemini searches the live web
 * via Google Search before answering and we return the cited sources.
 * Every call is counted against the daily cost-protection cap first.
 */
export async function runGemini({
  system,
  prompt,
  model = MODEL_FLASH,
  grounding = false,
}: RunOpts): Promise<GeminiResult> {
  record("gemini"); // throws UsageLimitError if the daily cap is reached
  const client = getClient();

  const res = await client.models.generateContent({
    model,
    contents: prompt,
    config: {
      systemInstruction: system,
      // Grounding cannot be combined with a JSON response schema, so when it's
      // off we ask Gemini for raw JSON output; when it's on we parse the text.
      ...(grounding
        ? { tools: [{ googleSearch: {} }] }
        : { responseMimeType: "application/json" }),
    },
  });

  const text = res.text;
  if (!text || !text.trim()) {
    throw new Error("Gemini returned an empty response. Try again in a moment.");
  }

  const chunks = res.candidates?.[0]?.groundingMetadata?.groundingChunks ?? [];
  const seen = new Set<string>();
  const sources: Source[] = [];
  for (const c of chunks) {
    const url = c.web?.uri;
    if (!url || seen.has(url)) continue;
    seen.add(url);
    sources.push({ title: c.web?.title || url, url });
  }

  return { text, sources };
}

/**
 * Pulls a JSON value out of a model response. Tolerates markdown code fences
 * and stray prose around the JSON.
 */
export function extractJson<T>(text: string): T {
  let t = text.trim();

  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) t = fence[1].trim();

  const firstObj = t.indexOf("{");
  const firstArr = t.indexOf("[");
  let start = -1;
  let end = -1;

  if (firstArr !== -1 && (firstObj === -1 || firstArr < firstObj)) {
    start = firstArr;
    end = t.lastIndexOf("]");
  } else {
    start = firstObj;
    end = t.lastIndexOf("}");
  }

  if (start === -1 || end === -1 || end <= start) {
    throw new Error("Could not find JSON in the model response.");
  }

  try {
    return JSON.parse(t.slice(start, end + 1)) as T;
  } catch {
    throw new Error("The model response was not valid JSON. Try again.");
  }
}

export function errMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
