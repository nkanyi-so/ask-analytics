// Wording only. Every number shown is a field from the API; nothing here adds,
// subtracts or counts.
import type { Window } from "./windows";

const WINDOW_LABELS: Record<Window, string> = {
  today: "today",
  "7d": "the last 7 days",
  "30d": "the last 30 days",
};

const PREVIOUS_LABELS: Record<Window, string> = {
  today: "vs the day before",
  "7d": "vs the 7 days before",
  "30d": "vs the 30 days before",
};

export function windowLabel(window: Window): string {
  return WINDOW_LABELS[window];
}

export function previousLabel(window: Window): string {
  return PREVIOUS_LABELS[window];
}

/** A change as the backend computed it: "+5", "−41", "no change". */
export function formatChange(change: number | null): string {
  if (change === null) return "no earlier data";
  if (change === 0) return "no change";
  // The sign is the backend's; this only picks a typographic minus.
  return change > 0 ? `+${change}` : `−${String(change).slice(1)}`;
}
