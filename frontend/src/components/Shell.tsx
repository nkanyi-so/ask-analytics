"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { switchLabel } from "@/lib/format";
import { parseWindow, WINDOWS } from "@/lib/windows";

import { AskContext } from "./ask-context";
import { AskPanel, type AskHandle } from "./AskPanel";

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
  { path: "/about", label: "About" },
] as const;

// The window switch has nothing to drive on a view with no figures.
const NO_WINDOW = new Set<string>(["/about"]);

/** The link's own words, dimmed for the moment between a press and the new numbers. */
function Pending({ children }: { children: ReactNode }): ReactNode {
  const { pending } = useLinkStatus();
  return <span className={pending ? "pending" : undefined}>{children}</span>;
}

/**
 * The frame every view sits in: one header, the view, and the assistant beside it.
 * Mounted once in the layout, so the assistant and its answers survive a change of view.
 */
export function Shell({ demoMode, children }: { demoMode: boolean | null; children: ReactNode }): ReactNode {
  const pathname = usePathname();
  const window = parseWindow(useSearchParams().get("window") ?? undefined);
  const [ask, setAsk] = useState<AskState>("auto");
  const [opened, setOpened] = useState(0);
  const panel = useRef<AskHandle>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const docked = useDocked();
  // Laid over the page, the assistant is a dialog: the page behind it is out of reach.
  const overlay = ask === "open" && !docked;

  const open = useCallback(() => {
    setAsk("open");
    setOpened((count) => count + 1);
  }, []);

  const close = useCallback(() => setAsk("closed"), []);

  // A tile on the dashboard can hand the assistant a question: open it, then ask.
  const bridge = useMemo(
    () => ({
      live: demoMode === false,
      ask: (question: string) => {
        // Already showing when docked and never closed; otherwise open it.
        const showing = globalThis.matchMedia(DOCKED).matches;
        setAsk((state) => (state === "auto" && showing ? "auto" : "open"));
        // Opened over the page it is a dialog, and the tile behind it goes inert: move
        // focus into the panel, as the launcher does.
        setOpened((count) => count + 1);
        panel.current?.ask(question);
      },
    }),
    [demoMode],
  );

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
    if (ask !== "auto") return;
    const query = globalThis.matchMedia(DOCKED);
    // A real resize only: a page that loads narrow must not grab focus.
    function onChange(event: MediaQueryListEvent): void {
      if (!event.matches && document.activeElement === document.body) launcher.current?.focus();
    }
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [ask]);

  return (
    <AskContext value={bridge}>
    <div className="shell" data-ask={ask}>
      <div className="shell-main" inert={overlay}>
        <div className="site-bar">
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
                <Pending>{view.label}</Pending>
              </Link>
            ))}
          </nav>
          {NO_WINDOW.has(pathname) ? null : (
            <nav className="window-switch" aria-label="Time window">
              {WINDOWS.map((each) => (
                <Link
                  key={each}
                  href={`${pathname}?window=${each}`}
                  aria-current={each === window ? "page" : undefined}
                  // The numbers change in place; keep the reader where they are.
                  scroll={false}
                >
                  <Pending>{switchLabel(each)}</Pending>
                </Link>
              ))}
            </nav>
          )}
        </header>
        </div>
        {children}
      </div>

      {/* Only present when the panel lies over the page; a click on it closes the panel. */}
      <div className="scrim" onClick={close} aria-hidden="true" />
      <AskPanel demoMode={demoMode} opened={opened} modal={overlay} handle={panel} onClose={close} />
      <button className="launcher" type="button" ref={launcher} onClick={open}>
        Ask a question
      </button>
    </div>
    </AskContext>
  );
}
