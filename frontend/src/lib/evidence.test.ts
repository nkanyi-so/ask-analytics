import { describe, expect, it } from "vitest";

import { endpointFor, figuresIn, isLookup, rowsOf, shownFor, type Asked } from "./evidence";
import type { ActivityOverTime, OverviewResponse, ReliabilityResponse, Roster, ToolUsage } from "./types";

function tool(id: string, name: string, event: string, count: number, previous: number, errors = 1): ToolUsage {
  return {
    tool_id: id,
    tool_name: name,
    headline_event: event,
    headline_count: count,
    active_people: 22,
    errors,
    headline_count_previous: previous,
    headline_count_change: count - previous, // test data only: the backend sends this
    active_people_previous: 25,
    active_people_change: -3,
    errors_previous: 2,
    errors_change: 84,
  };
}

const ROSTER: Roster = {
  invited_count: 40,
  active_count: 35,
  never_showed_up_count: 3,
  went_quiet_count: 2,
  active: [],
  never_showed_up: [
    { user_id: "u011", name: "Yara Dunmore", client_name: "Alder & Finch", last_seen: null },
    { user_id: "u027", name: "Otto Thackeray", client_name: "Cobalt Lane", last_seen: null },
  ],
  went_quiet: [{ user_id: "u014", name: "Xena Jarrah", client_name: "Brightwater", last_seen: "2026-09-25" }],
  active_count_previous: 35,
  active_count_change: 0,
  went_quiet_count_previous: 2,
  went_quiet_count_change: 0,
};

// The chart series plays no part in the working; an empty one satisfies the type.
const TREND: ActivityOverTime = {
  unit: "day",
  buckets: [],
  outputs: 0,
  outputs_previous: 0,
  outputs_change: 0,
  errors: 0,
  errors_previous: 0,
  errors_change: 0,
};

const OVERVIEW: OverviewResponse = {
  as_of: "2026-10-30",
  window: "7d",
  usage_by_tool: [
    tool("invoice_generator", "Invoice generator", "invoice_issued", 10, 51, 86),
    tool("contact_enrichment", "Contact enrichment", "contact_enriched", 0, 0),
    tool("email_drafter", "Email drafter", "email_sent", 91, 86),
  ],
  activity_by_person: [],
  activity_by_client: [],
  roster: ROSTER,
  trend: TREND,
};

const RELIABILITY: ReliabilityResponse = {
  as_of: "2026-10-30",
  window: "7d",
  trend: TREND,
  errors: [
    {
      source: "pdf_renderer",
      tool_id: "invoice_generator",
      tool_name: "Invoice generator",
      count: 86,
      people_affected: 21,
      affected: [],
      count_previous: 0,
      count_change: 86,
      people_affected_previous: 0,
      people_affected_change: 21,
    },
    {
      source: "input_validation",
      tool_id: "invoice_generator",
      tool_name: "Invoice generator",
      count: 0,
      people_affected: 0,
      affected: [],
      count_previous: 2,
      count_change: -2,
      people_affected_previous: 2,
      people_affected_change: -2,
    },
  ],
};

const PLAIN: Asked = { compared: false, userId: null, toolId: null };
const COMPARED: Asked = { ...PLAIN, compared: true };

describe("shaping a lookup result (on the server)", () => {
  it("knows the five lookups and where each one lives", () => {
    expect(isLookup("usage_by_tool")).toBe(true);
    expect(isLookup("raw_events")).toBe(false);
    expect(isLookup(null)).toBe(false);
    expect(endpointFor("errors_seen")).toBe("reliability");
    expect(endpointFor("roster")).toBe("overview");
  });

  it("returns titles and figures, never ids, and previous values only when asked", () => {
    const plain = rowsOf("usage_by_tool", OVERVIEW, PLAIN);
    const compared = rowsOf("usage_by_tool", OVERVIEW, COMPARED);

    expect(plain[0]).toEqual({
      title: "Invoice generator",
      facts: [
        { label: "invoice issued", value: 10 },
        { label: "active people", value: 22 },
        { label: "errors", value: 86 },
      ],
    });
    expect(compared[0].facts[0]).toEqual({ label: "invoice issued", value: 10, previous: 51, change: -41 });
    expect(JSON.stringify([plain, compared])).not.toMatch(/_id|u0\d\d|invoice_generator/);
    expect(JSON.stringify(plain)).not.toContain("previous");
  });

  it("keeps only the tool the model filtered by, and only groups the lookup listed", () => {
    const filtered = { ...PLAIN, toolId: "invoice_generator" };

    expect(rowsOf("errors_seen", RELIABILITY, filtered).map((row) => row.title)).toEqual([
      "pdf renderer on Invoice generator",
    ]);
    expect(rowsOf("errors_seen", RELIABILITY, { ...filtered, compared: true })).toHaveLength(2);
    expect(rowsOf("errors_seen", RELIABILITY, { ...PLAIN, toolId: "email_drafter" })).toEqual([]);
  });

  it("gives the roster as four counts, with names only for the two short lists", () => {
    const rows = rowsOf("roster", OVERVIEW, PLAIN);

    expect(rows.map((row) => [row.title, row.facts[0].value])).toEqual([
      ["Active", 35],
      ["Went quiet", 2],
      ["Never showed up", 3],
      ["Invited", 40],
    ]);
    expect(rows[0].names).toBeUndefined();
    expect(rows[2].names).toEqual(["Yara Dunmore", "Otto Thackeray"]);
  });
});

