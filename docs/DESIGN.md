# Design: ask-analytics

Status: approved on 16 Nov 2026 and built; recomposed on 17 Nov 2026 as a dashboard with the assistant docked beside it. This document describes what is built.

## Direction

1. A quiet tool, not a landing page. Near-monochrome, one accent, soft shapes, a lot of air.
2. The answer is the one loud thing: the largest number on the screen, and under it the working in plain words.
3. The working is the product's argument. It shows which lookup ran, what came back, and that the number was checked. A visitor should understand the app from one answer, without the README.
4. Two anchored parts, like the product this is rebuilt from: a dashboard you scan (key values first, then detail), and an assistant that stays in the same place whichever view you are on.
5. Nothing is invented. Every figure on screen is a field from the API, in every state and every screenshot.

Who it is for: a recruiter or engineering lead with two minutes. They should leave thinking the person who built this finishes things.

## What the answer can honestly show

The API returns the answer text, which lookups were called and with which arguments. It does not return what the lookups returned, and the brief rules out changing the backend. So:

- **The hero number** is the first number in the answer text that is not part of a date or a window phrase ("the last 7 days"). If the answer has no such number ("Nobody has used Contact enrichment"), the answer sentence itself is the hero, in large type.
- **"What it returned"** comes from a new route in the frontend's own server, `GET /api/evidence`. It reads the same lookup through the existing backend endpoints, with the token, as the pages already do, and returns titled rows of figures: no ids, and previous-window values only when the model asked for the comparison. The Ask panel shows the rows the answer rests on. It shows rows; it never counts or adds them.
- **"Checked"** is a statement of what the backend does before it sends any answer: every number must be in a lookup result of that turn, or the answer is replaced by a refusal. The panel also marks a number in the answer when it found that number in the rows shown **and** the answer uses that measure's own words ("10 invoices were issued" against "invoice issued 10"). A shared number alone is not enough: "22 errors" is never marked against a row where 22 is the count of active people. When the panel is not sure, it shows the row and marks nothing.

If you would rather the backend returned the lookup results with the answer, that is cleaner and a small change, but it is an API change and so outside this pass.

## Colour

One accent, a muted evergreen: the colour of an auditor's tick. It is used for the primary button, focus rings, links, and the "checked" mark, and nowhere else. There is no red and no second accent. An error is told apart by its words, not by colour or decoration, and a fall is not coloured differently from a rise, because down is not always bad.

Contrast ratios are computed, not estimated. AA needs 4.5 for text and 3 for control borders and focus rings.

| Token | Light | Dark | Used for | Lowest contrast (light / dark) |
|---|---|---|---|---|
| `--canvas` | `#FAFAF9` | `#121314` | page background | |
| `--surface` | `#FFFFFF` | `#1A1B1D` | tiles, cards and the assistant | |
| `--sunken` | `#F1F1EF` | `#0D0E0F` | the window switch, a suggestion under the pointer | |
| `--line` | `#E3E3E0` | `#2B2D30` | hairlines between rows (decorative) | |
| `--control` | `#85898E` | `#6E7379` | borders of inputs and buttons | 3.37 / 3.60 |
| `--ink` | `#17191B` | `#ECEDEE` | text, the hero number | 15.24 / 12.77 (on a checked number) |
| `--ink-2` | `#565B60` | `#A9ADB2` | secondary text | 6.07 / 7.64 |
| `--ink-3` | `#676C71` | `#8B9096` | captions, units | 4.69 / 5.36 |
| `--accent` | `#17694D` | `#79C9A6` | button, links, focus ring, tick | 5.74 / 7.64 |
| `--accent-ink` | `#FFFFFF` | `#0E1F18` | text on the accent | 6.64 / 8.73 |
| `--accent-soft` | `#E6F1EC` | `#1B2A24` | background of a checked number | |

Light and dark follow the system setting. There is no toggle: it would be one more control on a page that should have few.

## Type

