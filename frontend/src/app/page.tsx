import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { AskAbout } from "@/components/AskAbout";
import { Card } from "@/components/Card";
import { Change } from "@/components/Change";
import { ShowAll } from "@/components/ShowAll";
import { getOverview } from "@/lib/backend";
import { beforeLabel, formatCount, formatDay, windowLabel } from "@/lib/format";
import type { RosterPerson } from "@/lib/types";
import { parseWindow, type Window } from "@/lib/windows";

export const metadata: Metadata = { title: "Overview" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function Stat({
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
    <div className="stat">
      <dt>{label}</dt>
      <dd className="stat-value">{formatCount(value)}</dd>
      {change === undefined ? null : (
        <dd className="stat-change">
          <Change value={change} against={against} />
        </dd>
      )}
    </div>
  );
}

function People({ title, people, never }: { title: string; people: RosterPerson[]; never: string }): ReactNode {
  return (
    <div className="roll">
      <h3>{title}</h3>
      {people.length === 0 ? (
        <p className="empty">Nobody.</p>
      ) : (
        <ul>
          {people.map((person) => (
            <li key={person.user_id}>
              <span className="roll-name">{person.name}</span>
              <span className="roll-where">{person.client_name}</span>
              <span className="roll-when">{person.last_seen === null ? never : `last seen ${formatDay(person.last_seen)}`}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The question a tile asks for you. Written as a person would ask it. */
function questionAbout(tool: string, window: Window): string {
  return window === "today" ? `How is the ${tool} doing today?` : `How is the ${tool} doing in ${windowLabel(window)}?`;
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
      <p className="demo-note">
        A demo on made-up data: a usage dashboard, and an AI assistant that cannot invent a number.{" "}
        <Link href="/about">How it works</Link>
      </p>

      <div className="view-head">
        <h1>Overview</h1>
        <p>
          Who is using what, in {windowLabel(window)}. Data runs to{" "}
          <time dateTime={overview.as_of}>{formatDay(overview.as_of)}</time>.
        </p>
      </div>

      <dl className="stats" aria-label="People">
        <Stat label="Active" value={roster.active_count} change={roster.active_count_change} against={against} />
        <Stat
          label="Went quiet"
          value={roster.went_quiet_count}
          change={roster.went_quiet_count_change}
          against={against}
        />
        <Stat label="Never showed up" value={roster.never_showed_up_count} against={against} />
        <Stat label="Invited" value={roster.invited_count} against={against} />
      </dl>

      <section className="block" aria-labelledby="tools-heading">
        <header className="block-head">
          <h2 id="tools-heading">Tools</h2>
          <p>One number per tool: how many times it did its job. The change is against {against}.</p>
        </header>
        <ul className="tiles">
          {overview.usage_by_tool.map((tool) => (
            <li className="tile" key={tool.tool_id}>
              {/* The name comes first for a screen reader; the number is shown above it. */}
              <h3 className="tile-name">{tool.tool_name}</h3>
              <p className="tile-figure">
                <span className="tile-value">{formatCount(tool.headline_count)}</span>
                <span className="tile-change">
                  <Change value={tool.headline_count_change} against={against} />
                </span>
              </p>
              <p className="tile-what">
                <span>{tool.headline_event.replaceAll("_", " ")}</span>
                {/* Shown instead of the caption while the tile is pointed at (live mode only). */}
                <span className="tile-ask-hint" aria-hidden="true">
                  Ask about this
                </span>
              </p>
              <dl className="tile-more">
                <div>
                  <dt>
                    Active<span className="visually-hidden"> people</span>
                  </dt>
                  <dd>{formatCount(tool.active_people)}</dd>
                </div>
                <div>
                  <dt>Errors</dt>
                  <dd>{formatCount(tool.errors)}</dd>
                </div>
              </dl>
              <AskAbout label={`Ask about this tool: ${tool.tool_name}`} question={questionAbout(tool.tool_name, window)} />
            </li>
          ))}
        </ul>
      </section>

      <div className="cards">
        <Card id="clients-heading" title="Clients" note="Outputs across all tools.">
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

        <Card id="missing-heading" title="Not showing up" note="The people a usage chart cannot show, because they left no trace.">
          <People title="Went quiet" people={roster.went_quiet} never="never logged in" />
          <People title="Invited, never logged in" people={roster.never_showed_up} never="never logged in" />
        </Card>

        <Card id="persons-heading" title="Everyone" note="Each person invited, whether or not they have logged in." wide>
          <ShowAll
            more={`Show all ${formatCount(roster.invited_count)} people`}
            fewer="Show fewer"
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
          </ShowAll>
        </Card>
      </div>
    </main>
  );
}
