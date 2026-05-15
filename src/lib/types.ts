// Shared types used by the API routes, the scheduled scripts, and the UI.

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Story {
  id: string;
  headline: string;
  summary: string;
  domain: string;
  urgency: number; // 1-10
  severity: Severity;
  why: string;
}

/** A story before the Classifier agent has scored it. */
export type RawStory = Pick<Story, "headline" | "summary" | "why">;

export interface Source {
  title: string;
  url: string;
}

export interface DeepDive {
  rootCauses: {
    trigger: string;
    buildup: string;
    deepForce: string;
  };
  butterflyChain: { event: string; detail: string }[];
  // "Connect the dots" — the questions that turn news into understanding.
  connectDots: {
    fiveYearsAgo: string;
    differentField: string;
    hiddenBeneficiary: string;
    officialVsReality: string;
    counterfactual1990: string;
    sixMonthsOut: string;
  };
  // Investigation mode — how different sides frame the same event.
  narratives: { side: string; framing: string }[];
  impacts: { domain: string; impact: string; signal: string }[];
  winners: string[];
  losers: string[];
  historicalPattern: {
    parallel: string;
    lesson: string;
    divergence: string;
  };
  blindSpots: string[];
  predictions: { horizon: string; prediction: string }[];
  contrarianView: string;
}

export interface AgentTake {
  role: string;
  emoji: string;
  lens: string; // the distinct way this analyst thinks
  take: string;
  historicalConnection: string;
  prediction: string;
}

/** Debate mode — where the analysts agree, clash, and break from the mainstream. */
export interface Synthesis {
  agreement: string;
  tension: string;
  contrarian: string;
}

export interface ScanItem {
  headline: string;
  summary: string;
  why: string;
}
export interface QuickScan {
  critical: boolean;
  items: ScanItem[];
}

// ---- API response shapes ----
export interface StoriesResponse {
  stories: Story[];
  sources: Source[];
}
export interface DeepDiveResponse {
  analysis: DeepDive;
  sources: Source[];
}
export interface AgentsResponse {
  agents: AgentTake[];
  synthesis: Synthesis;
  sources: Source[];
}
export interface ErrorResponse {
  error: string;
}
