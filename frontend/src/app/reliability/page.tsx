import type { ReactNode } from "react";

import { PageHeader } from "@/components/PageHeader";
import { getReliability } from "@/lib/backend";
import { formatChange, previousLabel, windowLabel } from "@/lib/format";
import { parseWindow } from "@/lib/windows";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function ReliabilityPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const reliability = await getReliability(window);

  return (
    <main>
      <PageHeader
        title="Reliability"
        path="/reliability"
        window={window}
        asOf={reliability.as_of}
      />
      <section aria-labelledby="errors-heading">
        <h2 id="errors-heading">Errors by source, {windowLabel(window)}</h2>
        {reliability.errors.length === 0 ? (
          <p>No errors in this window.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Source</th>
                  <th scope="col">Tool</th>
                  <th scope="col" className="number">
                    Errors
                  </th>
                  <th scope="col">Change {previousLabel(window)}</th>
                  <th scope="col" className="number">
                    People affected
                  </th>
                  <th scope="col">Who was affected</th>
                </tr>
              </thead>
              <tbody>
                {reliability.errors.map((group) => (
                  <tr key={`${group.source}:${group.tool_id}`}>
                    <th scope="row">{group.source}</th>
                    <td>{group.tool_name}</td>
                    <td className="number">{group.count}</td>
                    <td>{formatChange(group.count_change)}</td>
                    <td className="number">{group.people_affected}</td>
                    <td>{group.affected.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
