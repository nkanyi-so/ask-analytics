"use client";

import { useState, type ReactNode } from "react";

import { formatCount, formatDay, initials } from "@/lib/format";
import type { PersonActivity, RosterPerson } from "@/lib/types";

type Column = "name" | "logins" | "outputs" | "last_seen";

const ROWS_SHOWN = 8;

const COLUMNS: { id: Column; label: string; numeric: boolean }[] = [
  { id: "name", label: "Person", numeric: false },
  { id: "logins", label: "Logins", numeric: true },
  { id: "outputs", label: "Outputs", numeric: true },
  { id: "last_seen", label: "Last seen", numeric: false },
];

function compare(a: PersonActivity, b: PersonActivity, column: Column): number {
  switch (column) {
    case "name":
      return a.name.localeCompare(b.name);
    case "logins":
      return a.logins - b.logins;
    case "outputs":
      return a.outputs - b.outputs;
    case "last_seen":
      // ISO dates order as text. Someone never seen sorts before everyone who was.
      return (a.last_seen ?? "").localeCompare(b.last_seen ?? "");
  }
}

function SortIcon({ state }: { state: "none" | "ascending" | "descending" }): ReactNode {
  return (
    <svg viewBox="0 0 12 12" fill="none" aria-hidden="true" data-state={state}>
      <path d="M3.5 4.5L6 2l2.5 2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" className="up" />
      <path d="M3.5 7.5L6 10l2.5-2.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" className="down" />
    </svg>
  );
}

/**
 * Everyone invited, sortable, short until asked for in full. Sorting and trimming
 * only reorder and hide rows the API sent; nothing here is counted.
 */
export function PeopleTable({
  people,
  wentQuiet,
  sortBy,
}: {
  people: PersonActivity[];
  wentQuiet: RosterPerson[];
  sortBy: Column;
}): ReactNode {
  const [column, setColumn] = useState<Column>(sortBy);
  const [descending, setDescending] = useState(sortBy !== "name");
  const [all, setAll] = useState(false);
  const quiet = new Set(wentQuiet.map((person) => person.user_id));

  const sorted = [...people].sort((a, b) => (descending ? compare(b, a, column) : compare(a, b, column)));
  const shown = all ? sorted : sorted.slice(0, ROWS_SHOWN);

  function sort(next: Column, numeric: boolean): void {
    if (next === column) {
      setDescending(!descending);
    } else {
      setColumn(next);
      // A number starts at its largest; a name starts at A.
      setDescending(numeric);
    }
  }

  return (
    <>
      <table className="data" role="table">
        <thead role="rowgroup">
          <tr role="row">
            {COLUMNS.map((each) => {
              const state = each.id !== column ? "none" : descending ? "descending" : "ascending";
              return (
                <th
                  key={each.id}
                  role="columnheader"
                  scope="col"
                  className={each.numeric ? "num" : undefined}
                  aria-sort={state}
                >
                  <button className="sort" type="button" onClick={() => sort(each.id, each.numeric)}>
                    {each.label}
                    <SortIcon state={state} />
                  </button>
                </th>
              );
            })}
            <th role="columnheader" scope="col">
              Role
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {shown.map((person) => (
            <tr role="row" key={person.user_id}>
              <th role="rowheader" scope="row">
                <span className="person">
                  <span className="avatar" aria-hidden="true">
                    {initials(person.name)}
                  </span>
                  <span>
                    <span className="cell-name">{person.name}</span>
                    <small>{person.client_name}</small>
                  </span>
                </span>
              </th>
              <td role="cell" className="num strong" data-label="Logins">
                {formatCount(person.logins)}
              </td>
              <td role="cell" className="num strong" data-label="Outputs">
                {formatCount(person.outputs)}
              </td>
              <td role="cell" data-label="Last seen">
                {person.last_seen === null ? (
                  <span className="pill">never logged in</span>
                ) : quiet.has(person.user_id) ? (
                  <span className="pill bad">went quiet, {formatDay(person.last_seen)}</span>
                ) : (
                  formatDay(person.last_seen)
                )}
              </td>
              <td role="cell" data-label="Role">
                <span className="pill">{person.role}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {people.length > ROWS_SHOWN ? (
        <button className="text-button" type="button" aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? "Show fewer" : "Show everyone"}
        </button>
      ) : null}
    </>
  );
}
