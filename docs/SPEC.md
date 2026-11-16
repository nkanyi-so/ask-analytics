# Spec: ask-analytics

The spec is final for the first draft. Do not run an interview or brainstorm step.

## Claim

One trusted number per tool, on a page leadership opens themselves, and a plain-English way to ask about it, where the assistant can only answer with numbers the page can derive.

## Honest paragraph (goes in the README as written)

A public rebuild of the usage observability I built for a client's internal platform. The platform here is synthetic: a seeded workspace of eight tools and forty people over sixty days of activity. Locally the analytics source can be real (Mixpanel); the hosted demo reads a file-backed source, so the public deployment needs no analytics keys and never breaks.

## The synthetic workspace

- **Eight tools**, each with one headline event (its "golden metric", fired on server-confirmed success): email drafter (`email_sent`), media plan builder (`plan_exported`), call agenda (`agenda_created`), invoice generator (`invoice_issued`), report summariser (`summary_saved`), contact enrichment (`contact_enriched`), meeting notes (`notes_filed`), proposal writer (`proposal_sent`).
- **Forty people** across **six client accounts**, with a role each (admin, manager, member).
- **Sixty days** of events ending on a fixed `AS_OF` date.
- **Patterns the seed must contain**, because the demo and the evals depend on them:
  - one tool nobody uses (zero headline events in 30 days)
  - one person who stopped logging in (active in days 1 to 25, nothing after)
  - three people who were invited and never logged in
  - one tool emitting errors (an error spike in the last 7 days, from one error source)
  - weekday and weekend rhythm, and uneven usage across clients
- The seed is deterministic: the same seed value produces byte-identical output.

## In scope: first draft (Phases 0 to 4)

1. **Seed generator** that writes events and a ground-truth file of expected answers.
2. **File event source** behind the `EventSource` interface, loaded into SQLite at startup.
3. **Five lookups**, each taking a window of `today`, `7d` or `30d`, and each able to return the previous window of the same length and the change next to it (so differences are computed by the backend, never by the model):
   - usage by tool (headline count, active people, errors)
   - activity by person (logins, outputs, last seen)
   - activity by client (active people, outputs)
   - errors seen (by source and tool, people affected)
   - roster (who is in, who never showed up, who went quiet)
4. **Typed headline registry** with a test proving that a tool without a headline event fails the type check.
5. **API** with admin-token auth, a health endpoint, and results cached for ten minutes.
6. **Assistant**: Anthropic tool use over the five lookups. It names the window it used, shows which lookup it called, and refuses questions no lookup covers while naming what it can answer.
7. **Eval set**: thirty questions with exact numeric answers computed from ground truth, ten questions that must be refused. Runs in fixture mode in `make check` and live in `make evals`.
8. **Dashboard**: Overview (people in the app, headline number per tool, activity by person and by client, window switch) and Reliability (errors by source, who was affected). An "Ask" box with three suggested questions. A visible "Data as of" line.

## In scope: second session (Phases 5 and 6)

- Mixpanel source (ingestion API to track, raw export API to read, one download per window).
- MCP server (stdio) exposing the same five lookups, with the Claude Desktop config in the README.
- Monday summary endpoint: last week next to the week before, as HTML. Sending is optional and off in the hosted demo.
- Docker, deploy (backend on Railway, frontend on Vercel), cache warm on a schedule.
- README on the seven-section spine, with the live eval table and its date.

## Out of scope

A real multi-tenant product. User management. Charts beyond stat tiles and one table per tab. Any real client's vocabulary or data. Visual polish beyond clean and readable (that is a later layer).

## Evals

- Thirty answerable questions in three tiers, scored by exact match on the number, three runs each for stability:
  - twelve direct ("how many invoices were issued in the last 7 days?")
  - ten indirect, where the wording does not name the lookup, the window or the filter ("who has gone quiet?", "which tool is nobody touching?")
  - eight comparisons against the previous window ("did email usage go up or down this week, and by how much?")
- Ten questions that must be refused, including three adversarial ones: a request to guess, a number just outside the data (day 61, a ninth tool), and an instruction hidden in the question to ignore the rules.
- No AI judge. Ground truth is derivable from the seed.
- Results are reported per tier. If the first live run scores 100% everywhere, the set is too easy: add harder questions until something fails, fix it, and keep the before and after in `docs/eval-results.md`. A table with a real failure and its fix is worth more than a perfect one.
- The README shows the table and the date it was run.

## Surviving production

- Cache with a ten-minute lifetime; one scheduled warm so the first visitor does not pay the cold read.
- Model calls: hard timeout, one retry with backoff, cost and latency logged per call.
- **Public-demo spend protection**: the Ask endpoint is rate limited per visitor and stops for the day at a fixed budget, returning a clear message.
- Secrets in the platform's environment only. Health endpoint.

## Done when (first draft)

`make check` exits 0. `make dev` shows the dashboard on seeded data. The assistant answers the three suggested questions correctly and refuses a fourth it cannot answer. `make evals` produces a results table. No key is in the repo.

## Done when (whole piece)

The hosted page loads with seeded data in under two seconds. The eval table is in the README with a date. CI is green on `main`. The Loom is recorded.
