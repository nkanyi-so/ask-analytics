// "What the lookup returned", for the working under an answer.
//
// The backend does not send lookup results with an answer, so the page reads the same
// lookup again through the frontend's own server (`rowsOf`, on the server) and shows the
// rows the answer rests on (`shownFor`, in the browser). This file selects and words;
// it never counts or adds.
import type { OverviewResponse, ReliabilityResponse } from "./types";

export const LOOKUPS = [
  "usage_by_tool",
  "activity_by_person",
  "activity_by_client",
  "errors_seen",
  "roster",
] as const;

export type Lookup = (typeof LOOKUPS)[number];

export function isLookup(value: string | null): value is Lookup {
  return LOOKUPS.some((lookup) => lookup === value);
}

/** The words a reader would use for each lookup. */
export const LOOKUP_NAMES: Record<Lookup, string> = {
  usage_by_tool: "usage by tool",
  activity_by_person: "activity by person",
  activity_by_client: "activity by client",
  errors_seen: "errors by source",
  roster: "the roster",
};

/** Which of the dashboard's two endpoints holds a lookup. */
export function endpointFor(lookup: Lookup): "overview" | "reliability" {
  return lookup === "errors_seen" ? "reliability" : "overview";
}

/** How the model called the lookup: what it asked to be compared, and any filter. */
export interface Asked {
  compared: boolean;
  userId: string | null;
  toolId: string | null;
}

/** One measure of one row: its value, and the comparison if the lookup was asked for it. */
export interface Fact {
  label: string;
  value: number;
  previous?: number | null;
  change?: number | null;
}

export interface EvidenceRow {
  title: string;
  facts: Fact[];
  /** Names the lookup listed under this row (the roster's lists). */
  names?: string[];
}

type Measured = Record<string, unknown>;

function fact(row: object, field: string, label: string, compared: boolean): Fact {
  const measured = row as Measured;
  const value = measured[field] as number;
  if (!compared) return { label, value };
  return {
    label,
    value,
    previous: measured[`${field}_previous`] as number | null,
    change: measured[`${field}_change`] as number | null,
  };
}

/**
 * A lookup's result as titled rows of figures: what the model was given, and no more.
 * No ids, and previous values only when the model asked for the comparison.
 */
export function rowsOf(
  lookup: Lookup,
  body: OverviewResponse | ReliabilityResponse,
  asked: Asked,
): EvidenceRow[] {
  const { compared } = asked;
  if (lookup === "errors_seen") {
    return (body as ReliabilityResponse).errors
      .filter((row) => asked.toolId === null || row.tool_id === asked.toolId)
      // Without the comparison, the lookup only lists groups that had errors.
      .filter((row) => compared || row.count > 0)
      .map((row) => ({
        title: `${row.source.replaceAll("_", " ")} on ${row.tool_name}`,
        facts: [fact(row, "count", "errors", compared), fact(row, "people_affected", "people affected", compared)],
      }));
  }
  const overview = body as OverviewResponse;
  switch (lookup) {
    case "usage_by_tool":
      return overview.usage_by_tool.map((row) => ({
        title: row.tool_name,
        facts: [
          fact(row, "headline_count", row.headline_event.replaceAll("_", " "), compared),
          fact(row, "active_people", "active people", compared),
          fact(row, "errors", "errors", compared),
        ],
      }));
    case "activity_by_person":
      return overview.activity_by_person
        .filter((row) => asked.userId === null || row.user_id === asked.userId)
        .map((row) => ({
          title: row.name,
          facts: [fact(row, "logins", "logins", compared), fact(row, "outputs", "outputs", compared)],
        }));
    case "activity_by_client":
      return overview.activity_by_client.map((row) => ({
        title: row.client_name,
        facts: [fact(row, "outputs", "outputs", compared), fact(row, "active_people", "active people", compared)],
      }));
    case "roster": {
      const { roster } = overview;
      return [
        { title: "Active", facts: [fact(roster, "active_count", "people active", compared)] },
        {
          title: "Went quiet",
          facts: [fact(roster, "went_quiet_count", "people went quiet", compared)],
          names: roster.went_quiet.map((person) => person.name),
        },
        {
          title: "Never showed up",
          facts: [{ label: "people never showed up", value: roster.never_showed_up_count }],
          names: roster.never_showed_up.map((person) => person.name),
        },
        { title: "Invited", facts: [{ label: "people invited", value: roster.invited_count }] },
      ];
    }
  }
}

