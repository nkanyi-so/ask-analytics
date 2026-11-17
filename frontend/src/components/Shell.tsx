"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

import { switchLabel } from "@/lib/format";
import { parseWindow, WINDOWS } from "@/lib/windows";

import { AskContext } from "./ask-context";
import { AskPanel, type AskHandle } from "./AskPanel";
import { ThemeToggle } from "./ThemeToggle";

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

// The sidebar's destinations. "Usage" holds two tabs, Overview and Reliability.
const SECTIONS = [
  { path: "/", label: "Usage", icon: "M3 3v18h18M7 15v-4M12 15V7M17 15v-6", matches: ["/", "/reliability"] },
  { path: "/about", label: "About", icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 8h.01M11 12h1v5h1", matches: ["/about"] },
] as const;

const TABS = [
  { path: "/", label: "Overview" },
  { path: "/reliability", label: "Reliability" },
] as const;

const TITLES: Record<string, { title: string; about: string }> = {
  "/": { title: "Usage", about: "Who is using what." },
  "/reliability": { title: "Usage", about: "Who is using what." },
  "/about": { title: "About this demo", about: "What it is, how it works, and how it is tested." },
};

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
  const hasTabs = TABS.some((tab) => tab.path === pathname);

  const open = useCallback(() => {
    setAsk("open");
    setOpened((count) => count + 1);
  }, []);

  const close = useCallback(() => setAsk("closed"), []);

  // A tool's name on the dashboard can hand the assistant a question: open it, then ask.
  const bridge = useMemo(
    () => ({
      live: demoMode === false,
      ask: (question: string) => {
        // Already showing when docked and never closed; otherwise open it.
        const showing = globalThis.matchMedia(DOCKED).matches;
        setAsk((state) => (state === "auto" && showing ? "auto" : "open"));
        // Opened over the page it is a dialog, and the name behind it goes inert: move
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
      <nav className="sidebar" aria-label="Sections" inert={overlay}>
        <Link className="logo" href={`/?window=${window}`} aria-label="ask-analytics, home">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 13l4.5 4.5L19 7" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Link>
        <ul>
          {SECTIONS.map((section) => (
            <li key={section.path}>
              <Link
                href={section.path === "/" ? `/?window=${window}` : section.path}
                aria-current={(section.matches as readonly string[]).includes(pathname) ? "page" : undefined}
              >
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d={section.icon} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <Pending>{section.label}</Pending>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="shell-main" inert={overlay}>
        <header className="page-head">
          <div>
            <p className="page-title">{(TITLES[pathname] ?? TITLES["/"]).title}</p>
            <p className="page-about">{(TITLES[pathname] ?? TITLES["/"]).about}</p>
          </div>
          <div className="page-tools">
            {hasTabs ? (
              <nav className="seg" aria-label="Time window">
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
            ) : null}
            <ThemeToggle />
          </div>
        </header>
        {hasTabs ? (
          <nav className="tabs" aria-label="Views">
            {TABS.map((tab) => (
              <Link key={tab.path} href={`${tab.path}?window=${window}`} aria-current={pathname === tab.path ? "page" : undefined}>
                <Pending>{tab.label}</Pending>
              </Link>
            ))}
          </nav>
        ) : null}
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
