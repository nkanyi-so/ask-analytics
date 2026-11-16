import type { ReactNode } from "react";

import { formatDay } from "@/lib/format";
import type { Window } from "@/lib/windows";

import { WindowSwitch } from "./WindowSwitch";

/** Where the data ends, and the window every figure below is for. */
export function DashHead({ path, window, asOf }: { path: string; window: Window; asOf: string }): ReactNode {
  return (
    <div className="dash-head">
      <p className="as-of">
        Data to <time dateTime={asOf}>{formatDay(asOf)}</time>. Seeded demo data, not a live system.
      </p>
      <WindowSwitch path={path} current={window} />
    </div>
  );
}
