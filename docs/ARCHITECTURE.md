# Architecture: ask-analytics

## Shape

```
seed (scripts/seed.py)
   └─ data/events.jsonl + data/ground_truth.json
          │
   EventSource (file by default, Mixpanel locally)
          │  load once at startup
       SQLite (events, users, clients, tools)
          │
   lookups.py  ── five lookups + one chart series, SQL group-bys, cached 10 min
      │                    │
  API routes           assistant (Anthropic tool use)
      │                    │
  Next.js server-side route handlers (hold the admin token)
      │
  Dashboard: Overview, Reliability, Ask
```

## Layout

```
backend/
  app/
    main.py          FastAPI app, routes, auth dependency
    config.py        settings from env (pydantic-settings)
    db.py            SQLite engine, schema, load from an EventSource
    sources/
      base.py        EventSource protocol
      file.py        reads data/events.jsonl
      mixpanel.py    import API to write, raw export API to read
      mixpanel_push.py  `make mixpanel-push`: sends the seeded workspace
    registry.py      tool catalog and typed headline registry
    lookups.py       the five lookups, the chart series and the Window type
    cache.py         TTL cache keyed by (lookup, window, args)
    assistant.py     tool-use loop, refusal rule, cost and latency log
    llm.py           ModelClient protocol, Anthropic client, fixture client
    limits.py        per-visitor rate limit and daily budget
    mcp_server.py    the five lookups as an MCP server over stdio
    summary.py       the Monday summary as HTML
  tests/
  evals/
    questions.json   generated from ground truth (30 answerable, 10 refusals)
    run.py           fixture mode and live mode, writes docs/eval-results.md
scripts/seed.py
data/                generated; events.jsonl and ground_truth.json are tracked
frontend/            Next.js, TypeScript strict, app router
docs/
```

## Data model (SQLite, SQLAlchemy Core)

- `clients(id, name)`
- `users(id, name, client_id, role, invited_at)`
- `tools(id, name, headline_event)`
- `events(id, ts, user_id, client_id, tool_id NULL, name, error_source NULL)`
  - `name` is one of: `login`, `tool_opened`, a tool's headline event, `error`
  - indexes on `ts`, `(tool_id, name)`, `user_id`

SQL is written to be portable to Postgres. See `docs/decisions/0001-sqlite-for-the-demo.md`.

### The data file

`data/events.jsonl` is one JSON object per line, each with a `kind`: one `meta` line (`as_of`, `seed`, `days`), then `client`, `tool`, `user` and `event` lines. People who never logged in have no events, so the roster has to travel with the events; this is how. An `EventSource` returns all of it as one `Workspace` (clients, tools, users, events, `as_of`).

### The Mixpanel source

Chosen with `EVENT_SOURCE=mixpanel`; meant for local use, never the hosted demo. `make mixpanel-push` sends the seeded workspace through the import API, and the source reads it back through the raw export API. Both use a service account (basic auth, plus `project_id`).

- **One download per load.** SPEC says "one download per window". Here every window is answered from one in-memory database, so a load is a single export request covering the 30-day window and the 30 days before it. No lookup ever triggers a download, and the export API's limit of 60 queries an hour is never a concern.
- **The roster travels as events.** People who never logged in have no events, and the lookups need clients and tools too. They are sent as `workspace_user`, `workspace_client`, `workspace_tool` and `workspace_meta` events, so one export returns the whole `Workspace`.
- **The export can hold duplicates.** Mixpanel says so. Every record has a stable `$insert_id`, which makes a repeated push harmless, and the source drops duplicates by the event's own id.
- **Timezones.** Projects created before 2023 shift `time` and the export's date range into the project's timezone. So each event carries its own timestamp as a property, which is what is read back, and the date range is padded by a day on each side.
- **`MIXPANEL_AS_OF`.** The export needs a date range before anything is read, so the day the data runs to is a setting. The data carries it too (`workspace_meta`), and a mismatch stops the load.
- **Dates come back changed.** A property that is just a date (`2026-07-01`) is returned as a date-time (`2026-07-01T00:00:00`). Dates are read in either form.
- **The first export after an import is slow.** It took almost two minutes once, then seconds. A load right after a first push can hit the deadline; wait a few minutes.
- **Failure.** 429, 502, 503 and dropped connections are retried twice, after 2 and 4 seconds, as Mixpanel asks. A 400 or 401 is not retried. A load has 60 seconds in total, retries and waits included: no single wait is allowed to outlast what is left, and once the time is up the load stops and is not retried. An event with one of our names that we did not send stops the load, so use a project that holds nothing else.

