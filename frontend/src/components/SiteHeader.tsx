import Link from "next/link";
import type { ReactNode } from "react";

import type { Window } from "@/lib/windows";

/** The same two links on every page. The chosen window travels with them. */
export function SiteHeader({ path, window }: { path: string; window: Window }): ReactNode {
  return (
    <header className="site-header">
      <Link className="brand" href={`/?window=${window}`}>
        ask-analytics
      </Link>
      <nav className="site-nav" aria-label="Pages">
        <Link href={`/?window=${window}`} aria-current={path === "/" ? "page" : undefined}>
          Overview
        </Link>
        <Link
          href={`/reliability?window=${window}`}
          aria-current={path === "/reliability" ? "page" : undefined}
        >
          Reliability
        </Link>
      </nav>
    </header>
  );
}
