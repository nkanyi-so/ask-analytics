import type { Metadata } from "next";
import type { ReactNode } from "react";

import { BarChart } from "@/components/BarChart";
import { ChangePill } from "@/components/ChangePill";
import { getReliability } from "@/lib/backend";
import { beforeLabel, formatCount, inWindow } from "@/lib/format";
import { parseWindow } from "@/lib/windows";

export const metadata: Metadata = { title: "Reliability" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ReliabilityPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const reliability = await getReliability(window);
  const { trend } = reliability;
  const against = beforeLabel(window);
  const per = trend.unit;

  return (
    <main className="view">
      <h1 className="visually-hidden">Reliability</h1>
      <section className="card" aria-labelledby="errors-chart">
        <header className="card-head">
          <div>
            <h2 id="errors-chart">Errors</h2>
            <p>
              Per {per}, {inWindow(window)}, across every tool.
            </p>
          </div>
          <span className="card-tools">
            <ChangePill value={trend.errors_change} better="down" against={against} />
            <span className="pill">{formatCount(trend.errors)} in total</span>
          </span>
        </header>
        <BarChart
          points={trend.buckets.map((bucket) => ({ label: bucket.label, value: bucket.errors }))}
          unit={trend.unit}
          tone="bad"
          summary={`Errors per ${per}`}
        />
      </section>

      <section className="card" aria-labelledby="errors-heading">
        <header className="card-head">
          <div>
            <h2 id="errors-heading">Where they came from</h2>
            <p>Grouped by source and by the tool that raised them. The change is against {against}.</p>
          </div>
        </header>
        {reliability.errors.length === 0 ? (
          <p className="empty pad">No errors in this window.</p>
        ) : (
          <table className="data" role="table">
            <thead role="rowgroup">
              <tr role="row">
                <th role="columnheader" scope="col">
                  Source
                </th>
                <th role="columnheader" scope="col" className="num">
                  Errors
                </th>
                <th role="columnheader" scope="col" className="num">
                  Change
                </th>
                <th role="columnheader" scope="col" className="num">
                  People
                </th>
                <th role="columnheader" scope="col">
                  Who it reached
                </th>
              </tr>
            </thead>
            <tbody role="rowgroup">
              {reliability.errors.map((group) => (
                <tr role="row" key={`${group.source}:${group.tool_id}`}>
                  <th role="rowheader" scope="row">
                    <span className="cell-name">{group.source.replaceAll("_", " ")}</span>
                    <small>{group.tool_name}</small>
                  </th>
                  <td role="cell" className="num strong" data-label="Errors">
                    {formatCount(group.count)}
                  </td>
                  <td role="cell" className="num" data-label="Change">
                    <ChangePill value={group.count_change} better="down" against={against} />
                  </td>
                  <td role="cell" className="num" data-label="People">
                    {formatCount(group.people_affected)}
                  </td>
                  <td role="cell" className="wide" data-label="Who it reached">
                    {group.affected.join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
