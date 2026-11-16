# Design: ask-analytics

Status: approved on 16 Nov 2026 and built. Where the build differs from the first proposal, this document was updated to match.

## Direction

1. A quiet tool, not a landing page. Near-monochrome, one accent, soft shapes, a lot of air.
2. The answer is the one loud thing: a very large number, and under it the working in plain words.
3. The working is the product's argument. It shows which lookup ran, what came back, and that the number was checked. A visitor should understand the app from one answer, without the README.
4. Everything else is rows and figures, not cards. The dashboard sits below the answer and stays out of its way.
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
| `--surface` | `#FFFFFF` | `#1A1B1D` | the answer panel, inputs | |
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
| `--text-hero` | `clamp(4.5rem, 14vw, 9rem)` / 0.95 | 600, tracking −0.04em | the hero number |
| `--text-hero-words` | `clamp(1.75rem, 4.5vw, 2.75rem)` / 1.15 | 600, tracking −0.02em | the hero when it is a sentence |
| `--text-title` | 1.75rem / 1.2 | 600 | page title |
| `--text-lead` | 1.25rem / 1.45 | 400 | the answer sentence, the intro line |
| `--text-heading` | 1.125rem / 1.35 | 600 | section headings |
| `--text-body` | 1rem / 1.55 | 400 | body, table cells |
| `--text-small` | 0.875rem / 1.45 | 400 | secondary lines, the working |
| `--text-caption` | 0.8125rem / 1.4 | 500 | column headings, units |

All figures use tabular lining numerals. Labels are sentence case. Text lines stay under 72 characters.

## Space, shape, motion

- **Spacing** on a 4px base: `--space-1` 4, `-2` 8, `-3` 12, `-4` 16, `-5` 24, `-6` 32, `-7` 48, `-8` 64, `-9` 96. Sections are separated by `--space-8`; the answer has `--space-9` above the dashboard.
- **Width**: content column 72rem at most, text measure 40rem, side gutter 16px on a phone and 32px above 768.
- **Radius** by rank, not one value everywhere: `--radius-control` 10px (inputs, buttons), `--radius-panel` 20px (the answer panel only), `--radius-pill` 999px (suggested questions, the window switch).
- **Elevation**: none. Rank comes from surface and space. No shadows, no gradients.
- **Motion**: one moment. When an answer arrives it rises 8px and fades in over 240ms, and the working follows 60ms later. The number does not count up, because a count-up shows numbers that are not in the data. With "reduce motion" on, nothing moves.
- **Focus**: a 2px accent ring with a 2px offset on every interactive element, visible in both modes.

## Layout

Left aligned throughout. The answer panel is the only bordered, rounded surface on the page.

```
1280
┌──────────────────────────────────────────────────────────────────────────────┐
│ ask-analytics                                        Overview   Reliability  │
│                                                                              │
│ Usage numbers for a workspace of 8 tools and 40 people.                      │
│ Ask a question. The assistant can only answer with numbers                   │
│ this page can derive.                                                        │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────┐ ┌────────┐ │
│ │ Ask about usage, people, clients or errors                   │ │  Ask   │ │
│ └──────────────────────────────────────────────────────────────┘ └────────┘ │
│ (How many invoices…) (Which tool is nobody touching?) (Did email usage…)    │
│                                                                              │
│ ╭──────────────────────────────────────────────────────────────────────────╮ │
│ │                                    │ How this was worked out             │ │
│ │  10                                │ 1  Looked up usage by tool          │ │
│ │                                    │    for the last 7 days              │ │
│ │  In the last 7 days, 10 invoices   │ 2  Got back                         │ │
│ │  were issued.                      │    Invoice generator   10           │ │
│ │                                    │    7 days before 51 · change −41    │ │
│ │                                    │ 3  ✓ Checked: every number in the   │ │
│ │                                    │    answer is in that result         │ │
│ ╰──────────────────────────────────────────────────────────────────────────╯ │
│                                                                              │
│                                                                              │
│ Data to 30 Oct 2026. Seeded demo data.          (Today)(7 days)(30 days)     │
│                                                                              │
│ People            35 active   2 went quiet   3 never showed up   40 invited  │
│ ──────────────────────────────────────────────────────────────────────────── │
│ Tools             Tool                 Output   Change   People   Errors     │
│                   Call agenda              46       −8       26        1     │
│                   …                                                          │
│ Clients           …                                                          │
│ People            …                                                          │
└──────────────────────────────────────────────────────────────────────────────┘

375: one column. The number, then the sentence, then the working, each full width.
     Tables become one stacked row per item, with the figure on the right.
768: the working sits under the answer, and each section heading sits above its table, so no table has to fit beside a heading. Both move alongside from 1024.
```

