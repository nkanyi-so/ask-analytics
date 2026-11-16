import type { ReactNode } from "react";

import { AskPanel } from "@/components/AskPanel";
import { Change } from "@/components/Change";
import { DashHead } from "@/components/DashHead";
import { SiteHeader } from "@/components/SiteHeader";
import { getHealth, getOverview } from "@/lib/backend";
import { beforeLabel, formatCount, formatDay, windowLabel } from "@/lib/format";
import type { RosterPerson } from "@/lib/types";
import { parseWindow } from "@/lib/windows";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function Names({ label, people }: { label: string; people: RosterPerson[] }): ReactNode {
  if (people.length === 0) return null;
  return (
    <p className="names">
      <strong>{label}:</strong> {people.map((person) => person.name).join(", ")}
    </p>
  );
}

function Figure({
  label,
  value,
  change,
  against,
}: {
  label: string;
  value: number;
  /** `undefined` when the measure has no comparison at all. */
  change?: number | null;
  against: string;
}): ReactNode {
  return (
    <div>
      <p className="figure-value">{formatCount(value)}</p>
      <p className="figure-label">{label}</p>
      {change === undefined ? null : (
        <p className="figure-change">
          <Change value={change} against={against} />
          {change === null ? "" : ` from ${against}`}
        </p>
      )}
    </div>
  );
}

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const [overview, health] = await Promise.all([getOverview(window), getHealth()]);
  const { roster } = overview;
  const against = beforeLabel(window);

  return (
    <>
      <SiteHeader path="/" window={window} />
      <main>
        <div className="intro">
          <h1>Who is using what, across a workspace of {formatCount(roster.invited_count)} people.</h1>
          <p>
            Ask a question. The assistant can only answer with numbers this page can derive, and it shows
            its working.
          </p>
        </div>
        <AskPanel demoMode={health.demo_mode} />

        <div className="dash">
          <DashHead path="/" window={window} asOf={overview.as_of} />

          <section className="section" aria-labelledby="people-heading">
            <h2 id="people-heading">
              People
              <span className="section-note">In {windowLabel(window)}</span>
            </h2>
            <div>
              <div className="figures">
                <Figure label="active" value={roster.active_count} change={roster.active_count_change} against={against} />
                <Figure
                  label="went quiet"
                  value={roster.went_quiet_count}
                  change={roster.went_quiet_count_change}
                  against={against}
                />
                <Figure label="never showed up" value={roster.never_showed_up_count} against={against} />
                <Figure label="invited" value={roster.invited_count} against={against} />
              </div>
              <Names label="Went quiet" people={roster.went_quiet} />
              <Names label="Never showed up" people={roster.never_showed_up} />
            </div>
          </section>

          <section className="section" aria-labelledby="tools-heading">
            <h2 id="tools-heading">
              Tools
              <span className="section-note">One headline number each: the event that means the tool did its job.</span>
            </h2>
            <table className="data" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">Tool</th>
                  <th role="columnheader" scope="col">Counts</th>
                  <th role="columnheader" scope="col" className="num">
                    Output
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Change
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Active people
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Errors
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {overview.usage_by_tool.map((tool) => (
                  <tr role="row" key={tool.tool_id}>
                    <th role="rowheader" scope="row">{tool.tool_name}</th>
                    <td role="cell" className="dim" data-label="Counts">
                      {tool.headline_event.replaceAll("_", " ")}
                    </td>
                    <td role="cell" className="num" data-label="Output">
                      {formatCount(tool.headline_count)}
                    </td>
                    <td role="cell" className="num dim" data-label="Change">
                      <Change value={tool.headline_count_change} against={against} />
                    </td>
                    <td role="cell" className="num" data-label="Active people">
                      {formatCount(tool.active_people)}
                    </td>
                    <td role="cell" className="num" data-label="Errors">
                      {formatCount(tool.errors)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="section" aria-labelledby="clients-heading">
            <h2 id="clients-heading">
              Clients
              <span className="section-note">Outputs are headline events, across all tools.</span>
            </h2>
            <table className="data" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">Client</th>
                  <th role="columnheader" scope="col" className="num">
                    Outputs
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Change
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Active people
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {overview.activity_by_client.map((client) => (
                  <tr role="row" key={client.client_id}>
                    <th role="rowheader" scope="row">{client.client_name}</th>
                    <td role="cell" className="num" data-label="Outputs">
                      {formatCount(client.outputs)}
                    </td>
                    <td role="cell" className="num dim" data-label="Change">
                      <Change value={client.outputs_change} against={against} />
                    </td>
                    <td role="cell" className="num" data-label="Active people">
                      {formatCount(client.active_people)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="section" aria-labelledby="persons-heading">
            <h2 id="persons-heading">
              Everyone
              <span className="section-note">Each person invited, whether or not they have logged in.</span>
            </h2>
            <table className="data" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">Person</th>
                  <th role="columnheader" scope="col">Client</th>
                  <th role="columnheader" scope="col">Role</th>
                  <th role="columnheader" scope="col" className="num">
                    Logins
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Outputs
                  </th>
                  <th role="columnheader" scope="col">Last seen</th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {overview.activity_by_person.map((person) => (
                  <tr role="row" key={person.user_id}>
                    <th role="rowheader" scope="row">{person.name}</th>
                    <td role="cell" className="dim" data-label="Client">
                      {person.client_name}
                    </td>
                    <td role="cell" className="dim" data-label="Role">
                      {person.role}
                    </td>
                    <td role="cell" className="num" data-label="Logins">
                      {formatCount(person.logins)}
                    </td>
                    <td role="cell" className="num" data-label="Outputs">
                      {formatCount(person.outputs)}
                    </td>
                    <td role="cell" className="dim" data-label="Last seen">
                      {person.last_seen === null ? "never" : formatDay(person.last_seen)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </>
  );
}
