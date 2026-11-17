import { describe, expect, it } from "vitest";

import { beforeLabel, bucketLabel, formatCount, formatDay, initials, inWindow, switchLabel, versusLabel } from "./format";

describe("display wording", () => {
  it("labels the window switch briefly", () => {
    expect([switchLabel("today"), switchLabel("7d"), switchLabel("30d")]).toEqual(["Today", "7 days", "30 days"]);
  });

  it("names the window a comparison is made against", () => {
    expect(beforeLabel("today")).toBe("the day before");
    expect(beforeLabel("30d")).toBe("the 30 days before");
  });

  it("writes a day without moving it across a timezone", () => {
    expect(formatDay("2026-10-30")).toBe("30 Oct 2026");
    expect(formatDay("2026-01-01")).toBe("1 Jan 2026");
  });

  it("groups thousands", () => {
    expect(formatCount(9039)).toBe("9,039");
    expect(formatCount(46)).toBe("46");
  });

  it("labels a chart bucket by its unit", () => {
    expect(bucketLabel("2026-10-24", "day")).toBe("Sat 24");
    expect(bucketLabel("09:00", "hour")).toBe("09");
  });

  it("takes initials from the first and last name", () => {
    expect(initials("Juno Dunmore")).toBe("JD");
    expect(initials("Alder & Finch")).toBe("AF");
  });
});

describe("the window inside a sentence", () => {
  it("does not say 'in today'", () => {
    expect(inWindow("today")).toBe("today");
    expect(inWindow("7d")).toBe("in the last 7 days");
  });

  it("names what a change is measured against", () => {
    expect(versusLabel("today")).toBe("vs the day before");
    expect(versusLabel("30d")).toBe("vs prior 30 days");
  });
});
