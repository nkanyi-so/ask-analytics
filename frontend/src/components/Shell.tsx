"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { switchLabel } from "@/lib/format";
import { parseWindow, WINDOWS } from "@/lib/windows";

import { AskPanel } from "./AskPanel";

/** "auto" follows the screen: docked open where there is room, closed where there is not. */
type AskState = "auto" | "open" | "closed";

// Below this width the panel cannot sit beside the dashboard, so it opens over it.
// Keep in step with the `80rem` media query in globals.css.
const DOCKED = "(min-width: 80rem)";

function watchDocked(onChange: () => void): () => void {
  const query = globalThis.matchMedia(DOCKED);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** Is there room for the assistant beside the dashboard? Assumed so until the browser says. */
function useDocked(): boolean {
  return useSyncExternalStore(
    watchDocked,
    () => globalThis.matchMedia(DOCKED).matches,
    () => true,
  );
}

const VIEWS = [
  { path: "/", label: "Overview" },
  { path: "/reliability", label: "Reliability" },
] as const;

/**
 * The frame every view sits in: one header, the view, and the assistant beside it.
 * Mounted once in the layout, so the assistant and its answers survive a change of view.
 */
export function Shell({ demoMode, children }: { demoMode: boolean | null; children: ReactNode }): ReactNode {
  const pathname = usePathname();
  const window = parseWindow(useSearchParams().get("window") ?? undefined);
  const [ask, setAsk] = useState<AskState>("auto");
  const [opened, setOpened] = useState(0);
  const launcher = useRef<HTMLButtonElement>(null);
  const docked = useDocked();
  // Laid over the page, the assistant is a dialog: the page behind it is out of reach.
  const overlay = ask === "open" && !docked;

  const open = useCallback(() => {
    setAsk("open");
    setOpened((count) => count + 1);
  }, []);

  const close = useCallback(() => setAsk("closed"), []);

  // Closing hands focus back to the launcher. It can only take focus once it is shown,
  // which is after this render, so the hand-back waits for the state to land.
  useEffect(() => {
    if (ask === "closed") launcher.current?.focus();
  }, [ask]);

  // Escape closes the panel when it lies over the page. Docked, it is part of the page.
  useEffect(() => {
    if (!overlay) return;
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") close();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [overlay, close]);

  // When the window narrows, a docked panel that was never opened by hand disappears.
  // If the cursor was inside it, hand focus to the launcher rather than lose it.
  useEffect(() => {
    if (!docked && ask === "auto" && document.activeElement === document.body) launcher.current?.focus();
  }, [docked, ask]);

  return (
    <div className="shell" data-ask={ask}>
      <div className="shell-main" inert={overlay}>
        <header className="site-header">
          <Link className="brand" href={`/?window=${window}`}>
            ask-analytics
          </Link>
          <nav className="site-nav" aria-label="Views">
            {VIEWS.map((view) => (
              <Link
                key={view.path}
                href={`${view.path}?window=${window}`}
                aria-current={pathname === view.path ? "page" : undefined}
              >
                {view.label}
              </Link>
            ))}
          </nav>
          <nav className="window-switch" aria-label="Time window">
            {WINDOWS.map((each) => (
              <Link
                key={each}
                href={`${pathname}?window=${each}`}
                aria-current={each === window ? "page" : undefined}
                // The numbers change in place; keep the reader where they are.
                scroll={false}
              >
                {switchLabel(each)}
              </Link>
            ))}
          </nav>
        </header>
        {children}
      </div>

      {/* Only present when the panel lies over the page; a click on it closes the panel. */}
      <div className="scrim" onClick={close} aria-hidden="true" />
      <AskPanel demoMode={demoMode} opened={opened} modal={overlay} onClose={close} />
      <button className="launcher" type="button" ref={launcher} onClick={open}>
        Ask a question
      </button>
    </div>
  );
}
