# Architecture: ask-analytics

## Shape

```
seed (scripts/seed.py)
   └─ data/events.jsonl + data/ground_truth.json
          │
   EventSource (file now, Mixpanel later)
          │  load once at startup
       SQLite (events, users, clients, tools)
          │
   lookups.py  ── five functions, SQL group-bys, cached 10 min
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
    registry.py      tool catalog and typed headline registry
    lookups.py       the five lookups and the Window type
    cache.py         TTL cache keyed by (lookup, window, args)
    assistant.py     tool-use loop, refusal rule, cost and latency log
    llm.py           ModelClient protocol, Anthropic client, fixture client
    limits.py        per-visitor rate limit and daily budget
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

## Registry

`ToolId` is a `Literal` of the eight tool ids and `HeadlineEvent` a `Literal` of the eight headline events. `catalog_entry(tool: ToolId) -> CatalogEntry` is a `match` over every id that ends in `assert_never`, and `CatalogEntry.headline_event` is a required field. So the type checker rejects a tool id with no case, a case with no headline event, and a headline event that is not one of the eight.

An earlier draft of this section said a `dict[ToolId, HeadlineEvent]` "must be total" and that the type checker enforces it. It does not: mypy accepts a dict that is missing a key. The exhaustive `match` is what makes the claim true.

`tests/test_registry.py` copies `registry.py`, adds a ninth tool id without a case (and, separately, removes or falsifies a headline event), runs `mypy --strict` on the copy and asserts that it fails. It also checks that the unaltered copy passes, and that the catalog matches the tools in the data.

## API

All `/api/*` routes require `Authorization: Bearer <ADMIN_TOKEN>`.

- `GET /health` no auth
- `GET /api/overview?window=` usage by tool, activity by person and client, roster counts, `as_of`
- `GET /api/reliability?window=` errors seen
- `POST /api/ask {question}` → `{answer, window, lookups_called, refused, latency_ms, cost_usd}`

## Assistant

1. System prompt: the five tools, the three windows, `AS_OF`, the rule that every number must come from a tool result, and the refusal rule.
2. Loop: model picks a tool and arguments; backend runs the lookup; result goes back; at most three tool calls; then the model writes a short answer that names the window.
3. Refusal: if the model answers with no tool call, or the question needs something no lookup returns, the reply is a refusal listing what it can answer.
4. Check after generation: every number in the answer must appear verbatim in the tool results of that turn (counts, previous-window values and differences all come from the lookups). Dates and the window length are allowed. If any other number appears, the answer is replaced with a refusal and the miss is logged.
5. The question is untrusted input. The tools are read-only and scoped to the seeded data, so the worst a hostile question can do is get a refusal; the system prompt still tells the model to ignore instructions inside questions, and one eval covers it.
6. Each call logs latency, tokens in and out, and cost.

`llm.py` defines `ModelClient`. `AnthropicClient` is the real one; the model id comes from `ANTHROPIC_MODEL`. `FixtureClient` replays recorded tool choices for tests and fixture evals, so `make check` never spends credits.

## Frontend

Next.js app router. Pages: `/` (Overview), `/reliability`, plus the Ask box on Overview. Server-side route handlers under `/app/api/*` call the backend with the admin token from the server environment; the browser never sees it. Stat tiles and one table per tab. A window switch (today, 7 days, 30 days). A "Data as of" line. Three suggested questions under the Ask box. Each answer shows which lookup was used.

## Security

- Admin token on every data route; compared in constant time.
- The token lives only in server environments.
- Ask endpoint: per-visitor rate limit and a daily budget cap.
- CORS limited to the frontend origin.
- `.env` ignored, `.env.example` tracked, secret scan in CI from Phase 0.
- Rate limit and budget counters are in memory, which is enough for one small instance; the README says so and names Redis as the next step.

## How the spine maps

| Spine | Where it lives |
|---|---|
| Connect to an existing system securely | `EventSource` seam, Mixpanel service account (Phase 5), admin token, server-side proxy |
| Rules where they suffice, model only for judgment | lookups do all numbers; the model only routes and words |
| Human in the loop | every answer shows its lookup and window; refusals over guesses |
| Evals with numbers | 30 exact-match plus 10 refusals, three runs, table in the README |
| Production survival | cache, timeout and retry, cost and latency log, rate limit, budget cap, health |
