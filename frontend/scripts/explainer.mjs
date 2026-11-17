// A narrated walk through the app, for someone who has never seen it.
//
//   BASE=http://localhost:3000 OUT=../screenshots node scripts/explainer.mjs
//
// It drives the real app in a browser and records the screen, speaks each scene with
// the macOS `say` voice, shows the same words as captions, and joins the two with
// ffmpeg. Needs macOS (`say`) and ffmpeg. Run it against a live backend: it asks three
// real questions (well under one cent). In demo mode a tool's name is not clickable.
// The recording in screenshots/explainer.mp4 predates the 17 Nov 2026 redesign.
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { chromium } from "playwright";

const BASE = process.env.BASE ?? "http://localhost:3000";
const OUT = resolve(process.env.OUT ?? "explainer-out");
const VOICE = process.env.VOICE ?? "Daniel";
const WORK = join(OUT, "explainer-work");
const SIZE = { width: 1280, height: 720 };
const FIELD = "Ask about usage, people, clients or errors";

// The last line quotes the eval result. Keep it in step with docs/eval-results.md.
const OUTRO =
  process.env.OUTRO ??
  "And the About page shows how it is tested. Forty questions with known right answers, asked of the real model. It scored seventy percent the first time, and one hundred after the faults it found were fixed. A number you can trust, and an assistant that cannot invent one.";

const pause = (ms) => new Promise((done) => setTimeout(done, ms));

async function caption(page, text) {
  await page.evaluate((words) => {
    let bar = document.getElementById("explainer-caption");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "explainer-caption";
      bar.style.cssText =
        "position:fixed;left:24px;bottom:24px;width:780px;z-index:99999;padding:14px 18px;" +
        "border-radius:12px;background:rgba(18,19,20,.92);color:#fff;font:500 19px/1.4 var(--font);" +
        "pointer-events:none";
      document.body.append(bar);
    }
    bar.textContent = words;
  }, text);
}

