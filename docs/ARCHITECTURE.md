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

## Time

`AS_OF` is the last day of the seed, stored in `ground_truth.json` and loaded into settings. Windows are computed from it: `today` is that calendar day, `7d` and `30d` end on it, inclusive. Nothing reads the wall clock for data.

## The five lookups

```python
Window = Literal["today", "7d", "30d"]

usage_by_tool(window) -> list[ToolUsage]          # headline_count, active_people, errors
activity_by_person(window, user_id=None) -> list[PersonActivity]   # logins, outputs, last_seen
activity_by_client(window) -> list[ClientActivity]  # active_people, outputs
errors_seen(window, tool_id=None) -> list[ErrorGroup]   # source, tool, count, people_affected
roster(window) -> Roster                          # active, never_showed_up, went_quiet
```

Every lookup takes `with_previous: bool = False`. When true, each row also carries the same measure for the previous window of equal length and the difference. This is how "up or down, and by how much" gets answered without the model doing arithmetic.

Return types are frozen dataclasses or pydantic models. The same objects feed the API, the assistant's tool results and the ground-truth generator's checks.

## Registry

`TOOL_IDS` is a `Literal` of the eight tool ids. `HEADLINE: dict[ToolId, HeadlineEvent]` must be total over it; the type checker enforces that. One test adds a ninth tool to a copy of the catalog without a headline event and asserts that `mypy` fails on it.

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
