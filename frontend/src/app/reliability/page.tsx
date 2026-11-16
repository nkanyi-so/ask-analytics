import type { ReactNode } from "react";

import { Change } from "@/components/Change";
import { DashHead } from "@/components/DashHead";
import { SiteHeader } from "@/components/SiteHeader";
import { getReliability } from "@/lib/backend";
import { beforeLabel, formatCount, windowLabel } from "@/lib/format";
import { parseWindow } from "@/lib/windows";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ReliabilityPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const reliability = await getReliability(window);
  const against = beforeLabel(window);

  return (
    <>
      <SiteHeader path="/reliability" window={window} />
      <main>
        <div className="intro">
          <h1>What is failing, and who it reached.</h1>
          <p>Errors grouped by where they came from and which tool raised them.</p>
        </div>

        <div className="dash">
          <DashHead path="/reliability" window={window} asOf={reliability.as_of} />
          <section className="section" aria-labelledby="errors-heading">
            <h2 id="errors-heading">
              Errors
              <span className="section-note">In {windowLabel(window)}</span>
            </h2>
            {reliability.errors.length === 0 ? (
              <p className="empty">No errors in this window.</p>
            ) : (
              <table className="data" role="table">
                <thead role="rowgroup">
                  <tr role="row">
                    <th role="columnheader" scope="col">Source</th>
                    <th role="columnheader" scope="col">Tool</th>
                    <th role="columnheader" scope="col" className="num">
                      Errors
                    </th>
                    <th role="columnheader" scope="col" className="num">
                      Change
                    </th>
                    <th role="columnheader" scope="col" className="num">
                      People affected
                    </th>
                    <th role="columnheader" scope="col">Who</th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {reliability.errors.map((group) => (
                    <tr role="row" key={`${group.source}:${group.tool_id}`}>
                      <th role="rowheader" scope="row">{group.source.replaceAll("_", " ")}</th>
                      <td role="cell" className="dim" data-label="Tool">
                        {group.tool_name}
                      </td>
                      <td role="cell" className="num" data-label="Errors">
                        {formatCount(group.count)}
                      </td>
                      <td role="cell" className="num dim" data-label="Change">
                        <Change value={group.count_change} against={against} />
                      </td>
                      <td role="cell" className="num" data-label="People affected">
                        {formatCount(group.people_affected)}
                      </td>
                      <td role="cell" className="wide" data-label="Who">
                        {group.affected.join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
