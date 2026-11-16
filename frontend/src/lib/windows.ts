// The three windows every lookup accepts. The backend owns their meaning;
// the frontend only passes the name through.
export const WINDOWS = ["today", "7d", "30d"] as const;

export type Window = (typeof WINDOWS)[number];

export const DEFAULT_WINDOW: Window = "7d";

export function parseWindow(value: string | string[] | undefined): Window {
  const candidate: string | undefined = Array.isArray(value) ? value[0] : value;
  return WINDOWS.find((window) => window === candidate) ?? DEFAULT_WINDOW;
}
