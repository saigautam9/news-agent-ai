// A tiny JSON-file "database" (data/log.json) for deduplication and history.
// Committed back to the repo by GitHub Actions, so it costs nothing and lets
// the app remember what it has already covered.

import { promises as fs } from "fs";
import type { Severity } from "./types";

export interface LogEntry {
  fp: string; // fingerprint of the headline
  headline: string;
  summary: string;
  why: string;
  domain: string;
  severity: Severity;
  date: string; // YYYY-MM-DD
  mode: string; // morning | afternoon | evening | monitor
}

export interface LogStore {
  entries: LogEntry[];
}

/** A normalized fingerprint of a headline, used to detect repeat stories. */
export function fingerprint(headline: string): string {
  return headline
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .slice(0, 10)
    .join(" ");
}

function dayString(offsetDays = 0): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export async function loadLog(file: string): Promise<LogStore> {
  try {
    const raw = JSON.parse(await fs.readFile(file, "utf8")) as LogStore;
    return { entries: Array.isArray(raw.entries) ? raw.entries : [] };
  } catch {
    return { entries: [] };
  }
}

/** Save the log, trimmed to the last 30 days (and 400 entries) to stay small. */
export async function saveLog(file: string, store: LogStore): Promise<void> {
  const cutoff = dayString(-30);
  const entries = store.entries
    .filter((e) => e.date >= cutoff)
    .slice(-400);
  await fs.writeFile(file, JSON.stringify({ entries }, null, 2) + "\n");
}

/** True if a story with this headline was already logged in the last `days`. */
export function seenRecently(
  store: LogStore,
  headline: string,
  days = 2,
): boolean {
  const fp = fingerprint(headline);
  const cutoff = dayString(-(days - 1));
  return store.entries.some((e) => e.fp === fp && e.date >= cutoff);
}

/** Add a story to the log (skipped if the same story is already logged today). */
export function logStory(
  store: LogStore,
  entry: Omit<LogEntry, "fp" | "date"> & { date?: string },
): void {
  const date = entry.date || dayString(0);
  const fp = fingerprint(entry.headline);
  if (store.entries.some((e) => e.fp === fp && e.date === date)) return;
  store.entries.push({ ...entry, fp, date });
}

/** Unique MEDIUM-severity stories logged in the last 7 days — the weekly roundup. */
export function mediumLastWeek(store: LogStore): LogEntry[] {
  const cutoff = dayString(-6);
  const seen = new Set<string>();
  const out: LogEntry[] = [];
  for (const e of store.entries) {
    if (e.date < cutoff || e.severity !== "MEDIUM" || seen.has(e.fp)) continue;
    seen.add(e.fp);
    out.push(e);
  }
  return out;
}
