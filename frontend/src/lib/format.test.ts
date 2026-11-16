import { describe, expect, it } from "vitest";

import { formatChange, previousLabel, windowLabel } from "./format";

describe("windowLabel", () => {
  it("names each window in plain words", () => {
    expect(windowLabel("today")).toBe("today");
    expect(windowLabel("7d")).toBe("the last 7 days");
    expect(windowLabel("30d")).toBe("the last 30 days");
  });
});

describe("previousLabel", () => {
  it("says what a change is measured against", () => {
    expect(previousLabel("today")).toBe("vs the day before");
    expect(previousLabel("7d")).toBe("vs the 7 days before");
    expect(previousLabel("30d")).toBe("vs the 30 days before");
  });
});

describe("formatChange", () => {
  it("shows the sign the backend computed, and never computes one", () => {
    expect(formatChange(5)).toBe("+5");
    expect(formatChange(-41)).toBe("−41");
    expect(formatChange(0)).toBe("no change");
  });

  it("says so when there is nothing to compare with", () => {
    expect(formatChange(null)).toBe("no earlier data");
  });
});
