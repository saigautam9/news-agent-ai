import Groq from "groq-sdk";
import { record } from "./usage";

// Free-tier Groq model — Llama 4 Scout. Handles historical reasoning, debate
// synthesis, and the final plain-English rewrite step of the pipeline.
export const GROQ_MODEL =
  process.env.GROQ_MODEL || "meta-llama/llama-4-scout-17b-16e-instruct";

let groq: Groq | null = null;

function getClient(): Groq {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GROQ_API_KEY is not set. Create a free key at https://console.groq.com/keys and add it to .env.local — see SETUP.md.",
    );
  }
  if (!groq) groq = new Groq({ apiKey });
  return groq;
}

interface RunOpts {
  system: string;
  prompt: string;
}

/** Runs a single Groq (Llama 4 Scout) call in JSON mode. Counted against the
 *  daily cost-protection cap first. */
export async function runGroq({ system, prompt }: RunOpts): Promise<string> {
  record("groq"); // throws UsageLimitError if the daily cap is reached

  const res = await getClient().chat.completions.create({
    model: GROQ_MODEL,
    temperature: 0.4,
    response_format: { type: "json_object" },
    messages: [
      { role: "system", content: system },
      { role: "user", content: prompt },
    ],
  });

  const content = res.choices[0]?.message?.content;
  if (!content || !content.trim()) {
    throw new Error("Groq returned an empty response. Try again in a moment.");
  }
  return content;
}
