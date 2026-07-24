import { RAG } from "../../lib/brand";
import type { Rag } from "../../lib/api";

// Reuses the app's single status-color source of truth (brand.ts's RAG,
// already validated + used everywhere via RagBadge) instead of inventing a
// second palette — these are status encodings (state), not series identity.
export const PERSON_STATUS_RAG: Record<string, Rag> = {
  overloaded: "red",
  optimal: "green",
  underutilized: "amber",
};
export const PERSON_STATUS_LABEL: Record<string, string> = {
  overloaded: "Overloaded",
  optimal: "Optimal",
  underutilized: "Underutilized",
};

export const TEAM_STATUS_RAG: Record<string, Rag> = {
  critical: "red",
  overloaded: "amber",
  healthy: "green",
  low: "grey",
};
export const TEAM_STATUS_LABEL: Record<string, string> = {
  critical: "Critical",
  overloaded: "Overloaded",
  healthy: "Healthy",
  low: "Low",
};

export const PROJECT_HEALTH_RAG: Record<string, Rag> = {
  on_track: "green",
  at_risk: "amber",
  behind: "red",
};
export const PROJECT_HEALTH_LABEL: Record<string, string> = {
  on_track: "On Track",
  at_risk: "At Risk",
  behind: "Behind",
};

export function ragHex(rag: Rag): string {
  return RAG[rag].hex;
}

// antd <Tag color> wants a semantic name (success/warning/error/default), not
// the raw Rag key — RagBadge.tsx uses the same indirection.
export function ragTagColor(rag: Rag): string {
  return RAG[rag].color;
}
