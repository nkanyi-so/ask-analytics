# Plan: ask-analytics

This file is the single record of progress. Each phase lands as its own branch and pull request, with the phase's plan summary and gate evidence in the description, so the history shows how the work was reviewed. Each phase has a gate. A gate is ticked only when its evidence (the commands run and their real output) is written in the phase log. Never start a phase before the previous gate is ticked.

First draft = Phases 0 to 4. Second session = Phases 5 and 6.

---

## Phase 0: scaffold and process layer

- [ ] Backend: uv project, FastAPI, ruff, mypy strict, pytest. Frontend: Next.js with TypeScript strict and ESLint.
- [ ] `Makefile` with `setup`, `seed`, `dev`, `check`, `evals`.
- [ ] Port the process layer from `../ytscribe` and adapt it to this repo (Python plus a frontend): `.claude/settings.json`, `.claude/agents/reviewer.md`, `.claude/hooks/`, `.claude/skills/next-phase/`, `.githooks/pre-commit`. Read those files, keep their structure, change only what is specific to ytscribe. List every change in the log.
- [ ] `.gitignore`, `.env.example` (already in the kit) wired into `config.py`.
- [ ] GitHub Actions workflow on every pull request and on `main`: lint, type check, tests, fixture evals (once they exist), gitleaks secret scan.
- [ ] `docs/REFERENCES.md`: start from `../ytscribe/docs/REFERENCES.md`, keep what applies here, and add the current official docs for the Anthropic tool-use loop and the FastAPI project layout you follow. Name, link, and one line on what is borrowed from each.

**Gate:** `make check` exits 0 on an empty app with one passing test per side. The pre-commit hook refuses a commit when a test is made to fail (show it, then undo). The workflow file is valid and runs green on the first push.

**Log:**

---

## Phase 1: seed and source

- [ ] `scripts/seed.py`: deterministic generator for clients, users, tools and sixty days of events, containing every pattern listed in `docs/SPEC.md`.
- [ ] `data/ground_truth.json`: `as_of`, the seed value, and expected results for every lookup in every window, computed independently of `lookups.py` (plain Python over the events, no SQL).
- [ ] `EventSource` protocol and the file source. `db.py` loads a source into SQLite at startup.
- [ ] Tests: same seed gives byte-identical output; each required pattern is present.

**Gate:** `make seed` twice gives identical checksums. Pattern tests pass. `make check` exits 0.

**Log:**

---

## Phase 2: lookups, registry, API

- [ ] The five lookups as SQL group-bys, with the `Window` type, pinned time and `with_previous`.
- [ ] Tests: every lookup, every window, equals ground truth exactly.
- [ ] Typed headline registry and the test proving a tool without a headline event fails `mypy`.
- [ ] TTL cache. API routes with the admin-token dependency. Health endpoint.
- [ ] Tests: 401 without the token; cached call does not hit the database twice.

**Gate:** all lookup tests equal ground truth. The registry failure test passes. `curl` output for `/health`, `/api/overview?window=7d` with and without the token is in the log.

**Log:**

---

## Phase 3: assistant and evals

- [ ] `ModelClient`, `AnthropicClient`, `FixtureClient`.
- [ ] Tool-use loop over the five lookups, the refusal rule, and the after-generation number check.
- [ ] Cost and latency logging. Rate limit and daily budget on `/api/ask`.
- [ ] `evals/questions.json` generated from ground truth: thirty answerable in three tiers, ten refusals including three adversarial (see `docs/SPEC.md`). Results reported per tier. `evals/run.py` with fixture and live modes, writing `docs/eval-results.md`.
- [ ] Tests (fixture client): a correct answer, a refusal, a made-up number replaced by a refusal, the rate limit, the budget cap.

**Gate:** fixture evals run inside `make check` and pass. One live run of `make evals` is done only if `ANTHROPIC_API_KEY` is set and the human has said yes; its table goes in the log. If there is no key, say so and leave the live run unticked.

**Log:**

---

## Phase 4: dashboard

- [ ] Overview and Reliability pages, window switch, "Data as of" line.
- [ ] Ask box with three suggested questions; each answer shows the lookup and window used.
- [ ] Server-side route handlers holding the admin token. No token in any client bundle (grep the build output and show it).
- [ ] Clean and readable only. No visual polish pass.

**Gate:** `make dev` serves the page on seeded data. Screenshots or text dumps of both pages are in the log. The three suggested questions answer correctly and a fourth, unanswerable one is refused. `make check` exits 0.

**Log:**

---

## Phase 5: real source, MCP, summary (second session)

- [ ] Mixpanel source: track via ingestion, read via raw export with a service account, one download per window, retry with backoff and a hard timeout.
- [ ] MCP server (stdio) exposing the five lookups; Claude Desktop config in the README.
- [ ] Monday summary endpoint.

**Gate:** with Mixpanel keys set locally, lookups over the Mixpanel source equal ground truth. An MCP client lists five tools and one call returns the same result as the API.

**Log:**

---

## Phase 6: CI, deploy, README (second session)

- [ ] `main` protected; CI (in place since Phase 0) required to pass before merge.
- [ ] Docker. Backend on Railway, frontend on Vercel. Scheduled cache warm.
- [ ] README on the seven-section spine from `job-search/portfolio/README.md`, with the live eval table and its date.

**Gate:** hosted page loads in under two seconds. CI is green on `main`. No key in the repo or its history.

**Log:**
