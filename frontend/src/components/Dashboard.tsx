"use client";

import { useState, type ReactNode } from "react";

import { beforeLabel, formatCount, formatDay, inWindow, versusLabel } from "@/lib/format";
import type { OverviewResponse, RosterPerson } from "@/lib/types";
import type { Window } from "@/lib/windows";

import { useAsk } from "./ask-context";
import { BarChart, Sparkline } from "./BarChart";
import { ChangePill } from "./ChangePill";
import { PeopleTable } from "./PeopleTable";

type Kpi = "active" | "outputs" | "errors" | "missing";

const UNIT_WORD = { hour: "hour", day: "day" } as const;

/** The question a row asks for you. Written as a person would ask it. */
function questionAbout(tool: string, window: Window): string {
  return `How is the ${tool} doing ${inWindow(window)}?`;
}

/** A tool's name: a way into the assistant when a live model is connected, plain text when not. */
function ToolName({ name, window }: { name: string; window: Window }): ReactNode {
  const { ask, live } = useAsk();
  if (!live) return <span className="cell-name">{name}</span>;
  return (
    <button className="cell-name ask-link" type="button" onClick={() => ask(questionAbout(name, window))} title="Ask the assistant about this tool">
      {name}
    </button>
  );
}

function Roll({ title, people, none }: { title: string; people: RosterPerson[]; none: string }): ReactNode {
  return (
    <div className="roll">
      <h3 className="sub">{title}</h3>
      {people.length === 0 ? (
        <p className="empty">{none}</p>
      ) : (
        <ul>
          {people.map((person) => (
            <li key={person.user_id}>
              <span>
                <span className="cell-name">{person.name}</span>
                <small>{person.client_name}</small>
              </span>
              <span className="pill">
                {person.last_seen === null ? "never logged in" : `last seen ${formatDay(person.last_seen)}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * The Overview: four numbers you can press, and under them the chart and the tables
 * behind whichever one is selected. Every figure is a field of the API's reply. This
 * component chooses which to show and in what order; it does not count or add.
 */
export function Dashboard({ overview }: { overview: OverviewResponse }): ReactNode {
  const [selected, setSelected] = useState<Kpi>("outputs");
  const { roster, trend, window } = overview;
  const against = beforeLabel(window);
  const per = UNIT_WORD[trend.unit];
  const when = inWindow(window);

  const tools = [...overview.usage_by_tool].sort((a, b) => b.headline_count - a.headline_count);
  const clients = [...overview.activity_by_client].sort((a, b) => b.outputs - a.outputs);
  const failing = [...overview.usage_by_tool].sort((a, b) => b.errors - a.errors);

  const cards: { id: Kpi; label: string; value: number; foot: ReactNode }[] = [
    {
      id: "active",
      label: "Active people",
      value: roster.active_count,
      foot: (
        <>
          <ChangePill value={roster.active_count_change} better="up" against={against} />
          {versusLabel(window)}
        </>
      ),
    },
    {
      id: "outputs",
      label: "Outputs",
      value: trend.outputs,
      foot: (
        <>
          <ChangePill value={trend.outputs_change} better="up" against={against} />
          {versusLabel(window)}
        </>
      ),
    },
    {
      id: "errors",
      label: "Errors",
      value: trend.errors,
      foot: (
        <>
          <ChangePill value={trend.errors_change} better="down" against={against} />
          {versusLabel(window)}
        </>
      ),
    },
    {
      id: "missing",
      label: "Never showed up",
      value: roster.never_showed_up_count,
      foot: <>of {formatCount(roster.invited_count)} invited</>,
    },
  ];

  return (
    <>
      {/* Toggle buttons, not tabs: each is pressed or not, and Tab moves between them. */}
      <div className="kpis" role="group" aria-label="Key numbers. Press one to see what is behind it.">
        {cards.map((card) => (
          <button
            key={card.id}
            className="kpi"
            type="button"
            id={`kpi-${card.id}`}
            aria-pressed={selected === card.id}
            aria-controls="kpi-detail"
            onClick={() => setSelected(card.id)}
          >
            <span className="kpi-label">{card.label}</span>
            <span className="kpi-value">{formatCount(card.value)}</span>
            <span className="kpi-foot">{card.foot}</span>
          </button>
        ))}
      </div>

      <section className="card detail" id="kpi-detail" aria-labelledby="kpi-detail-heading">
        {selected === "active" ? (
          <>
            <header className="card-head">
              <div>
                <h2 id="kpi-detail-heading">Active people</h2>
                <p>
                  People who logged in, per {per}, {when}.
                </p>
              </div>
              <span className="pill">{formatCount(roster.active_count)} in the whole window</span>
            </header>
            <BarChart
              points={trend.buckets.map((bucket) => ({ label: bucket.label, value: bucket.active_people }))}
              unit={trend.unit}
              summary={`Active people per ${per}`}
            />
            <h3 className="sub rule">Behind the number: everyone invited, by logins</h3>
            <PeopleTable people={overview.activity_by_person} wentQuiet={roster.went_quiet} sortBy="logins" />
          </>
        ) : null}

        {selected === "outputs" ? (
          <>
            <header className="card-head">
              <div>
                <h2 id="kpi-detail-heading">Outputs</h2>
                <p>
                  Per {per}, {when}. An output is a tool doing its job once.
                </p>
              </div>
              <span className="pill">{formatCount(trend.outputs)} in total</span>
            </header>
            <BarChart
              points={trend.buckets.map((bucket) => ({ label: bucket.label, value: bucket.outputs }))}
              unit={trend.unit}
              summary={`Outputs per ${per}`}
            />
            <h3 className="sub rule">Behind the number</h3>
            <div className="pair">
              <table className="data" role="table">
                <thead role="rowgroup">
                  <tr role="row">
                    <th role="columnheader" scope="col">
                      Tool
                    </th>
                    <th role="columnheader" scope="col">
                      Per {per}
                    </th>
                    <th role="columnheader" scope="col" className="num">
                      Outputs
                    </th>
                    <th role="columnheader" scope="col" className="num">
                      Change
                    </th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {tools.map((tool) => (
                    <tr role="row" key={tool.tool_id}>
                      <th role="rowheader" scope="row">
                        <ToolName name={tool.tool_name} window={window} />
                        <small>{tool.headline_event.replaceAll("_", " ")}</small>
                      </th>
                      <td role="cell" data-label={`Per ${per}`}>
                        <Sparkline
                          values={trend.buckets.map((bucket) => bucket.outputs_by_tool[tool.tool_id] ?? 0)}
                          label={`${tool.tool_name}, per ${per}`}
                        />
                      </td>
                      <td role="cell" className="num strong" data-label="Outputs">
                        {formatCount(tool.headline_count)}
                      </td>
                      <td role="cell" className="num" data-label="Change">
                        <ChangePill value={tool.headline_count_change} better="up" against={against} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
                      Active
                    </th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {clients.map((client) => (
                    <tr role="row" key={client.client_id}>
                      <th role="rowheader" scope="row">
                        <span className="cell-name">{client.client_name}</span>
                      </th>
                      <td role="cell" className="num strong" data-label="Outputs">
                        {formatCount(client.outputs)}
                      </td>
                      <td role="cell" className="num" data-label="Change">
                        <ChangePill value={client.outputs_change} better="up" against={against} />
                      </td>
                      <td role="cell" className="num" data-label="Active">
                        {formatCount(client.active_people)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}

        {selected === "errors" ? (
          <>
            <header className="card-head">
              <div>
                <h2 id="kpi-detail-heading">Errors</h2>
                <p>
                  Per {per}, {when}, across every tool. The Reliability tab shows where they came from.
                </p>
              </div>
              <span className="pill">{formatCount(trend.errors)} in total</span>
            </header>
            <BarChart
              points={trend.buckets.map((bucket) => ({ label: bucket.label, value: bucket.errors }))}
              unit={trend.unit}
              tone="bad"
              summary={`Errors per ${per}`}
            />
            <h3 className="sub rule">Behind the number</h3>
            <table className="data" role="table">
              <thead role="rowgroup">
                <tr role="row">
                  <th role="columnheader" scope="col">
                    Tool
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Errors
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Change
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Outputs
                  </th>
                  <th role="columnheader" scope="col" className="num">
                    Active
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {failing.map((tool) => (
                  <tr role="row" key={tool.tool_id}>
                    <th role="rowheader" scope="row">
                      <ToolName name={tool.tool_name} window={window} />
                    </th>
                    <td role="cell" className="num strong" data-label="Errors">
                      {formatCount(tool.errors)}
                    </td>
                    <td role="cell" className="num" data-label="Change">
                      <ChangePill value={tool.errors_change} better="down" against={against} />
                    </td>
                    <td role="cell" className="num" data-label="Outputs">
                      {formatCount(tool.headline_count)}
                    </td>
                    <td role="cell" className="num" data-label="Active">
                      {formatCount(tool.active_people)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}

        {selected === "missing" ? (
          <>
            <header className="card-head">
              <div>
                <h2 id="kpi-detail-heading">Not showing up</h2>
                <p>The people a usage chart cannot show, because they left no trace {when}.</p>
              </div>
              <span className="pill">{formatCount(roster.invited_count)} invited</span>
            </header>
            <div className="pair rolls">
              <Roll title="Invited, never logged in" people={roster.never_showed_up} none="Everyone invited has logged in." />
              <Roll title="Went quiet" people={roster.went_quiet} none="Nobody has gone quiet." />
            </div>
          </>
        ) : null}
      </section>

      {/* With "Active people" chosen, the same table is already open above. */}
      {selected === "active" ? null : (
      <section className="card" aria-labelledby="everyone-heading">
        <header className="card-head">
          <div>
            <h2 id="everyone-heading">
              Everyone <span className="pill">{formatCount(roster.invited_count)} people</span>
            </h2>
            <p>Each person invited, whether or not they have logged in.</p>
          </div>
        </header>
        <PeopleTable people={overview.activity_by_person} wentQuiet={roster.went_quiet} sortBy="outputs" />
      </section>
      )}
    </>
  );
}