The three steps are numbered because they are a real sequence: look up, read the result, check.

The intro line and the Ask field come first on Overview, above the window switch, because the window switch belongs to the dashboard, not to the question. Reliability keeps the same header and tables and has no Ask field, as now.

## Words

- The field label is "Ask about usage, people, clients or errors". The button says "Ask" and, while waiting, "Asking".
- The working uses the names a reader would use: "usage by tool", "activity by person", "activity by client", "errors by source", "the roster". The lookup's code name is not shown.
- Messages from the backend (refusal, limits, unavailable) are shown as sent. The page adds one plain line saying what to do next.

## Screen states

Every state below gets a screenshot at 375, 768 and 1280, in light and dark.

**Ask**

1. **First visit.** Intro line, empty field, three suggested questions, no answer panel.
2. **Demo mode** (no API key). As first visit, with one line under the field: "Demo mode: recorded answers, live model not connected". Asking anything but a recorded question shows the backend's "no recorded answer" message in the refusal layout.
3. **Loading.** The field and suggestions are disabled, the button reads "Asking", and the panel shows "Looking it up. This usually takes a few seconds." No spinner, no pulsing dots.
4. **Answer with one number.** Hero number, the sentence, the three steps.
5. **Answer with a comparison.** Hero is the first number; the other numbers are marked as checked in the sentence; the row shows current, previous and change.
6. **Answer with no number.** The sentence is the hero ("Nobody has used Contact enrichment in the last 7 days."); the steps are unchanged.
7. **Answer that used more than one lookup.** Step 1 and step 2 repeat per lookup, in the order called. Built, but not photographed: no recorded answer uses two lookups, and the live model did not use two for any question tried.
8. **Refusal.** No number. The hero is "That can't be answered from this data." Under it, the backend's list of what can be asked, and one line: "No lookup ran. The assistant refuses rather than guesses."
9. **Rate limit reached** (429). The backend's message, plus "Your question is still in the field."
10. **Daily budget reached** (429). The backend's message, plus "The dashboard below still works."
11. **Assistant unavailable** (503) and **network failure.** "The assistant could not be reached." plus "Try again", which re-sends the same question.
12. **Question too long or empty.** Pressing Ask with nothing typed puts the cursor in the field; the button is not greyed out, so the page always shows its one accent. The field stops at 500 characters and says so.

**Dashboard**

13. **Overview** in each window: today, 7 days, 30 days. The 30-day view includes "no earlier data" where the backend sends no previous value.
14. **Reliability** with errors (7 days, today). The page with none ("No errors in this window.") is built but cannot be photographed: the seeded data has errors in every window.
15. **Backend unreachable.** The page-level error: what happened, and a "Try again" button.

**Every interactive element**: default, hover, focus-visible, waiting. Focus is photographed (three shots). Hover is not: it only darkens a suggestion or lifts the button slightly, and was checked by eye. While an answer is awaited the field is read-only and the buttons are marked `aria-disabled`, not disabled, so keyboard focus stays where it was.

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
- **Phone tables** are a name and one wrapped line of labelled figures per row. One line per figure made the page eleven screens long.
- **Live answers are the model's words.** It writes things like "the 7d window" and "(email_sent)". The page shows them as written; changing them means changing the prompt, which is backend behaviour and outside this pass.

## Screenshots

`frontend/scripts/screenshots.mjs` takes every state at 375, 768 and 1280 in light and dark: 126 in demo mode and 18 against the live model (12 real questions, $0.008). A few are kept in `docs/design/`; the full set is written to `screenshots/`, which is not tracked.

## Process, after approval

1. Tokens in one file (`frontend/src/app/tokens.css`). What stays inline: breakpoints (CSS cannot read a variable in a media query), and a few `em` offsets that only mean something next to their own text, such as the padding of a marked number.
2. Build, with `make check` green and no change to the backend, the API or existing tests.
3. Playwright screenshots of every state at three widths in both modes; review against this document; fix; repeat once. Playwright is a new development dependency and gets its line in `docs/decisions/`.
4. `npx impeccable detect`, and fix what it finds.
5. Final screenshots and a short list of anything still uncertain.