One family, **Hanken Grotesk**, loaded through `next/font` (self-hosted at build, no new package). It is plain and even, with figures that stay calm at very large sizes, which is where this design spends its weight. No second typeface and no monospace. The first proposal named Instrument Sans; the `impeccable` detector flags it as overused, so it was replaced.

| Token | Size / line height | Weight | Used for |
|---|---|---|---|
| `--text-hero` | 4.5rem / 0.95 | 600, tracking −0.04em | the hero number, in the assistant |
| `--text-hero-words` | 1.75rem / 1.15 | 600, tracking −0.02em | the hero when it is a sentence; notices |
| `--text-title` | 1.75rem / 1.2 | 600 | page title |
| `--text-answer` | 1.125rem / 1.45 | 400 | the answer sentence |
| `--text-figure` | 2rem / 1.1 | 600, tracking −0.02em | tile values, the People figures |
| `--text-heading` | 1.125rem / 1.35 | 600 | section headings |
| `--text-body` | 1rem / 1.55 | 400 | body, table cells |
| `--text-small` | 0.875rem / 1.45 | 400 | secondary lines, the working |
| `--text-caption` | 0.8125rem / 1.4 | 500 | column headings, units |

All figures use tabular lining numerals. Labels are sentence case. Text lines stay under 72 characters.

## Space, shape, motion

- **Spacing** on a 4px base: `--space-1` 4, `-2` 8, `-3` 12, `-4` 16, `-5` 24, `-6` 32, `-7` 48, `-9` 96. Blocks of the dashboard are `--space-7` apart; tiles and cards are `--space-3` apart.
- **Width**: the dashboard column is 72rem at most; the assistant is 26rem; text measure 40rem; side gutter 16px on a phone and 32px above 768.
- **Radius** by rank, not one value everywhere: `--radius-control` 10px (inputs, buttons, suggested questions), `--radius-card` 14px (tiles and cards), `--radius-pill` 999px (the window switch, the launcher).
- **Elevation**: none. Rank comes from surface and space. No shadows, no gradients. When the assistant lies over the page on a small screen, the page behind is dimmed, not shadowed.
- **Motion**: one moment. When an answer arrives it rises 8px and fades in over 240ms, and the working follows 60ms later. The number does not count up, because a count-up shows numbers that are not in the data. With "reduce motion" on, nothing moves.
- **Focus**: a 2px accent ring with a 2px offset on every interactive element, visible in both modes.

## Layout

Two parts in one frame, mounted once so neither is rebuilt when the view changes.

- **The dashboard**, left. A header with the two views and the window switch, which drives every figure under it. Then key values first: one tile per tool, eight tiles in two even rows. Then cards: People beside Clients, and Everyone full width. Reliability is one full-width card. One tile style, one card style, one table style, repeated.
- **The assistant**, right. A full-height column with a title, a running list of questions and answers, and the field at the bottom. Suggested questions sit in its empty state. It is docked and open on arrival where there is room, because a visitor with two minutes will not go looking for a launcher.

```
1280 and wider: docked. The dashboard reflows beside it; nothing is covered.
┌───────────────────────────────────────────────────┬────────────────────────┐
│ ask-analytics  Overview  Reliability   [T|7d|30d] │ Ask                  × │
│                                                   │ mode line              │
│ Overview                                          ├────────────────────────┤
│ Who is using what … Data to 30 Oct 2026.          │ the question           │
│                                                   │                        │
│ One headline number per tool                      │ 10                     │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                   │ In the last 7 days, …  │
│ │ 46  │ │  0  │ │ 91  │ │ 10  │                   │ ────────────────────── │
│ └─────┘ └─────┘ └─────┘ └─────┘                   │ How this was worked out│
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                   │ 1 Looked up …          │
│ └─────┘ └─────┘ └─────┘ └─────┘                   │ 2 Got back …           │
│ ┌ People ─────────┐ ┌ Clients ──────────┐         │ 3 ✓ Checked            │
│ └─────────────────┘ └───────────────────┘         ├────────────────────────┤
│ ┌ Everyone ───────────────────────────────┐       │ [ Ask a question ][Ask]│
└───────────────────────────────────────────────────┴────────────────────────┘

Below 1280: the assistant is closed on arrival, behind an "Ask a question" button
fixed at the bottom right. Opened, it is a dialog over the right of the page (the
whole screen on a phone): the page behind is dimmed, cannot be scrolled and cannot
take focus. Escape or the close button closes it, as does a click on the dimmed
page where any shows, and focus returns to the button.

Closed at any width: the dashboard takes the full width and the button is shown.
Phone: tiles two across, cards one across, each table row a name and one wrapped
line of labelled figures.
```

