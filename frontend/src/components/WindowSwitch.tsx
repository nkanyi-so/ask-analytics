import Link from "next/link";
import type { ReactNode } from "react";

import { switchLabel } from "@/lib/format";
import { WINDOWS, type Window } from "@/lib/windows";

export function WindowSwitch({ path, current }: { path: string; current: Window }): ReactNode {
  return (
    <nav className="window-switch" aria-label="Time window">
      {WINDOWS.map((window) => (
        <Link
          key={window}
          href={`${path}?window=${window}`}
          aria-current={window === current ? "page" : undefined}
          // The page changes below the switch; keep the reader where they are.
          scroll={false}
        >
          {switchLabel(window)}
        </Link>
      ))}
    </nav>
  );
}
