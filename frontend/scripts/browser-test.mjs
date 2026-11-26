// `make browser-test`: one short journey in a real Chromium against the app in demo mode.
// No key and no model call: every answer shown is a recorded one.
//
// Started by scripts/browser-test.sh, which runs the backend and the frontend first.
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://localhost:3000";
const SUGGESTED = "How many invoices were issued in the last 7 days?";
const OUT_OF_SCOPE = "What will usage look like next month?";
// The start of the backend's fixed refusal (REFUSAL_TEXT in backend/app/assistant.py).
const REFUSAL = "I can't answer that from this dashboard.";

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(30_000);
  const keyNumbers = () => page.getByRole("group", { name: /^Key numbers/ }).innerText();

  await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
  await page.getByText("Demo mode: recorded answers, live model not connected.").waitFor();
  const week = await keyNumbers();
  check(/\d/.test(week), "the dashboard shows no numbers");
  console.log("pass  the dashboard loads in demo mode");

  await page.getByRole("navigation", { name: "Time window" }).getByRole("link").last().click();
  await page.waitForURL(/window=30d/);
  await page.waitForFunction(
    (before) => document.querySelector('[aria-label^="Key numbers"]')?.innerText !== before,
    week,
  );
  check((await keyNumbers()) !== week, "the numbers did not change with the window");
  console.log("pass  switching to 30 days changes the numbers");

  await page.getByRole("button", { name: SUGGESTED }).click();
  const answer = page.locator(".entry .answer").last();
  await answer.getByText("How this was worked out").waitFor();
  check(/\d/.test(await answer.locator(".answer-top").innerText()), "the answer holds no number");
  await answer.getByText(/^Looked up /).waitFor();
  await answer.getByText("Recorded answer. No model was called.").waitFor();
  await answer.getByText(/^Request [0-9a-f]{12}$/).waitFor();
  console.log("pass  a suggested question is answered, with its lookup shown");

  await page.getByLabel("Ask about usage, people, clients or errors").fill(OUT_OF_SCOPE);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const refusal = page.locator(".entry").last();
  await refusal.getByText(REFUSAL, { exact: false }).waitFor();
  await refusal.getByText("No lookup ran. The assistant refuses rather than guesses.").waitFor();
  console.log("pass  an out-of-scope question gets the fixed refusal");
} finally {
  await browser.close();
}
