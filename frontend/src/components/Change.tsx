import type { ReactNode } from "react";

import { formatChange } from "@/lib/format";

/** A change as the backend computed it, with what it is measured against for screen readers. */
export function Change({ value, against }: { value: number | null; against: string }): ReactNode {
  return (
    <>
      {formatChange(value)}
      {value === null ? null : <span className="visually-hidden"> against {against}</span>}
    </>
  );
}