const USAGE = rowsOf("usage_by_tool", OVERVIEW, PLAIN);
const USAGE_COMPARED = rowsOf("usage_by_tool", OVERVIEW, COMPARED);

describe("choosing what to show (in the browser)", () => {
  it("shows the row and the figure the answer states, and nothing else", () => {
    const shown = shownFor(USAGE, "10 invoices were issued.", new Set([10]));

    expect(shown.rows).toEqual([
      { title: "Invoice generator", facts: [{ label: "invoice issued", value: 10 }], names: undefined },
    ]);
    expect(shown).toMatchObject({ more: false, confirmed: true });
  });

  it("matches a fall by its size, whatever sign the answer used", () => {
    const shown = shownFor(USAGE_COMPARED, "Invoices issued are down by 41.", new Set([41]));

    expect(shown.rows[0].facts).toEqual([{ label: "invoice issued", value: 10, previous: 51, change: -41 }]);
    expect(shown.confirmed).toBe(true);
  });

  it("never confirms a number against a different measure that happens to share it", () => {
    // The invoice generator had 86 errors; 22 is its count of active people.
    const answer = "The Invoice generator had 22 errors in the last 7 days.";

    const shown = shownFor(USAGE, answer, new Set([22]));

    expect(shown.confirmed).toBe(false);
    expect(figuresIn([shown]).size).toBe(0);
    // It still shows the named row, in full, so the reader can see the real figure.
    expect(shown.rows.map((row) => row.title)).toEqual(["Invoice generator"]);
    expect(shown.rows[0].facts.map((each) => each.value)).toEqual([10, 22, 86]);
  });

  it("does not pull in rows that only share a common number", () => {
    const shown = shownFor(USAGE, "0 contacts were enriched in the last 7 days.", new Set([0]));

    expect(shown.rows.map((row) => row.title)).toEqual(["Contact enrichment"]);
    expect(shown.rows[0].facts).toEqual([{ label: "contact enriched", value: 0 }]);
  });

  it("falls back to the names in the answer when it states no number, unconfirmed", () => {
    const shown = shownFor(USAGE, "Nobody has used Contact enrichment.", new Set());

    expect(shown.rows.map((row) => row.title)).toEqual(["Contact enrichment"]);
    expect(shown.rows[0].facts.map((each) => each.value)).toEqual([0, 22, 1]);
    expect(shown.confirmed).toBe(false);
  });

  it("shows roster counts with the names the answer repeats", () => {
    const answer = "3 people never showed up: Yara Dunmore and Otto Thackeray among them.";

    const shown = shownFor(rowsOf("roster", OVERVIEW, PLAIN), answer, new Set([3]));

    expect(shown.rows).toEqual([
      {
        title: "Never showed up",
        facts: [{ label: "people never showed up", value: 3 }],
        names: ["Yara Dunmore", "Otto Thackeray"],
      },
    ]);
    expect(shown.confirmed).toBe(true);
  });

  it("collects only confirmed figures, so the page marks nothing it is unsure of", () => {
    const sure = shownFor(USAGE_COMPARED, "Invoices issued fell by 41 to 10.", new Set([41, 10]));
    const unsure = shownFor(USAGE, "Nobody has used Contact enrichment.", new Set());

    expect([...figuresIn([sure, unsure])].sort((a, b) => a - b)).toEqual([10, 41, 51]);
  });

  it("says when more rows matched than it shows", () => {
    const many: OverviewResponse = {
      ...OVERVIEW,
      usage_by_tool: Array.from({ length: 7 }, (_, index) => tool(`t${index}`, `Tool ${index}`, "thing_done", 4, 4)),
    };

    const shown = shownFor(rowsOf("usage_by_tool", many, PLAIN), "Each thing was done 4 times.", new Set([4]));

    expect(shown.rows).toHaveLength(5);
    expect(shown.more).toBe(true);
  });
});