// --- what to show ----------------------------------------------------------------------

export interface Shown {
  rows: EvidenceRow[];
  /** True when more rows matched than are shown. */
  more: boolean;
  /**
   * True when each figure shown is one the answer states about the same thing: the
   * number matches and the answer uses the measure's own words. Only then may the page
   * mark the number in the answer as found.
   */
  confirmed: boolean;
}

const MAX_ROWS = 5;

function states(each: Fact, numbers: Set<number>): boolean {
  // A change is matched without its sign: "down by 41" and "-41" are the same statement.
  // The sign-less value is used for matching only and is never displayed.
  const change = typeof each.change === "number" ? Math.abs(each.change) : null;
  return [each.value, each.previous, change].some(
    (candidate) => typeof candidate === "number" && numbers.has(candidate),
  );
}

/** Does the answer use this measure's words? "invoice issued" matches "invoices were issued". */
function worded(label: string, answer: string): boolean {
  const text = answer.toLowerCase();
  return label
    .toLowerCase()
    .split(" ")
    .filter((word) => word.length >= 4)
    .some((word) => text.includes(word.slice(0, 5)));
}

function named(row: EvidenceRow, answer: string): boolean {
  const text = answer.toLowerCase();
  return (
    text.includes(row.title.toLowerCase()) ||
    (row.names ?? []).some((name) => text.includes(name.toLowerCase()))
  );
}

/**
 * The part of a lookup result that the answer rests on, in order of how sure it is.
 *
 * 1. Figures the answer states in the measure's own words ("10 invoices were issued"
 *    against "invoice issued 10"). These are confirmed, and may be marked.
 * 2. Otherwise, rows the answer names ("Nobody has used Contact enrichment"), with all
 *    their figures, unmarked.
 * 3. Otherwise, rows that share a number with the answer, unmarked.
 *
 * A shared number alone is never confirmation: "22 errors" must not be matched to a
 * row where 22 is the count of active people.
 */
export function shownFor(all: EvidenceRow[], answer: string, numbers: Set<number>): Shown {
  const sure = all
    .map((row) => ({
      ...row,
      facts: row.facts.filter((each) => states(each, numbers) && worded(each.label, answer)),
    }))
    .filter((row) => row.facts.length > 0);
  const sureAndNamed = sure.filter((row) => named(row, answer));
  const byName = all.filter((row) => named(row, answer));
  const byNumber = all.filter((row) => row.facts.some((each) => states(each, numbers)));

  const confirmed = sure.length > 0;
  const chosen = sureAndNamed.length > 0 ? sureAndNamed : confirmed ? sure : byName.length > 0 ? byName : byNumber;
  const rows = chosen.slice(0, MAX_ROWS).map((row) => ({
    ...row,
    names: row.names?.filter((name) => answer.toLowerCase().includes(name.toLowerCase())),
  }));
  return { rows, more: chosen.length > MAX_ROWS, confirmed };
}

/** The figures the page may mark in the answer: those in confirmed rows, sign aside. */
export function figuresIn(shown: Shown[]): Set<number> {
  const figures = new Set<number>();
  for (const { rows, confirmed } of shown) {
    if (!confirmed) continue;
    for (const row of rows) {
      for (const each of row.facts) {
        for (const value of [each.value, each.previous, each.change]) {
          if (typeof value === "number") figures.add(Math.abs(value));
        }
      }
    }
  }
  return figures;
}
