import Link from "next/link";
import type { ReactNode } from "react";

import { windowLabel } from "@/lib/format";
import { WINDOWS, type Window } from "@/lib/windows";

export function WindowSwitch({ path, current }: { path: string; current: Window }): ReactNode {
  return (
    <nav className="window-switch" aria-label="Time window">
      {WINDOWS.map((window) => (
        <Link
          key={window}
          href={`${path}?window=${window}`}
          aria-current={window === current ? "page" : undefined}
        >
          {windowLabel(window)}
        </Link>
      ))}
    </nav>
  );
}
