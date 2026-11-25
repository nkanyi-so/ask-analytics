import type { ReactNode } from "react";

import { bucketLabel, formatCount } from "@/lib/format";

export interface Point {
  label: string;
  value: number;
}

const LABEL_EVERY_BAR_UP_TO = 10;
const AXIS_TICKS = 8;

/**
 * One bar per bucket. Bars are drawn to the tallest one; that proportion is the only
 * thing worked out here, and it is never shown as a number. Every figure printed is
 * a count from the backend.
 */
export function BarChart({
  points,
  unit,
  tone = "brand",
  summary,
}: {
  points: Point[];
  unit: "hour" | "day";
  tone?: "brand" | "bad";
  /** What the chart shows, for a screen reader, e.g. "Outputs per day". */
  summary: string;
}): ReactNode {
  const tallest = Math.max(1, ...points.map((point) => point.value));
  const labelBars = points.length <= LABEL_EVERY_BAR_UP_TO;
  const tickEvery = Math.ceil(points.length / AXIS_TICKS);
  const columns = { gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` };
  const spoken = points.map((point) => `${bucketLabel(point.label, unit)}: ${formatCount(point.value)}`).join(", ");

  return (
    <figure className="chart" data-dense={!labelBars}>
      <div className="plot" style={columns} role="img" aria-label={`${summary}. ${spoken}.`}>
        {points.map((point) => (
          <div
            key={point.label}
            className={tone === "bad" ? "bar bad" : "bar"}
            style={{ height: `${(point.value / tallest) * 100}%` }}
            title={`${bucketLabel(point.label, unit)}: ${formatCount(point.value)}`}
          >
            {labelBars ? <span>{formatCount(point.value)}</span> : null}
          </div>
        ))}
      </div>
      <div className="axis" style={columns} aria-hidden="true">
        {points.map((point, index) => (
          <span key={point.label}>
            {index % tickEvery === 0 ? (
              <>
                {/* The weekday is dropped where there is no room for it. */}
                <span className="wide-only">{bucketLabel(point.label, unit)}</span>
                <span className="narrow-only">{bucketLabel(point.label, unit).split(" ").at(-1)}</span>
              </>
            ) : null}
          </span>
        ))}
      </div>
    </figure>
  );
}

/** A row-sized version: the shape of one tool's activity, no labels. */
export function Sparkline({ values, label }: { values: number[]; label: string }): ReactNode {
  const tallest = Math.max(1, ...values);
  const flat = values.every((value) => value === 0);
  return (
    <span className={flat ? "sparkline none" : "sparkline"} role="img" aria-label={label}>
      {values.map((value, index) => (
        <i key={index} style={{ height: `${(value / tallest) * 100}%` }} />
      ))}
    </span>
  );
}
