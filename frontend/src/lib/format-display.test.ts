import { describe, expect, it } from "vitest";

import { beforeLabel, formatCount, formatDay, switchLabel } from "./format";

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
});
