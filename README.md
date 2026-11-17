# ask-analytics

One trusted number per tool, on a page leadership opens themselves, and a plain-English way to ask about it, where the assistant can only answer with numbers the page can derive.

A public rebuild of the usage observability I built for a client's internal platform. The platform here is synthetic: a seeded workspace of eight tools and forty people over sixty days of activity. Locally the analytics source can be real (Mixpanel); the hosted demo reads a file-backed source, so the public deployment needs no analytics keys and never breaks.

> **Status, 17 Nov 2026.** Live at https://ask-analytics-five.vercel.app (frontend on Vercel, backend on Railway). The live eval has been run on `claude-haiku-5-5` (not yet on `claude-opus-5-5`). The Mixpanel source has been run against a real Mixpanel project: all five lookups in every window equal ground truth.

## Run it

```
cp .env.example .env      # then set ADMIN_TOKEN to any long random string
make setup
make dev                  # backend on :8000, frontend on :3000
```

Open http://localhost:3000. With no `ANTHROPIC_API_KEY` the Ask box runs in demo mode: it is labelled as such, answers the questions in the eval set (the three suggested ones among them) from recorded answers, and says the live model is not connected for anything else. `make check` runs what CI's `check` job runs; CI also builds the Docker image and scans the git history for secrets.

## Before

<!-- DRAFT: written from the project notes, not from memory of the client. Rewrite in your own words. -->

"Who is actually using what?" had no single answer. Usage lived in an analytics tool that leadership did not open, every tool counted success differently, and a question such as "did the invoice tool get used this week?" meant asking an engineer to run a query. People who were invited and never logged in did not appear anywhere, because a person with no events is invisible to an event store.

## Decisions

**1. Where rules end and the model begins.** Every number comes from a lookup function (`backend/app/lookups.py`): SQL group-bys over the events. The assistant can call five of them; a sixth feeds the dashboard's charts only. The model never does arithmetic and never sees a raw event. It picks a lookup and a window, gets the result, and words the answer. "Up or down, and by how much" is answered by the lookup returning the previous window and the change, so the model has nothing to subtract. After the model replies, code checks that every number in the answer is a number in a lookup result from that turn; if not, the answer is replaced with a refusal.

**2. Where the human sits.** Every answer shows which lookup and which window it used, so a reader can check it against the page. A question no lookup covers gets a fixed refusal that names what can be answered. A refusal is treated as a correct result, and the eval set scores it as one.

**3. Data and tools.**

- *One headline event per tool, in a typed registry.* Each tool has a single success event that counts as its number. Adding a tool without one fails the type check, and a test proves that by running the type checker on an altered copy.
- *Sources behind one interface.* `EventSource` has a file implementation and a Mixpanel one. Nothing outside `backend/app/sources/` knows which is in use. The roster travels with the events, which is how people with no activity stay visible.
- *SQLite in memory.* The whole workspace is nine thousand events, loaded once at startup. The SQL is written to move to Postgres unchanged (`docs/decisions/0001-sqlite-for-the-demo.md`).
- *Anthropic tool use, called directly.* One loop, five tools, no framework: there is nothing to orchestrate. The default model is `claude-haiku-5-5`, because the task is routing and wording.
- *Time is pinned.* "Today" is the last day of the seed, never the wall clock. That is what makes exact-match evals possible.
- *The same five lookups over MCP.* `docs/mcp.md` has the Claude Desktop config. The server reuses the assistant's tool definitions, so the two cannot drift.

## Evals

Forty questions: twelve direct, ten indirect (the wording names no lookup, window or filter), eight comparisons against the previous window, and ten that must be refused, three of them adversarial. Every expected answer is computed from the seed by plain Python that shares no code with the lookups. Scoring is exact match on the number. There is no AI judge.

| Mode | Model | Date | Direct | Indirect | Comparison | Refusal |
|---|---|---|---|---|---|---|
| Fixture | none | 16 Nov 2026 | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 |
| Live, first run | `claude-haiku-5-5` | 16 Nov 2026 | 8 of 12 | 9 of 10 | 1 of 8 | 10 of 10 |
| Live, latest run | `claude-haiku-5-5` | 17 Nov 2026 | 12 of 12 | 10 of 10 | 8 of 8 | 10 of 10 |
| Live | `claude-opus-5-5` | not run yet | | | | |

Read the fixture row for what it is. The fixture client plays the model from a script, so it proves the lookups, the loop, the number check and the scorer. It says nothing about whether a model picks the right lookup. The live rows do. A live run asks every question three times, and a question passes only if all three runs pass.

The first live run scored 70%. Getting to 100% took four rounds of fixes, and the failures were the useful part: the number check caught the model counting rows by itself; the model refused "how many emails were sent" because the prompt never said which tools exist; and telling it to write digits did not stop it writing "Three people", so the number check now reads number words too. A review of those fixes then found two that had loosened a check too far, which were tightened before the last run. The last run is partly fitted to these forty questions, since they are what the fixes were tested on. Every run, failure and fix is in `docs/eval-results.md`.

How a change is gated: fixture evals run inside `make check`, on every commit and every pull request, and must score 40 of 40. Details and known weak spots are in `docs/eval-results.md`.

## Surviving production

- **Cache.** Lookup results are cached for ten minutes. The cache is warmed at startup and every five minutes after, so no visitor pays for a cold read.
- **Model calls.** A 30-second timeout and one retry. Latency, tokens and cost are logged per call.
- **Spend.** The Ask endpoint is limited per visitor and stops for the day at a fixed budget. A question reserves its worst-case cost before the model is called, so a burst cannot overshoot. The admin token does not protect spend: anyone who opens the page can ask. The rate limit and the budget do.
- **Mixpanel.** Checked against a real project, not only a fake. One export request per load, retried with backoff on the statuses Mixpanel says to retry, inside one 60-second deadline. A repeated push is harmless because every record has a stable id.
- **Secrets and auth.** The admin token lives only on the two servers. Pages are rendered on the server and the Ask box talks to a route handler, so the token never reaches a browser; importing the module that reads it from client code fails the build. CI scans the whole git history for secrets.
- **A deployed build cannot pretend.** The Docker image refuses to start in demo mode, without a real admin token, or on any source but the file.
- **Known limit.** Rate-limit and budget counters are in memory, which fits one small instance. Redis is the next step.

## How this was built

AI-assisted, with Claude Code, under gates I set and checked: a plan reviewed before any code; tests first on the core logic (seed, lookups, registry, refusals); `make check` before every commit; CI and a secret scan on every pull request; a separate review of each phase's diff; one pull request per phase, with its evidence in `docs/PLAN.md`. The reviews found real bugs, and the log says which.

## What I'd do next

- Write a second set of questions that is never used for tuning, and run both models on it. The current forty were used to fix the failures they found.
- Deploy (`docs/deploy.md`), then check the visitor-address handling on the real platforms.
- Move the rate limit and budget to Redis.
- Send the Monday summary by email. Today the endpoint only renders it.
