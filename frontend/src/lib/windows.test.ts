import { describe, expect, it } from "vitest";

import { DEFAULT_WINDOW, parseWindow } from "./windows";

describe("parseWindow", () => {
  it("keeps a known window", () => {
    expect(parseWindow("30d")).toBe("30d");
  });

  it("falls back to the default for anything else", () => {
    expect(parseWindow("90d")).toBe(DEFAULT_WINDOW);
    expect(parseWindow(undefined)).toBe(DEFAULT_WINDOW);
  });

  it("uses the first value when the query repeats", () => {
    expect(parseWindow(["today", "30d"])).toBe("today");
  });
});
