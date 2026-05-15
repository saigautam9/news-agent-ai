// Builds the training corpus for the ML module (ml/).
//
// Runs Deep Signal's own fetch + classify pipeline across many topics, so every
// story comes back already labelled with a domain, an urgency score and a
// severity. The labelled rows are written to ml/data/corpus.csv.
//
//   npm run collect-corpus
//
// The npm script raises MAX_GEMINI_CALLS / MAX_GROQ_CALLS for this run so the
// daily safety cap doesn't interrupt the collection.

import { promises as fs } from "node:fs";
import path from "node:path";
import { fetchStories } from "../src/lib/pipeline";

// Diverse topics spread across all six domains, so the classifier sees a
// balanced range of news rather than one slice.
const TOPICS = [
  "US China relations",
  "Russia Ukraine war",
  "Middle East conflict",
  "India foreign policy",
  "European Union politics",
  "North Korea tensions",
  "stock market movements",
  "inflation and interest rates",
  "cryptocurrency markets",
  "global oil prices",
  "international trade tariffs",
  "big tech company earnings",
  "artificial intelligence",
  "semiconductor industry",
  "electric vehicles",
  "space exploration",
  "cybersecurity threats",
  "social media regulation",
  "global disease outbreaks",
  "healthcare policy",
  "mental health crisis",
  "pharmaceutical industry",
  "climate change impact",
  "renewable energy transition",
  "extreme weather events",
  "environmental policy",
  "education reform",
  "immigration policy",
  "labor market and jobs",
  "global housing crisis",
];

function csvCell(v: string | number): string {
  return `"${String(v).replace(/"/g, '""')}"`;
}

async function main(): Promise<void> {
  const outDir = path.join(process.cwd(), "ml", "data");
  await fs.mkdir(outDir, { recursive: true });
  const file = path.join(outDir, "corpus.csv");

  const rows: string[] = ["headline,summary,why,domain,urgency,severity"];
  const seen = new Set<string>();

  for (const topic of TOPICS) {
    try {
      const { stories } = await fetchStories(topic);
      let added = 0;
      for (const st of stories) {
        const key = st.headline.toLowerCase().slice(0, 60);
        if (seen.has(key)) continue; // skip near-duplicate stories
        seen.add(key);
        rows.push(
          [st.headline, st.summary, st.why, st.domain, st.urgency, st.severity]
            .map(csvCell)
            .join(","),
        );
        added++;
      }
      console.log(
        `[collect] ${topic} → +${added} (corpus: ${rows.length - 1})`,
      );
    } catch (e) {
      console.error(
        `[collect] ${topic} failed:`,
        e instanceof Error ? e.message : e,
      );
    }
  }

  await fs.writeFile(file, rows.join("\n") + "\n");
  console.log(`[collect] done — ${rows.length - 1} labelled rows → ${file}`);
}

main();