The three steps are numbered because they are a real sequence: look up, read the result, check.

**It looks like a chat and is not one.** The backend answers each question with no memory of the last, so "and what about last month?" would not work. The assistant is therefore a list of separate questions and answers, titled "Ask" and not "Chat", and the line under the field says "Each question stands alone." Real follow-ups would need the backend to accept earlier turns; that is a later piece of work.

**What changed from the first build, and why.** The first build was one column: question, a very large answer, then tables. It read like a document. The product this is rebuilt from has a dashboard and an assistant side by side, and that composition is what is borrowed here: structure only, no names, terms or data. Two things differ from the original on purpose. Its assistant floats over the dashboard and covers about two fifths of it; this one is docked, so nothing is covered. And its answers show no trace of how they were reached; this one keeps the working, because the working is the point.

The cost is that the answer no longer fills the page. Its number is still the largest on the screen, but the dashboard and the answer now share the stage.


## Words

- The assistant is titled "Ask". The field's label is "Ask about usage, people, clients or errors" and its placeholder "Ask a question". The button says "Ask" and, while waiting, "Asking".
- The working uses the names a reader would use: "usage by tool", "activity by person", "activity by client", "errors by source", "the roster". The lookup's code name is not shown.
- Messages from the backend (refusal, limits, unavailable) are shown as sent. The page adds one plain line saying what to do next.

## Screen states

Every state below gets a screenshot at 375, 768 and 1280, in light and dark.

**Ask**

1. **First visit.** On a wide screen: the dashboard, with the assistant docked and showing its empty state (what it does, three questions to try). Below 1280: the dashboard and the "Ask a question" button; the opened assistant is photographed as a state of its own.
2. **Demo mode** (no API key). The line under the assistant's title reads "Demo mode: recorded answers, live model not connected." Asking anything but a recorded question shows the backend's "no recorded answer" message in the refusal layout.
3. **Loading.** The field is read-only, the button reads "Asking", and the new entry shows "Looking it up. This usually takes a few seconds." No spinner, no pulsing dots.
4. **Answer with one number.** Hero number, the sentence, the three steps.
5. **Answer with a comparison.** Hero is the first number; the other numbers are marked as checked in the sentence; the row shows current, previous and change.
6. **Answer with no number.** The sentence is the hero ("Nobody has used Contact enrichment in the last 7 days."); the steps are unchanged.
7. **Several questions, and a change of view.** Each question is added under the last, and the list is still there after moving from Overview to Reliability. **An answer that used more than one lookup** repeats steps 1 and 2 per lookup. Step 1 and step 2 repeat per lookup, in the order called. Built, but not photographed: no recorded answer uses two lookups, and the live model did not use two for any question tried.
8. **Refusal.** No number. The hero is "That can't be answered from this data." Under it, the backend's list of what can be asked, and one line: "No lookup ran. The assistant refuses rather than guesses."
9. **Rate limit reached** (429). The backend's message, plus "Ask it again in a minute."
10. **Daily budget reached** (429). The backend's message, plus "The dashboard still works."
11. **Assistant unavailable** (503) and **network failure.** "The assistant could not be reached." plus "Try again", which re-sends the same question.
12. **Question too long or empty.** Pressing Ask with nothing typed puts the cursor in the field; the button is not greyed out, so the page always shows its one accent. The field stops at 500 characters and says so.

