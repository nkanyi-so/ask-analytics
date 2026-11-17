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

const FIELD = "Ask about usage, people, clients or errors";

async function home(page) {
  await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
}

/** On a wide screen the assistant is docked open. Below that it is opened by its launcher. */
async function openPanel(page) {
  const launcher = page.getByRole("button", { name: "Ask a question" });
  if (await launcher.isVisible()) await launcher.click();
  await page.getByLabel(FIELD).waitFor();
}

async function askByTyping(page, question) {
  await home(page);
  await openPanel(page);
  await page.getByLabel(FIELD).fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

async function askSuggested(page, question) {
  await home(page);
  await openPanel(page);
  await page.getByRole("button", { name: question }).click();
}

function replyWith(status, detail) {
  return async (page) => {
    await page.route("**/api/ask", (route) => route.fulfill({ status, json: { detail } }));
    await askByTyping(page, SUGGESTED.oneNumber);
    await page.locator(".notice").waitFor();
  };
}

const goto = (path) => (page) => page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });

/** name -> { run, whole }. `whole` captures the full page; otherwise one screen, grown to fit the answer. */
const STATES = {
  "01-first-visit": { run: home },
  "01-first-visit-panel-open": {
    run: async (page) => {
      await home(page);
      await openPanel(page);
    },
  },
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
  "07-two-questions-then-another-view": {
    // The assistant keeps its answers when the view changes.
    run: async (page) => {
      await askSuggested(page, SUGGESTED.oneNumber);
      await page.locator(".working").waitFor();
      await page.getByLabel(FIELD).fill(SUGGESTED.noNumber);
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await page.locator(".entry").nth(1).locator(".working").waitFor();
      // Laid over the page, the assistant has to be closed to reach the links, then reopened.
      const overlay = await page.locator(".scrim").isVisible();
      if (overlay) await page.keyboard.press("Escape");
      await page.getByRole("link", { name: "Reliability" }).click();
      await page.getByRole("heading", { name: "Reliability" }).waitFor();
      if (overlay) await openPanel(page);
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
      await openPanel(page);
      await page.getByLabel(FIELD).fill("How many ".repeat(60));
    },
  },
  "13-overview-today": { whole: true, run: goto("/?window=today") },
  "13-overview-7-days": { whole: true, run: goto("/?window=7d") },
  "13-overview-30-days": { whole: true, run: goto("/?window=30d") },
  "14-reliability-7-days": { whole: true, run: goto("/reliability?window=7d") },
  "14-reliability-today": { whole: true, run: goto("/reliability?window=today") },
  "15-backend-unreachable": {
    // Needs the frontend started with BACKEND_URL pointing at nothing; skipped otherwise.
    needs: "DOWN",
    run: async (page) => {
      await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: "Try again" }).waitFor();
    },
  },
  "16-focus-field": {
    run: async (page) => {
      await home(page);
      await openPanel(page);
      await page.getByLabel(FIELD).focus();
    },
  },
  "16-focus-suggestion": {
    run: async (page) => {
      await home(page);
      await openPanel(page);
      await page.getByRole("button", { name: SUGGESTED.noNumber }).focus();
    },
  },
  "16-focus-window-switch": {
    run: async (page) => {
      await home(page);
      await page.getByRole("link", { name: "30 days" }).focus();
    },
  },
  "17-panel-closed": {
    run: async (page) => {
      await home(page);
      await openPanel(page);
      await page.getByRole("button", { name: "Close the Ask panel" }).click();
      await page.getByRole("button", { name: "Ask a question" }).waitFor();
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
        await page.screenshot({ path, fullPage: true });
      } else {
        // One screen. If the answer is taller than the panel, grow the screen until it fits.
        const extra = await page.evaluate(() => {
          const box = document.querySelector(".transcript");
          return box && box.offsetParent !== null ? Math.max(0, box.scrollHeight - box.clientHeight) : 0;
        });
        if (extra > 0) await page.setViewportSize({ width, height: 900 + extra });
        await page.screenshot({ path });
      }
      await context.close();
      taken += 1;
    }
  }
}
await browser.close();
console.log(`${taken} screenshots in ${OUT}`);
