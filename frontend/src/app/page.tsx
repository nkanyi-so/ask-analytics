import type { ReactNode } from "react";

import { AskBox } from "@/components/AskBox";
import { PageHeader } from "@/components/PageHeader";
import { Tile } from "@/components/Tile";
import { getHealth, getOverview } from "@/lib/backend";
import { previousLabel, windowLabel } from "@/lib/format";
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

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const [overview, health] = await Promise.all([getOverview(window), getHealth()]);
  const { roster } = overview;
  const against = previousLabel(window);

  return (
    <main>
      <PageHeader title="Overview" path="/" window={window} asOf={overview.as_of} />
      <AskBox demoMode={health.demo_mode} />

      <section aria-labelledby="people-heading">
        <h2 id="people-heading">People in the app, {windowLabel(window)}</h2>
        <div className="tiles">
          <Tile
            label="Active"
            value={roster.active_count}
            change={roster.active_count_change}
            against={against}
          />
          <Tile
            label="Went quiet"
            value={roster.went_quiet_count}
            change={roster.went_quiet_count_change}
            against={against}
          />
          <Tile label="Never showed up" value={roster.never_showed_up_count} />
          <Tile label="Invited" value={roster.invited_count} />
        </div>
        <Names label="Went quiet" people={roster.went_quiet} />
        <Names label="Never showed up" people={roster.never_showed_up} />
      </section>

      <section aria-labelledby="tools-heading">
        <h2 id="tools-heading">Headline number per tool, {windowLabel(window)}</h2>
        <div className="tiles">
          {overview.usage_by_tool.map((tool) => (
            <Tile
              key={tool.tool_id}
              label={tool.tool_name}
              value={tool.headline_count}
              note={`${tool.headline_event} · people: ${tool.active_people} · errors: ${tool.errors}`}
              change={tool.headline_count_change}
              against={against}
            />
          ))}
        </div>
      </section>

      <section aria-labelledby="clients-heading">
        <h2 id="clients-heading">Activity by client, {windowLabel(window)}</h2>
        <div className="tiles">
          {overview.activity_by_client.map((client) => (
            <Tile
              key={client.client_id}
              label={client.client_name}
              value={client.outputs}
              note={`outputs · active people: ${client.active_people}`}
              change={client.outputs_change}
              against={against}
            />
          ))}
        </div>
      </section>

      <section aria-labelledby="persons-heading">
        <h2 id="persons-heading">Activity by person, {windowLabel(window)}</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Person</th>
                <th scope="col">Client</th>
                <th scope="col">Role</th>
                <th scope="col" className="number">
                  Logins
                </th>
                <th scope="col" className="number">
                  Outputs
                </th>
                <th scope="col">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {overview.activity_by_person.map((person) => (
                <tr key={person.user_id}>
                  <th scope="row">{person.name}</th>
                  <td>{person.client_name}</td>
                  <td>{person.role}</td>
                  <td className="number">{person.logins}</td>
                  <td className="number">{person.outputs}</td>
                  <td>{person.last_seen ?? "never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
