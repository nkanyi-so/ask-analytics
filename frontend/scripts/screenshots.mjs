// Screenshots of every screen state in docs/DESIGN.md, at three widths, light and dark.
//
//   BASE=http://localhost:3000 OUT=/some/dir node scripts/screenshots.mjs
//   ONLY=04,08 WIDTHS=1280 MODES=light ...   to take a few
//
// Run it against the app in demo mode (no ANTHROPIC_API_KEY): then every answer shown
// is a recorded one and nothing is spent. The three failure states cannot be produced
// on demand, so the reply to /api/ask is replaced with the backend's own status and
// message, copied word for word from backend/app/main.py.
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://localhost:3000";
const OUT = process.env.OUT ?? "screenshots";
const ONLY = process.env.ONLY?.split(",");
const WIDTHS = (process.env.WIDTHS ?? "375,768,1280").split(",").map(Number);
const MODES = (process.env.MODES ?? "light,dark").split(",");

const SUGGESTED = {
  oneNumber: "How many invoices were issued in the last 7 days?",
  noNumber: "Which tool is nobody touching?",
  comparison: "Did email usage go up or down this week, and by how much?",
};

async function home(page) {
  await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
}

async function askByTyping(page, question) {
  await home(page);
  await page.getByLabel("Ask about usage, people, clients or errors").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

async function askSuggested(page, question) {
  await home(page);
  await page.getByRole("button", { name: question }).click();
}

function replyWith(status, detail) {
  return async (page) => {
    await page.route("**/api/ask", (route) => route.fulfill({ status, json: { detail } }));
    await askByTyping(page, SUGGESTED.oneNumber);
    await page.locator(".notice").waitFor();
  };
}

/** name -> { run, whole }. `whole` captures the full page; otherwise down to the end of the answer. */
const STATES = {
  "01-first-visit": { run: home },
  "02-demo-no-recorded-answer": {
    run: async (page) => {
      await askByTyping(page, "What is the weather like?");
      await page.locator(".notice").waitFor();
    },
  },
  "03-loading": {
    run: async (page) => {
      // Hold the reply so the waiting state can be photographed.
      await page.route("**/api/ask", () => new Promise(() => {}));
      await askSuggested(page, SUGGESTED.oneNumber);
      await page.getByRole("button", { name: "Asking" }).waitFor();
    },
  },
  "04-answer-one-number": {
    run: async (page) => {
      await askSuggested(page, SUGGESTED.oneNumber);
      await page.locator(".working").waitFor();
    },
  },
  "05-answer-comparison": {
    run: async (page) => {
      await askSuggested(page, SUGGESTED.comparison);
      await page.locator(".working").waitFor();
    },
  },
  "06-answer-no-number": {
    run: async (page) => {
      await askSuggested(page, SUGGESTED.noNumber);
      await page.locator(".working").waitFor();
    },
  },
  "08-refusal": {
    run: async (page) => {
      await askByTyping(page, "What will usage look like next month?");
      await page.locator(".notice").waitFor();
    },
  },
  "09-rate-limit": { run: replyWith(429, "Too many questions. Wait a minute and try again.") },
  "10-daily-budget": { run: replyWith(429, "The demo has used its budget for today. Ask again tomorrow.") },
  "11-assistant-unavailable": { run: replyWith(503, "The assistant is unavailable right now.") },
  "11-network-failure": {
    run: async (page) => {
      await page.route("**/api/ask", (route) => route.abort());
      await askByTyping(page, SUGGESTED.oneNumber);
      await page.locator(".notice").waitFor();
    },
  },
  "12-question-at-the-limit": {
    run: async (page) => {
      await home(page);
      await page.getByLabel("Ask about usage, people, clients or errors").fill("How many ".repeat(60));
    },
  },
  "13-overview-today": { whole: true, run: (page) => page.goto(`${BASE}/?window=today`, { waitUntil: "networkidle" }) },
  "13-overview-7-days": { whole: true, run: (page) => page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" }) },
  "13-overview-30-days": { whole: true, run: (page) => page.goto(`${BASE}/?window=30d`, { waitUntil: "networkidle" }) },
  "14-reliability-7-days": { whole: true, run: (page) => page.goto(`${BASE}/reliability?window=7d`, { waitUntil: "networkidle" }) },
  "14-reliability-today": { whole: true, run: (page) => page.goto(`${BASE}/reliability?window=today`, { waitUntil: "networkidle" }) },
  "15-backend-unreachable": {
    // Needs the frontend started with BACKEND_URL pointing at nothing; skipped otherwise.
    needs: "DOWN",
    whole: true,
    run: async (page) => {
      await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Try again" }).waitFor();
    },
  },
  "16-focus-field": {
    run: async (page) => {
      await home(page);
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");
    },
  },
  "16-focus-suggestion": {
    run: async (page) => {
      await home(page);
      for (let i = 0; i < 6; i += 1) await page.keyboard.press("Tab");
    },
  },
  "16-focus-window-switch": {
    whole: true,
    run: async (page) => {
      await home(page);
      await page.getByRole("link", { name: "30 days" }).focus();
    },
  },
};

const browser = await chromium.launch();
await mkdir(OUT, { recursive: true });
let taken = 0;
for (const [name, state] of Object.entries(STATES)) {
  if (ONLY && !ONLY.some((prefix) => name.startsWith(prefix))) continue;
  if (state.needs && !process.env[state.needs]) continue;
  for (const width of WIDTHS) {
    for (const mode of MODES) {
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        colorScheme: mode,
        deviceScaleFactor: 2,
        // Screenshots show the settled state; the arrival animation is checked by eye.
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      await state.run(page);
      await page.evaluate(() => document.fonts.ready);
      // Park the pointer, so nothing is photographed in its hover state by accident.
      await page.mouse.move(0, 0);
      const path = `${OUT}/${name}-${width}-${mode}.png`;
      if (state.whole) {
        // MAXH=1600 keeps only the top of a long page, for a closer look.
        const cap = Number(process.env.MAXH ?? 0);
        if (cap > 0) await page.screenshot({ path, clip: { x: 0, y: Number(process.env.FROM ?? 0), width, height: cap }, fullPage: true });
        else await page.screenshot({ path, fullPage: true });
      } else {
        // Down to just past the answer (or the suggestions when there is no answer).
        const bottom = await page.evaluate(() => {
          const region = document.querySelector(".answer-region");
          const list = document.querySelector(".suggestions");
          const end = region && region.childElementCount > 0 ? region : list;
          return Math.ceil(end.getBoundingClientRect().bottom + window.scrollY) + 48;
        });
        await page.setViewportSize({ width, height: Math.max(bottom, 400) });
        await page.screenshot({ path, clip: { x: 0, y: 0, width, height: Math.max(bottom, 400) } });
      }
      await context.close();
      taken += 1;
    }
  }
}
await browser.close();
console.log(`${taken} screenshots in ${OUT}`);
