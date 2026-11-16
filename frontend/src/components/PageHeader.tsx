import Link from "next/link";
import type { ReactNode } from "react";

import type { Window } from "@/lib/windows";

import { WindowSwitch } from "./WindowSwitch";

interface PageHeaderProps {
  title: string;
  path: string;
  window: Window;
  asOf: string;
}

export function PageHeader({ title, path, window, asOf }: PageHeaderProps): ReactNode {
  return (
    <header className="page-header">
      <nav className="tabs" aria-label="Pages">
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
      <h1>{title}</h1>
      <p className="as-of">
        Data as of <time dateTime={asOf}>{asOf}</time>. Seeded demo data, not a live system.
      </p>
      <WindowSwitch path={path} current={window} />
    </header>
  );
}