## Time

`AS_OF` is the last day of the seed. The source provides it (the `meta` line for the file source) and `ground_truth.json` repeats it; the app reads it from the source, never from the ground-truth file, which exists only to check answers. Windows are computed from it: `today` is that calendar day, `7d` and `30d` end on it, inclusive. Nothing reads the wall clock for data. `AS_OF` is a weekday so that `today` is not an empty weekend.

## Definitions

These are the meanings behind every number. The lookups and the ground-truth generator implement them separately and must agree.

- **Window**: `today` is `AS_OF`; `7d` is the 7 calendar days ending on `AS_OF`; `30d` is the 30 ending on `AS_OF`. Days run midnight to midnight in the workspace's own clock.
- **Previous window**: the same number of days immediately before the window. For `30d` that is days 1 to 30 of the seed, so sixty days are exactly enough.
- **Change**: current minus previous, as a whole number. No percentages, so no number the backend did not count ever reaches the model.
- **Output**: one headline event. **Headline count** of a tool: its headline events in the window.
- **Active person** (in a window): at least one `login` in it.
- **Active people of a tool**: distinct people with any event on that tool in the window (opened, headline or error).
- **Errors of a tool**: `error` events on that tool in the window.
- **Last seen**: the date of a person's most recent `login` on or before `AS_OF`, whatever the window. Empty if they never logged in.
- **Never showed up**: invited, and no `login` up to `AS_OF`. The same people in every window.
- **Went quiet** (in a window): logged in before the window started, and not once inside it. It needs history before the window, so its previous value and change are empty when no data precedes the previous window. That is the case for `30d`, whose previous window starts on day 1. Every other measure has a previous value in every window.
- **Error group**: errors sharing a source and a tool. **People affected**: distinct people in the group; `affected` lists their names in alphabetical order.

## The five lookups

```python
Window = Literal["today", "7d", "30d"]

usage_by_tool(window) -> list[ToolUsage]          # headline_count, active_people, errors
activity_by_person(window, user_id=None) -> list[PersonActivity]   # logins, outputs, last_seen
activity_by_client(window) -> list[ClientActivity]  # active_people, outputs
errors_seen(window, tool_id=None) -> list[ErrorGroup]   # source, tool, count, people_affected, affected
roster(window) -> Roster                          # active, never_showed_up, went_quiet
```

Every lookup takes `with_previous: bool = False`. When true, each row also carries the same measure for the previous window of equal length and the difference (`<measure>_previous`, `<measure>_change`). This is how "up or down, and by how much" gets answered without the model doing arithmetic.

Rows are complete and ordered: every tool, person and client appears even at zero, sorted by id. Error groups are sorted by count, largest first, then by source, then by tool id. Without `with_previous` only groups with errors in the window appear; with it, a group that only had errors in the previous window also appears, at zero. The roster carries its own counts next to its lists, so nothing downstream ever counts.

Return types are frozen dataclasses or pydantic models. The same objects feed the API, the assistant's tool results and the ground-truth generator's checks.

### The chart series

```python
activity_over_time(window) -> ActivityOverTime   # unit, buckets, outputs and errors with previous and change
```

A sixth function in the same file, added for the dashboard's charts. It returns the window cut into buckets (one per hour for `today`, one per day otherwise), and for each bucket the active people, outputs, errors and outputs per tool. It also carries the window's total outputs and errors with the previous window and the change, which the dashboard shows as two of its key numbers.

