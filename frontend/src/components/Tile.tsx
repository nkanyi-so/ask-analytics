import type { ReactNode } from "react";

import { formatChange } from "@/lib/format";

interface TileProps {
  label: string;
  value: number;
  note?: string;
  /** `undefined` hides the line; `null` means the backend had nothing to compare with. */
  change?: number | null;
  against?: string;
}

export function Tile({ label, value, note, change, against }: TileProps): ReactNode {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {note ? <div className="tile-note">{note}</div> : null}
      {change !== undefined ? (
        <div className="tile-change">
          {formatChange(change)}
          {change !== null && against ? ` ${against}` : ""}
        </div>
      ) : null}
    </div>
  );
}
