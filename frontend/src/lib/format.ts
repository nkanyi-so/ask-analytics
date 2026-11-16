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

const SWITCH_LABELS: Record<Window, string> = { today: "Today", "7d": "7 days", "30d": "30 days" };

const BEFORE_LABELS: Record<Window, string> = {
  today: "the day before",
  "7d": "the 7 days before",
  "30d": "the 30 days before",
};

/** The short label on the window switch. */
export function switchLabel(window: Window): string {
  return SWITCH_LABELS[window];
}

/** "the 7 days before": the window a comparison is made against. */
export function beforeLabel(window: Window): string {
  return BEFORE_LABELS[window];
}

const DAY = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** "2026-10-30" as "30 Oct 2026". Wording only: the day is the backend's. */
export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

const COUNT = new Intl.NumberFormat("en-US");

/** 1234 as "1,234". */
export function formatCount(value: number): string {
  return COUNT.format(value);
}
