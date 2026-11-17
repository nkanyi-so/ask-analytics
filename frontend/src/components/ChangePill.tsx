import type { ReactNode } from "react";

import { formatChange } from "@/lib/format";

/** Which way is better for a measure: more outputs is good, more errors is not. */
export type Better = "up" | "down";

function Arrow({ up }: { up: boolean }): ReactNode {
  return (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d={up ? "M6 9.5v-7M2.5 6L6 2.5 9.5 6" : "M6 2.5v7M2.5 6L6 9.5 9.5 6"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * A change as the backend computed it, coloured by whether it is good news.
 * The arrow and the colour only word the sign; the number is the backend's.
 */
export function ChangePill({
  value,
  better,
  against,
}: {
  value: number | null;
  better: Better;
  against: string;
}): ReactNode {
  if (value === null) return <span className="pill">no earlier data</span>;
  if (value === 0) return <span className="pill">no change</span>;
  const up = value > 0;
  const good = up === (better === "up");
  return (
    <span className={good ? "pill good" : "pill bad"}>
      <Arrow up={up} />
      {/* The sign is shown as the arrow, so the digits are written without it. */}
      {formatChange(value).slice(1)}
      <span className="visually-hidden">
        {up ? " more" : " fewer"} than {against}
      </span>
    </span>
  );
}
