import type { ReactNode } from "react";

import { Card } from "@/components/Card";
import { Change } from "@/components/Change";
import { getOverview } from "@/lib/backend";
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
  const overview = await getOverview(window);
  const { roster } = overview;
  const against = beforeLabel(window);

  return (
    <main className="view">
      <div className="view-head">
        <h1>Overview</h1>
        <p>
          Who is using what, across a workspace of {formatCount(roster.invited_count)} people, in{" "}
          {windowLabel(window)}. Data to <time dateTime={overview.as_of}>{formatDay(overview.as_of)}</time>;
          seeded demo data, not a live system.
        </p>
      </div>

      <section className="block" aria-labelledby="tools-heading">
        <header className="block-head">
          <h2 id="tools-heading">One headline number per tool</h2>
          <p>The event that means the tool did its job. Change is against {against}.</p>
        </header>
        <ul className="tiles">
          {overview.usage_by_tool.map((tool) => (
            <li className="tile" key={tool.tool_id}>
              {/* The name comes first for a screen reader; the number is shown above it. */}
              <h3 className="tile-name">{tool.tool_name}</h3>
              <p className="tile-value">{formatCount(tool.headline_count)}</p>
              <p className="tile-what">{tool.headline_event.replaceAll("_", " ")}</p>
              <dl className="tile-more">
                <div>
                  <dt>Change</dt>
                  <dd>
                    <Change value={tool.headline_count_change} against={against} />
                  </dd>
                </div>
                <div>
                  <dt>Active people</dt>
                  <dd>{formatCount(tool.active_people)}</dd>
                </div>
                <div>
                  <dt>Errors</dt>
                  <dd>{formatCount(tool.errors)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      </section>

      <div className="cards">
        <Card id="people-heading" title="People" note={`Change is against ${against}.`}>
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
        </Card>

        <Card id="clients-heading" title="Clients" note="Outputs are headline events, across all tools.">
          <table className="data" role="table">
            <thead role="rowgroup">
              <tr role="row">
                <th role="columnheader" scope="col">
                  Client
                </th>
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
                  <th role="rowheader" scope="row">
                    {client.client_name}
                  </th>
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
        </Card>

        <Card
          id="persons-heading"
          title="Everyone"
          note="Each person invited, whether or not they have logged in."
          wide
        >
          <table className="data" role="table">
            <thead role="rowgroup">
              <tr role="row">
                <th role="columnheader" scope="col">
                  Person
                </th>
                <th role="columnheader" scope="col">
                  Client
                </th>
                <th role="columnheader" scope="col">
                  Role
                </th>
                <th role="columnheader" scope="col" className="num">
                  Logins
                </th>
                <th role="columnheader" scope="col" className="num">
                  Outputs
                </th>
                <th role="columnheader" scope="col">
                  Last seen
                </th>
              </tr>
            </thead>
            <tbody role="rowgroup">
              {overview.activity_by_person.map((person) => (
                <tr role="row" key={person.user_id}>
                  <th role="rowheader" scope="row">
                    {person.name}
                  </th>
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
        </Card>
      </div>
    </main>
  );
}