/** Draw the eye to one part of the screen until the next scene. */
async function point(page, selector) {
  await page.evaluate((target) => {
    document.querySelectorAll("[data-explainer]").forEach((el) => {
      el.style.outline = "";
      el.style.outlineOffset = "";
      el.removeAttribute("data-explainer");
    });
    const el = target ? document.querySelector(target) : null;
    if (!el) return;
    el.setAttribute("data-explainer", "");
    el.style.outline = "3px solid var(--brand)";
    el.style.outlineOffset = "6px";
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, selector);
}

async function type(page, text) {
  await page.getByLabel(FIELD).pressSequentially(text, { delay: 28 });
  await pause(300);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

/** Each scene: what is said (and captioned), and what happens on screen while it is said. */
const SCENES = [
  {
    say: "This is a demo of something I built for a company. They gave their people a set of internal tools, and nobody could say, simply, who was actually using what.",
    act: async (page) => {
      await page.goto(`${BASE}/?window=7d`, { waitUntil: "networkidle" });
    },
  },
  {
    say: "This page answers that. The top row is the key numbers for the week. Thirty-five people were active. And three were invited and never showed up at all.",
    act: (page) => point(page, ".kpis"),
  },
  {
    say: "Press a number and what is behind it opens: a chart per day, and each tool underneath. Ten invoices issued. Ninety-one emails sent. And one tool that nobody touched.",
    act: (page) => point(page, "#kpi-detail"),
  },
  {
    // Spelt out for the voice; the caption shows it as written.
    show: "On the right is an assistant you can ask in plain English. AI models are known for making numbers up. This one cannot.",
    say: "On the right is an assistant you can ask in plain English. A I models are known for making numbers up. This one cannot.",
    act: async (page) => {
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
      await point(page, ".ask-pitch");
    },
  },
  {
    say: "Ask it how many invoices were issued in the last seven days.",
    act: async (page) => {
      await point(page, null);
      await page.getByRole("button", { name: "How many invoices were issued in the last 7 days?" }).click();
    },
  },
  {
    // Spoken only once the answer is on screen.
    wait: (page) => page.locator(".working").waitFor(),
    say: "It says ten.",
    act: (page) => point(page, ".hero-number"),
  },
  {
    say: "It cannot do sums, and it never sees the raw data. It can only pick one of five fixed lookups. The code runs the lookup, and then checks every number in the answer against what came back.",
    act: (page) => point(page, ".steps"),
  },
  {
    say: "You can also just click a tool, and it asks for you.",
    act: async (page) => {
      await point(page, null);
      await page.getByRole("button", { name: "Invoice generator", exact: true }).click();
    },
  },
  {
    wait: (page) => page.locator(".entry").nth(1).locator(".working").waitFor(),
    say: "Invoices are down by forty-one, and the same tool threw eighty-six errors.",
    act: (page) => point(page, ".entry:nth-child(2) .answer-text"),
  },
  {
    say: "And if you ask something the data cannot answer, like what usage will look like next month?",
    act: async (page) => {
      await point(page, null);
      await type(page, "What will usage look like next month?");
    },
  },
  {
    wait: (page) => page.locator(".entry").nth(2).locator(".notice").waitFor(),
    say: "It refuses, rather than guesses.",
    act: (page) => point(page, ".entry:nth-child(3) .notice"),
  },
  {
    say: "The assistant stays with you as you move around. This second view shows what is failing, and who it reached.",
    act: async (page) => {
      await page.getByRole("link", { name: "Reliability" }).click();
      await page.getByRole("heading", { name: "Reliability" }).waitFor();
      await point(page, ".data tbody tr");
    },
  },
  {
    say: OUTRO,
    act: async (page) => {
      await point(page, null);
      await page.getByRole("link", { name: "About" }).click();
      await page.getByRole("heading", { name: "About this demo" }).waitFor();
      await point(page, "#tested");
    },
  },
];

rmSync(WORK, { recursive: true, force: true });
mkdirSync(WORK, { recursive: true });

// 1. Speak every scene to a file and measure it.
const lengths = SCENES.map((scene, index) => {
  const file = join(WORK, `scene-${index}.aiff`);
  execFileSync("say", ["-v", VOICE, "-r", "172", "-o", file, scene.say]);
  const seconds = execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]);
  return Number(String(seconds).trim());
});

// 2. Record the screen, noting when each scene starts.
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: WORK, size: SIZE }, deviceScaleFactor: 1 });
const page = await context.newPage();
const began = Date.now();
const starts = [];
for (const [index, scene] of SCENES.entries()) {
  // Some lines describe an answer: hold them until the answer is on screen.
  if (scene.wait) await scene.wait(page);
  if (index > 0) await caption(page, scene.show ?? scene.say);
  starts.push((Date.now() - began) / 1000);
  const spoken = pause(lengths[index] * 1000 + 500);
  await scene.act(page);
  if (index === 0) await caption(page, scene.show ?? scene.say);
  await spoken;
}
await pause(800);
const video = await page.video().path();
await context.close();
await browser.close();

// 3. Lay each spoken scene at its start time and join sound to picture.
const inputs = SCENES.flatMap((_, index) => ["-i", join(WORK, `scene-${index}.aiff`)]);
const delays = SCENES.map((_, index) => `[${index + 1}:a]adelay=${Math.round(starts[index] * 1000)}:all=1[a${index}]`);
const mix = `${SCENES.map((_, index) => `[a${index}]`).join("")}amix=inputs=${SCENES.length}:normalize=0[sound]`;
const output = join(OUT, "explainer.mp4");
execFileSync("ffmpeg", [
  "-y", "-loglevel", "error", "-i", video, ...inputs,
  "-filter_complex", [...delays, mix].join(";"),
  "-map", "0:v", "-map", "[sound]",
  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
  output,
]);
rmSync(WORK, { recursive: true, force: true });
const total = starts.at(-1) + lengths.at(-1);
console.log(`${output} (${Math.round(total)} seconds, ${SCENES.length} scenes)`);
