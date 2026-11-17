// Reading an answer for display. Nothing here computes a number: it finds the numbers
// the answer already contains, so the page can make one the hero and mark the rest.

/** A stretch of the answer: plain words, or one number as it was written. */
export interface Segment {
  text: string;
  /** Set when this stretch is a number that states something (not a date or a window). */
  value?: number;
}

const MONTH =
  "(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|" +
  "Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)";

// Digits that say when, not how many. They are shown as plain text and never marked.
const NOT_A_COUNT = new RegExp(
  [
    "\\d{4}-\\d{2}-\\d{2}", // 2026-10-30
    // A span of days written once: "24 to 30 October 2026", "October 24-30". Before the
    // single-date forms, so the first day is not left behind as a number.
    `\\d{1,2}(?:st|nd|rd|th)?\\s*(?:to|until|through|[-\u2013\u2014])\\s*\\d{1,2}(?:st|nd|rd|th)?\\s+(?:of\\s+)?${MONTH}\\b(?:,?\\s+\\d{4})?`,
    `${MONTH}\\s+\\d{1,2}(?:st|nd|rd|th)?\\s*(?:to|until|through|[-\u2013\u2014])\\s*\\d{1,2}(?:st|nd|rd|th)?(?:,?\\s+\\d{4})?`,
    `\\d{1,2}(?:st|nd|rd|th)?\\s+(?:of\\s+)?${MONTH}\\b(?:,?\\s+\\d{4})?`, // 30 October 2026
    `${MONTH}\\s+\\d{1,2}(?:st|nd|rd|th)?(?:,?\\s+\\d{4})?`, // October 30, 2026
    "\\b(?:7|30)(?:[\\s-]*days?|d)\\b", // the last 7 days, 30d
    "\\b(?:previous|prior|preceding|last|past)\\s+(?:7|30)\\b(?!\\s+[a-z])", // the previous 30
    "\\b[a-z]\\d{2,3}\\b", // an id such as u014
  ].join("|"),
  "gi",
);

// A sign written directly before the digits is part of the number as written: "-41".
// It must follow a space, a bracket or the start, so "10-41" is not read as minus 41.
const NUMBER = /(?<![\w.,-])[-\u2212+]?\d+(?:,\d{3})*|\d+(?:,\d{3})*/g;

function numbersIn(text: string): Segment[] {
  const segments: Segment[] = [];
  let from = 0;
  for (const match of text.matchAll(NUMBER)) {
    if (match.index > from) segments.push({ text: text.slice(from, match.index) });
    // The value is the size, for matching; the text keeps the sign, for showing.
    segments.push({ text: match[0], value: Number(match[0].replace(/[^\d]/g, "")) });
    from = match.index + match[0].length;
  }
  if (from < text.length) segments.push({ text: text.slice(from) });
  return segments;
}

/** The answer cut into words and numbers, with dates, windows and ids left as words. */
export function segmentsOf(answer: string): Segment[] {
  const segments: Segment[] = [];
  let from = 0;
  for (const match of answer.matchAll(NOT_A_COUNT)) {
    segments.push(...numbersIn(answer.slice(from, match.index)), { text: match[0] });
    from = match.index + match[0].length;
  }
  segments.push(...numbersIn(answer.slice(from)));
  return segments;
}

/** The first number the answer states, as written. `null` when it states none. */
export function heroOf(segments: Segment[]): string | null {
  return segments.find((segment) => segment.value !== undefined)?.text ?? null;
}

/** Every number the answer states. */
export function numbersOf(segments: Segment[]): Set<number> {
  const values = segments.flatMap((segment) => (segment.value === undefined ? [] : [segment.value]));
  return new Set(values);
}
