import { describe, expect, it } from "vitest";

import { heroOf, numbersOf, segmentsOf } from "./answer";

describe("reading an answer for display", () => {
  it("makes the first stated number the hero and keeps the text whole", () => {
    const answer = "In the last 7 days, 10 invoices were issued.";
    const segments = segmentsOf(answer);

    expect(heroOf(segments)).toBe("10");
    expect(segments.map((segment) => segment.text).join("")).toBe(answer);
  });

  it("does not treat dates, windows or ids as numbers", () => {
    const segments = segmentsOf(
      "Over the last 30 days (2026-10-01 to 2026-10-30) compared with the previous 30, " +
        "u014 was last seen on 25 September 2026 and October 22, and logged in 6 times.",
    );

    expect([...numbersOf(segments)]).toEqual([6]);
    expect(heroOf(segments)).toBe("6");
  });

  it("finds every number in a comparison, in the order written", () => {
    const segments = segmentsOf("91 emails in the last 7 days, up from 86, a rise of 5.");

    expect([...numbersOf(segments)]).toEqual([91, 86, 5]);
  });

  it("reads 1,234 as one number", () => {
    expect([...numbersOf(segmentsOf("There were 1,234 events."))]).toEqual([1234]);
  });

  it("has no hero when the answer states no number", () => {
    const segments = segmentsOf("Nobody has used Contact enrichment in the last 7 days.");

    expect(heroOf(segments)).toBeNull();
    expect(numbersOf(segments).size).toBe(0);
  });

  it("keeps a written sign on the hero, and reads the size for matching", () => {
    const segments = segmentsOf("Invoices issued: a change of -41 (from 51 to 10).");

    expect(heroOf(segments)).toBe("-41");
    expect([...numbersOf(segments)]).toEqual([41, 51, 10]);
    expect(heroOf(segmentsOf("Logins: +3 on last week."))).toBe("+3");
    expect([...numbersOf(segmentsOf("Between 10-41 either way."))]).toEqual([10, 41]);
  });

  it("still counts a number that follows a window phrase with a noun", () => {
    expect([...numbersOf(segmentsOf("The last 30 invoices failed."))]).toEqual([30]);
  });
});
