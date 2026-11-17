"use client";

import { useSyncExternalStore, type ReactNode } from "react";

const SYSTEM_DARK = "(prefers-color-scheme: dark)";

function isDark(): boolean {
  const chosen = document.documentElement.dataset.theme;
  return chosen === "dark" || (chosen === undefined && globalThis.matchMedia(SYSTEM_DARK).matches);
}

/** Tell React when the theme changes: a choice here, or the system setting. */
function watch(changed: () => void): () => void {
  const observer = new MutationObserver(changed);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const system = globalThis.matchMedia(SYSTEM_DARK);
  system.addEventListener("change", changed);
  return () => {
    observer.disconnect();
    system.removeEventListener("change", changed);
  };
}

/**
 * Switch between light and dark, and remember the choice. Until a choice is made the
 * page follows the system setting; `app/layout.tsx` applies a stored choice before
 * the first paint, so the page does not flash the other theme.
 */
export function ThemeToggle(): ReactNode {
  // The server cannot know the theme; it renders "not dark" and the browser corrects it.
  const dark = useSyncExternalStore(watch, isDark, () => false);

  function flip(): void {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private browsing may refuse storage; the choice then lasts for this visit only.
    }
  }

  return (
    <button className="round-button" type="button" onClick={flip} aria-pressed={dark} aria-label="Dark theme">
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