It is **not an assistant tool** and is not served over MCP: it is absent from `TOOL_SPECS`, so the model cannot call it and the eval set does not cover it. It is checked the same way as the others: `scripts/seed.py` writes the expected series to `data/ground_truth.json` (under `series`) with code that shares nothing with `lookups.py`, and the tests require the lookup to equal it in every window and to add up to the other lookups. `/api/overview` and `/api/reliability` return it as `trend`.

The frontend draws a bar's height from a bucket's value and the chart's largest value. That ratio positions a shape and is never shown as a number, so rule 1 (no aggregation outside the lookups) holds.

### Cache and the scheduled warm

Results are cached for ten minutes, keyed by lookup, window and arguments. The backend warms the cache at startup and again every five minutes, in its own process: it recomputes the eighteen results the dashboard and the summary ask for (five lookups with the previous window, and the chart series, in three windows) and stores them fresh, replacing entries before they expire. So no visitor pays for a cold read, and no platform scheduler is involved. A warm that fails is logged and the next one still runs. Questions that ask for something else (one person, one tool's errors) are computed on first use and cached as before.

## Registry

`ToolId` is a `Literal` of the eight tool ids and `HeadlineEvent` a `Literal` of the eight headline events. `catalog_entry(tool: ToolId) -> CatalogEntry` is a `match` over every id that ends in `assert_never`, and `CatalogEntry.headline_event` is a required field. So the type checker rejects a tool id with no case, a case with no headline event, and a headline event that is not one of the eight.

An earlier draft of this section said a `dict[ToolId, HeadlineEvent]` "must be total" and that the type checker enforces it. It does not: mypy accepts a dict that is missing a key. The exhaustive `match` is what makes the claim true.

`tests/test_registry.py` copies `registry.py`, adds a ninth tool id without a case (and, separately, removes or falsifies a headline event), runs `mypy --strict` on the copy and asserts that it fails. It also checks that the unaltered copy passes, and that the catalog matches the tools in the data.

## API

All `/api/*` routes require `Authorization: Bearer <ADMIN_TOKEN>`.

- `GET /health` no auth
- `GET /api/overview?window=` usage by tool, activity by person and client, roster counts, `as_of`
- `GET /api/reliability?window=` errors seen
- `POST /api/ask {question}` → `{answer, window, lookups_called, refused, latency_ms, cost_usd, demo_mode}`
- `GET /api/summary` the Monday summary as HTML: the `7d` window next to the 7 days before, every number a field of a lookup result. Nothing sends it; sending is optional in SPEC and is not built.

## MCP server

`python -m app.mcp_server` serves the five lookups over stdio, using the assistant's own tool definitions and argument check (`TOOL_SPECS`, `run_lookup`), so the two cannot drift apart. It has no token, because a stdio server is a local child process of its client. It does not apply the assistant's number check: the client's model words its own answers. Setup for Claude Desktop is in `docs/mcp.md`.

## Assistant

1. System prompt: the eight tools in the workspace and what each one counts (from the registry), the five lookups, the three windows, `AS_OF`, the rule that every number must come from a tool result, and the refusal rule.
2. Loop: model picks a tool and arguments; backend runs the lookup; result goes back; at most three tool calls; then the model writes a short answer that names the window.
3. Refusal: if the model answers with no tool call, or the question needs something no lookup returns, the reply is a refusal listing what it can answer.
4. Check after generation: every number in the answer must appear verbatim in the tool results of that turn (counts, previous-window values and differences all come from the lookups). Dates that appear in the results and the window length are allowed; the exact rule is under "What the API allows" below. If any other number appears, the answer is replaced with a refusal and the miss is logged.
5. The question is untrusted input. The tools are read-only and scoped to the seeded data, so the worst a hostile question can do is get a refusal; the system prompt still tells the model to ignore instructions inside questions, and one eval covers it.
6. Each call logs latency, tokens in and out, and cost.

`llm.py` defines `ModelClient`. `AnthropicClient` is the real one; the model id comes from `ANTHROPIC_MODEL` (default `claude-haiku-5-5`). Cost comes from a small price table keyed by model id; a model id that is not in the table fails at startup, because a budget cap over an unpriced model is no cap. The hard timeout and the single retry are the SDK's own settings (`timeout=30`, `max_retries=1`).

`FixtureClient` plays the model's part for tests and fixture evals, so `make check` never spends credits. Its script for each question is generated from the eval set: which lookup to call with which arguments, and which field of the result to put in the answer. The number in a fixture answer therefore still comes from the real lookup. Fixture evals prove the lookups, the loop, the number check and the scorer end to end. They say nothing about whether a model picks the right lookup; only a live run does.

### What the API allows, and what follows from it

- Current models reject a forced tool choice, so "the model must call a tool" is asked for in the prompt and enforced by rule 3 above: an answer with no tool call is replaced by the refusal.
- Sampling parameters such as temperature are rejected too. There is no determinism knob; running each eval question three times is the only stability check.
- A reply can stop with `stop_reason: "refusal"`. That is treated as a refusal like any other.
- The model is told to answer with the single word `REFUSE` when no lookup covers the question. The refusal text itself is fixed in code, so a hostile question cannot shape it.
- The number check: every number in the answer must be a number in a tool result of that turn (the sign aside). Digits are also allowed inside a date or an id that appears in the results, and in a window phrase such as "the last 7 days". A count that merely matches part of an id or a date is rejected, and so is any decimal, since lookups return counts. Numbers written as words ("three", "twenty-two", "forty") are held to the same rule, because the live model writes "Three people" whatever the prompt says; "hundred" and larger are never accepted. Once an answer has passed, its number words are rewritten as digits before it is returned. A window's days may be written as one span ("17 to 23 October 2026"), but only for the first and last day the result itself gives for that window or the one before it; any other pair of dates is not a span, because in a list of people "28 - 30 October" is where an invented count would sit. A window may be named without its unit only as the thing compared with ("compared with the previous 30"), and only for a window that turn compared; "up from the previous 7" stays a count, because that is where an invented previous value would sit. Limits that are known and accepted: a count that happens to equal a window's first day, written straight before its last day ("rose from 17 to 23 October" when the previous window is the 17th to the 23rd), reads as that span; the word "one" passes unchecked, since "no one" and "the one tool" are not counts; an ordinary "two" or "three" ("the two windows") can turn a good answer into a refusal if that number is in no result; and so can a harmless count the model adds by itself ("the top 3").

### Demo mode

With no `ANTHROPIC_API_KEY` the backend runs the `FixtureClient`. Every `/api/ask` reply then carries `demo_mode: true`, questions from the eval set get their recorded answer, and any other question gets a plain "the live model is not connected" reply. The Ask box shows a visible "Demo mode" label. Demo mode must never be on in a deployed build. The Docker image sets `DEPLOYED=1`, and Railway sets `RAILWAY_ENVIRONMENT_NAME` in every container; with either, the app refuses to start without `ANTHROPIC_API_KEY`, without an admin token of at least 32 characters, or with any source but the file (`check_deployable` in `main.py`).

## Frontend

Next.js app router. Three views, `/` (Overview), `/reliability` and `/about`, inside one frame (`components/Shell.tsx`) that the root layout mounts once: a sidebar, a page header with the window switch (today, 7 days, 30 days) and the light/dark toggle, tabs, the current view, and the assistant (`components/AskPanel.tsx`) as a panel beside it. Because the frame is not rebuilt when the view changes, the assistant keeps its questions and answers across views. It is docked and open where the screen is 1280 wide or more; below that it opens over the page as a dialog, with the page behind it inert. Overview is four key numbers, each a button that opens the chart and tables behind it (`components/Dashboard.tsx`), then a sortable table of everyone; Reliability is the errors chart and a table of where they came from. Charts are plain elements sized from the `trend` field (`components/BarChart.tsx`). Server components and the route handlers under `/app/api/*` call the backend with the admin token from the server environment; the browser never sees it. The layout itself asks the backend one thing, whether this is demo mode, and passes only that boolean to the frame.

The assistant is a list of separate questions, not a conversation: the backend answers each one with no memory of the last, and the panel says so.

There is a third view, `/about`, which is prose: the problem, the method, the eval results and a link to the source. Its eval figures are copied by hand into `frontend/src/lib/about.ts` from `docs/eval-results.md`, because no endpoint serves them.

With a live model, each tool's name in an Overview table is a button that hands the assistant a question ("How is the Invoice generator doing in the last 7 days?") through a small context the frame provides (`components/ask-context.tsx`). The question is sent like any typed one, through the same route, rate limit and budget. The look, the tokens and every screen state are in `docs/DESIGN.md`; all tokens live in `frontend/src/app/tokens.css`.

### The working under an answer

An answer is shown with its working: which lookup ran, what it returned, and that it was checked. The API does not send lookup results with an answer, so the page reads the lookup again through `GET /api/evidence`, a route on the frontend's own server that calls the existing `/api/overview` or `/api/reliability` with the token. It returns titled rows of figures and nothing else: no ids, and previous-window values only when the model asked for the comparison. Those previous values are the one thing it serves that the tables do not print (they show the change). `lib/evidence.ts` shapes the rows on the server and, in the browser, picks the ones the answer rests on; `lib/answer.ts` finds the numbers in the answer text. Both select and word; neither adds, counts or compares, so rule 1 holds. "Checked" on the page describes the backend's number check; the page does not re-run it. It marks a number in the answer only when the number is in a row shown and the answer uses that measure's words, and otherwise shows the row unmarked.

Two things the panel can only tell from the backend's wording, because the API has no field for them: which of the two 429s it got (the word "budget"), and a demo-mode question with no recording (the reply starts "Demo mode"). `backend/tests/test_frontend_wording.py` fails if either wording changes.

## Security

- Admin token on every data route; compared in constant time.
- The token lives only in server environments.
- Ask endpoint: per-visitor rate limit and a daily budget cap. The browser only ever talks to the frontend's server, so the backend sees one caller. The frontend's route handler therefore sends the visitor's address in `X-Visitor-Address`, and the backend uses it as the rate-limit key, grouping IPv6 by /64. It is a header of our own because proxies between the two rewrite `X-Forwarded-For`. It can be trusted only because the route requires the admin token: a caller without the token never gets that far. The frontend believes an address only on a platform that sets `x-real-ip` itself and overwrites the browser's value (Vercel). Anywhere else, including `make dev`, every visitor shares one key, which is stricter, never looser.
- The Ask route on the frontend has no cookie or session, so another site cannot read anything through it. It could still make its visitors' browsers ask questions and drain the budget, so the route turns away requests that are not JSON (which forces a preflight that fails), that a browser marks as coming from another site, or that are larger than a question can be.
- The budget is reserved, not just checked. Before the model is called, a question reserves its worst-case cost (five model calls, each with a large input and the full output allowance); afterwards it settles to what the calls really cost. So a burst of questions cannot pass the check together and overshoot the limit. Cost is recorded per model call, and a call that fails or times out is charged as a worst-case call, since it may still be billed. The price of this safety is that the endpoint stops one worst-case question short of the limit: about $0.02 on `claude-haiku-5-5` and about $0.71 on `claude-opus-5-5`, so a $2 budget is too small to say much with Opus.
- The admin token keeps strangers off the backend. It does not protect the public demo's spend: anyone who opens the page can ask through the frontend. The rate limit and the daily budget are what stand between a visitor and the API bill.
- CORS limited to the frontend origin.
- `.env` ignored, `.env.example` tracked, secret scan in CI from Phase 0.
- Rate limit and budget counters are in memory, which is enough for one small instance; the README says so and names Redis as the next step.

## How the spine maps

| Spine | Where it lives |
|---|---|
| Connect to an existing system securely | `EventSource` seam, Mixpanel service account, MCP server, admin token, server-side proxy |
| Rules where they suffice, model only for judgment | lookups do all numbers; the model only routes and words |
| Human in the loop | every answer shows its lookup and window; refusals over guesses |
| Evals with numbers | 30 exact-match plus 10 refusals, three runs, table in the README |
| Production survival | cache, timeout and retry, cost and latency log, rate limit, budget cap, health |