**Dashboard**

13. **Overview** in each window: today, 7 days, 30 days. The 30-day view includes "no earlier data" where the backend sends no previous value.
14. **Reliability** with errors (7 days, today). The page with none ("No errors in this window.") is built but cannot be photographed: the seeded data has errors in every window.
15. **Backend unreachable.** The view shows what happened and a "Try again" button. The frame and the assistant still render.
16. **Focus**, photographed on the field, a suggested question and the window switch.
17. **Assistant closed** on a wide screen: the dashboard at full width, with the button to reopen it.

**Every interactive element**: default, hover, focus-visible, waiting. Focus is photographed (three shots). Hover is not: it only darkens a suggestion or lifts the button slightly, and was checked by eye. While an answer is awaited the field is read-only and the Ask button is marked `aria-disabled`, not disabled, so keyboard focus stays where it was.

## What I am unsure about

- **Telling the two 429s apart.** Rate limit and daily budget are both a 429, and only the message text differs. I would pick the helper line by looking for the word "budget" in the message, and fall back to showing the message alone. A field in the API would be sturdier, but that is an API change.
- **The hero number rule.** "First number that is not a date or a window" is right for the questions I have seen. For a comparison the model sometimes leads with the current value and sometimes with the change. Both are true numbers; which is "the" number is a judgement the page cannot make. A sign the model wrote ("-41") is kept on the hero. A direction it wrote in words ("down by 104") is not: the hero shows 104 and the sentence under it says which way.
- **Evidence when the model filtered.** For a question about one person or one tool, the page filters the rows by that id. That is selecting, not computing, but it is logic in the frontend that the current rules keep to a minimum.
- **Live screenshots.** Every state can be shot in demo mode for free except "live answer, no demo label". Shooting that with the real model costs well under one cent per question; I will ask before doing it.
- **Font loading in CI.** `next/font` fetches Hanken Grotesk from Google at build time. If that proves flaky in CI, the fallback is to commit the font files, which needs a line in `docs/decisions/`.

## What the build changed

- **Typeface.** Instrument Sans became Hanken Grotesk, after the `impeccable` detector flagged the first as overused.
- **No rule beside notices.** Refusals and errors first had a thick rule down the left side. The detector flags that as a generated-UI habit, and it was decoration, so it went.
- **The Ask button is never greyed out when idle**, so the page always shows its one accent.
- **Recomposed on 17 Nov 2026** as a dashboard with a docked assistant; see Layout. Tiles and cards came back with it: the first build avoided cards, but key values in a grid are what a dashboard is, and one plain card style without icons is not the generated look the brief warned against.
- **Phone tables** are a name and one wrapped line of labelled figures per row. One line per figure made the page eleven screens long.
- **Live answers are the model's words.** It writes things like "the 7d window" and "(email_sent)". The page shows them as written; changing them means changing the prompt, which is backend behaviour and outside this pass.

## Screenshots

`frontend/scripts/screenshots.mjs` takes every state at 375, 768 and 1280 in light and dark: 144 in demo mode (24 states) and 30 against the live model. Ten are kept in `docs/design/`; the full set is written to `screenshots/`, which is not tracked. Live shots across both builds took 72 real questions, about $0.04.

## Process, after approval

1. Tokens in one file (`frontend/src/app/tokens.css`). What stays inline: breakpoints (CSS cannot read a variable in a media query), and a few `em` offsets that only mean something next to their own text, such as the padding of a marked number.
2. Build, with `make check` green and no change to the backend, the API or existing tests.
3. Playwright screenshots of every state at three widths in both modes; review against this document; fix; repeat once. Playwright is a new development dependency and gets its line in `docs/decisions/`.
4. `npx impeccable detect`, and fix what it finds.
5. Final screenshots and a short list of anything still uncertain.
