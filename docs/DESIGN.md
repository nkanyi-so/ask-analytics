# Design: ask-analytics

Status: this is the third design, approved from a static mock on 17 Nov 2026 and built the same day. It replaces the quiet near-monochrome design of 16 Nov, which was rejected as flat: no charts, numbers that could not be pressed, and a structure unlike the product this is rebuilt from. This document describes what is built.

## Direction

1. It should look like a product a company ships: a sidebar, a page header, tabs, key numbers, a chart, tables. The look is borrowed from current product UI (the Untitled UI kit for structure, Apple's system apps for finish); the structure is borrowed from the product this is rebuilt from. No names, terms or data from it.
2. The key numbers are the way in. Each of the four is a button; pressing one opens the chart and the tables behind it.
3. The assistant stays docked beside the dashboard on every view, and its answer still shows its working: which lookup ran, what came back, and that the number was checked.
4. Nothing is invented. Every figure on screen is a field from the API. A bar's height is drawn from its value and the largest value in the chart; that ratio is never shown as a number.

Who it is for: a recruiter or engineering lead with two minutes.

## What the answer can honestly show

The API returns the answer text and which lookups were called with which arguments. It does not return what the lookups returned. So:

- **The hero number** is the first number in the answer that is not part of a date, a span of days or a window phrase. If there is none, the sentence is the hero.
- **"Got back"** comes from the frontend's own server route, `GET /api/evidence`, which reads the same lookup through the backend and returns titled rows of figures. The panel shows rows; it never counts or adds.
- **"Checked"** states what the backend does before sending any answer. The panel marks a number in the answer only when it found that number in the rows shown and the answer uses that measure's own words.

## Colour

One brand blue, and one colour each for better and worse. A change is coloured by what it means, not by its direction: more outputs is green, more errors is red, fewer errors is green. "No change" and missing comparisons are grey. The Errors chart is red; every other chart is blue.

Contrast is computed. Text meets 4.5:1 on every surface it is used on in both themes, with one rule to keep: `--text-3` is not used on `--track` in light (4.19).

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` | `#f5f5f7` | `#000000` | the page |
| `--surface` | `#ffffff` | `#1c1c1e` | cards, answers |
| `--surface-2` | `#fafafb` | `#232326` | table headings, a suggestion under the pointer |
| `--glass` | white at 72% | `#1c1c1e` at 72% | the sidebar and the assistant, over a blur |
| `--track` / `--thumb` | `#e9e9ec` / `#ffffff` | `#2c2c2e` / `#636366` | the window switch, the question field |
| `--text`, `--text-2`, `--text-3` | `#1d1d1f`, `#515154`, `#6e6e73` | `#f5f5f7`, `#aeaeb2`, `#98989d` | text, secondary, captions |
| `--brand` | `#0a66e4` | `#0a84ff` | bars, the chosen number's outline, focus rings |
| `--brand-solid` | `#0a66e4` | `#0a66e4` | behind white text: buttons, your question |
| `--brand-text` | `#0a5ad0` | `#409cff` | links |
| `--good` | `#177541` | `#30d158` | a change for the better |
| `--bad` | `#c9271e` | `#ff6961` | a change for the worse, error bars |

**Themes.** Light and dark are one design. The page follows the system setting until the reader presses the toggle in the page header; the choice is kept in the browser (`localStorage`, key `theme`) and applied by a small inline script before first paint, so there is no flash.

## Type

The system font (San Francisco on Apple devices, the platform's own elsewhere). No web font is loaded. Figures are tabular.

| Token | Size | Used for |
|---|---|---|
| `--text-hero` | 3.25rem, 700 | the answer's number |
| `--text-kpi` | 2.125rem, 700 | the four key numbers |
| `--text-title` | 1.75rem, 700 | page title |
| `--text-hero-words` | 1.375rem, 700 | an answer with no number; the assistant's opening line |
| `--text-heading` | 1.0625rem, 600 | card headings |
| `--text-lead` | 0.9375rem | answers, prose |
| `--text-body` | 0.875rem | tables, controls |
| `--text-small`, `--text-caption`, `--text-micro` | 0.8125, 0.75, 0.6875rem | secondary lines, column headings, small labels |

Small section labels inside a card ("Behind the number") are uppercase at `--text-micro`. Everything else is sentence case.

## Space, shape, depth, motion

- **Spacing** on a 4px base: `--space-1` 4 to `--space-9` 72. Cards are `--space-4` apart.
- **Radius** by rank: cards 16px, controls 10px, chat bubbles 18px, bars 7px, pills fully round.
- **Depth**: in light, cards carry one soft shadow on a grey page. In dark there are no shadows; rank comes from layered greys on true black. The sidebar and the assistant are translucent over a blur.
- **Motion**: a card lifts 1px under the pointer; an answer rises and fades in; the assistant slides in when it opens over the page. None of it runs with "reduce motion" on. Numbers do not count up.
- **Focus**: a 2px brand outline, 2px off, on every interactive element in both themes.

## Layout

```
┌────┬──────────────────────────────────────────────┬──────────────────────┐
│ ✓  │ Usage                    [Today|7 days|30] ◐ │ Ask  Demo          × │
│    │ Who is using what.                           │                      │
│ Us │ Overview   Reliability                       │ your question  ▐     │
│ Ab │ ──────────────────────────────────────────── │ ┌──────────────────┐ │
│    │ Demo  Made-up data …            How it works │ │ 10               │ │
│    │ ┌──────┐ ┏━━━━━━┓ ┌──────┐ ┌──────┐          │ │ In the last 7 …  │ │
│    │ │ 35   │ ┃ 344  ┃ │ 94   │ │ 3    │          │ │ How this was     │ │
│    │ └──────┘ ┗━━━v━━┛ └──────┘ └──────┘          │ │ worked out 1 2 ✓ │ │
│    │ ┏ Outputs ━━━━━━━━━━━━━━━━━━━━━━━━┓          │ └──────────────────┘ │
│    │ ┃ ▁ ▁ █ █ █ █ █   per day         ┃          │                      │
│    │ ┃ Behind the number: tools│clients┃          │ [ Ask a question ]   │
│    │ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛          │                      │
│    │ ┌ Everyone (sortable) ─────────────┐         │                      │
└────┴──────────────────────────────────────────────┴──────────────────────┘
```

- **Sidebar.** A slim rail: the mark, Usage, About. On a phone it becomes a bar across the top.
- **Page header.** Title, one line, and on the Usage views the window switch (a segmented control) and the theme toggle. Under it, tabs: Overview and Reliability.
- **Key numbers.** Active people, Outputs, Errors, Never showed up. The first three show their value and a change pill against the window before; "Never showed up" shows "of 40 invited" instead, since it does not vary by window. They are toggle buttons (`aria-pressed`); the chosen one is outlined, with a notch pointing into the card it opens. Outputs is chosen on arrival.
- **The detail card.** A bar chart per day (per hour for Today), then "Behind the number":
  - *Active people*: everyone invited, sorted by logins.
  - *Outputs*: tools (with a small per-day chart each) beside clients.
  - *Errors*: tools sorted by errors.
  - *Never showed up*: who never logged in, beside who went quiet.
- **Everyone.** A sortable table with initials, client, logins, outputs, last seen and role; eight rows until asked for in full. Hidden while "Active people" is chosen, because the same table is then open above.
- **Reliability.** The errors chart, then each source of errors, its change, and who it reached.
- **About.** Prose in cards at a reading width, with the eval results.
- **The assistant.** Docked and open from 1280 wide. Below that it is behind an "Ask a question" button and opens as a dialog over the page: the page is dimmed, cannot scroll and cannot take focus; Escape, the close button or the dimmed page closes it and focus returns to the button. A question is a bubble on the right; the answer is a card on the left with the number, the sentence and the three numbered steps (a real sequence: look up, read, check).
- **Joined.** With a live model, a tool's name in a table is a button that asks the assistant about that tool. In demo mode it is plain text, because a question written on the spot has no recorded answer.
- **Phone.** Key numbers two across; each table row becomes a name and one wrapped line of labelled figures; chart labels drop the weekday.

**It looks like a chat and is not one.** Each question is answered with no memory of the last, so the panel is titled "Ask" and the line under the field says "Each question stands alone." Follow-ups are later work and need the backend to accept earlier turns.

## Charts

Charts are plain elements, not a library: a grid of bars whose heights are set from the API's values. Each chart is a `figure` with a spoken summary, and the value sits above each bar when there are few enough to read (a week of days, not thirty). The numbers come from a sixth lookup, `activity_over_time`, which exists for charts only and is not offered to the assistant; see `docs/ARCHITECTURE.md`.

## Screen states

`frontend/scripts/screenshots.mjs` takes each state at 375, 768 and 1280 in light and dark.

**Ask**: first visit; panel opened on a small screen; demo mode with no recorded answer; loading; answer with one number; with a comparison; with no number; two questions then another view; refusal; rate limit; daily budget; assistant unavailable; network failure; question at the limit.

**Dashboard**: Overview in each window; each of the four numbers chosen; Active people over 30 days; Reliability (7 days, today); backend unreachable; focus on the field, a suggestion and the window switch; panel closed; About; Everyone shown in full; a tool asking the assistant (live model only).

Built but not photographed: Reliability with no errors (the seeded data has errors in every window), and hover states.

## What I am unsure about

- **The floating "Ask a question" button** sits over the bottom right of the page below 1280 and can cover part of a chart until the page is scrolled.
- **Telling the two 429s apart** still depends on the word "budget" in the backend's message.
- **The hero number rule** ("first number that is not a date or a window") is a judgement the page cannot always make for comparisons.
- **The detector's notes.** `npx impeccable detect` raises two advisories on the Overview that are left as they are: the values printed above bars are measured against the bar's own colour, though they sit above it on the card; and the chart's grid lines are a repeating gradient, which it reads as decoration.
- **The explainer video** (`frontend/scripts/explainer.mjs`, `screenshots/explainer.mp4`) shows the previous design. It has not been remade.

## Process

Tokens live in one file (`frontend/src/app/tokens.css`); breakpoints stay inline because CSS cannot read a variable in a media query. The approved mocks are in `screenshots/mock/` (not tracked). Selected screenshots are in `docs/design/`.
