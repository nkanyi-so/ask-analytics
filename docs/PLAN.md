# Plan: ask-analytics

This file is the single record of progress. Each phase lands as its own branch and pull request, with the phase's plan summary and gate evidence in the description, so the history shows how the work was reviewed. Each phase has a gate. A gate is ticked only when its evidence (the commands run and their real output) is written in the phase log. Never start a phase before the previous gate is ticked.

First draft = Phases 0 to 4. Second session = Phases 5 and 6.

---

## Phase 0: scaffold and process layer

- [x] Backend: uv project, FastAPI, ruff, mypy strict, pytest. Frontend: Next.js with TypeScript strict and ESLint.
- [x] `Makefile` with `setup`, `seed`, `dev`, `check`, `evals`.
- [x] Port the process layer from `../ytscribe` and adapt it to this repo (Python plus a frontend): `.claude/settings.json`, `.claude/agents/reviewer.md`, `.claude/hooks/`, `.claude/skills/next-phase/`, `.githooks/pre-commit`. Read those files, keep their structure, change only what is specific to ytscribe. List every change in the log.
- [x] `.gitignore`, `.env.example` (already in the kit) wired into `config.py`.
- [x] GitHub Actions workflow on every pull request and on `main`: lint, type check, tests, fixture evals (once they exist), gitleaks secret scan.
- [x] `docs/REFERENCES.md`: start from `../ytscribe/docs/REFERENCES.md`, keep what applies here, and add the current official docs for the Anthropic tool-use loop and the FastAPI project layout you follow. Name, link, and one line on what is borrowed from each.

**Gate:** `make check` exits 0 on an empty app with one passing test per side. The pre-commit hook refuses a commit when a test is made to fail (show it, then undo). The workflow file is valid and runs green on the first push.

**Log:**

16 Nov 2026. Branch `phase-0-scaffold`, pull request #1.

*Before the phase.* The kit docs were committed straight to `main` (`7daa266`) so the per-phase pull requests have a base. That is the only commit that does not go through a pull request.

*Process layer: every change from `../ytscribe`.*

| File | Change |
|---|---|
| `.claude/settings.json` | Allow list swapped to this repo's commands (`uv run mypy` for `pyright`, `npm run lint/typecheck`, `npm test`, `make setup/seed/check`). `make evals` is deliberately not allowed, so it always asks. The `git push` deny is dropped because every phase needs a push and a pull request; force-push denies are added. Hooks block unchanged. |
| `.claude/agents/reviewer.md` | Same structure and reporting rule. The ytscribe checks (adapters, yt-dlp, politeness) are replaced by this repo's architecture rules, security list and a "no live model in tests or CI" check. Default range is `git diff main...HEAD`. |
| `.claude/hooks/protect-files.sh` | Also blocks `package-lock.json`, `data/ground_truth.json` and `data/events.jsonl` (generated; change the seed instead). |
| `.claude/hooks/format-python.sh` | Looks for `backend/pyproject.toml` and runs ruff from `backend/`. |
| `.claude/skills/next-phase/SKILL.md` | Name swapped; step 4 reordered to match this repo's working loop (reviewer before the gate, then pull request and merge on green CI). |
| `.githooks/pre-commit` | Identical (`diff` prints nothing). Enabled with `git config core.hooksPath .githooks`. |
| `Makefile` | New targets for two sides. Type check is `mypy --strict` on `backend/app`, as CLAUDE.md says, not pyright. |
| `.github/workflows/ci.yml` | Runs on pull requests and on `main` only (ytscribe ran on every push, which doubles the runs on a pull request). Adds Node and a gitleaks job over the full history, installed from a release pinned by version and checksum. Actions pinned by commit. |

*Where the libraries differ from the docs.*

- Starlette's test client now warns against `httpx` and asks for `httpx2`; the dev dependency is `httpx2`.
- `create-next-app` 16.4.6 turns on `cacheComponents` and `partialPrefetching` and loads Google fonts at build time. All three are removed: pages read fresh numbers per request and the build needs no network.
- `next lint` no longer exists; lint is `eslint --max-warnings 0`.
- Vitest 5 needs Node 22. Pinned to major 4, which also runs on Node 20. Its config has to be `vitest.config.mts` on Node 20.
- ruff's hardcoded-password rules (S105, S106) are off for `tests/` only, because tests use obviously fake tokens. No rule is relaxed for `backend/app`.
- Dependencies and their reasons: `docs/decisions/0002-dependencies.md`.

*Gate evidence.*

`make check` on the empty app, at least one passing test per side (output after the review fixes):

```
$ make check
cd backend && uv run ruff format --check .
6 files already formatted
cd backend && uv run ruff check .
All checks passed!
cd backend && uv run mypy
Success: no issues found in 3 source files
cd backend && uv run pytest
.....                                                                    [100%]
5 passed in 0.19s
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm test
 Test Files  1 passed (1)
      Tests  3 passed (3)
$ echo $?
0
```

The pre-commit hook refuses a commit when a test is made to fail. `backend/tests/test_health.py` was changed to expect `{"status": "broken on purpose"}`:

```
$ git commit -a -m "should be refused"
E       AssertionError: assert {'status': 'ok'} == {'status': 'b...n on purpose'}
tests/test_health.py:12: AssertionError
FAILED tests/test_health.py::test_health_needs_no_token - AssertionError: ass...
1 failed, 3 passed in 0.17s
make: *** [check] Error 1
pre-commit: make check failed. Fix the cause before committing.
$ git log --oneline
7daa266 docs: project kit (spec, architecture, plan, first decision)
```

No commit was created. The test was restored and `make check` exits 0 again.

The workflow ran green on the first push of the branch (run 43836144271):

```
$ gh pr checks 1
check    pass  1m1s  https://github.com/nkanyi-so/ask-analytics/actions/runs/43836144271/job/133193134148
secrets  pass  6s    https://github.com/nkanyi-so/ask-analytics/actions/runs/43836144271/job/133193133860
```

Secret scan locally: `gitleaks git --redact .` reports `no leaks found`. `.env` exists locally with a generated `ADMIN_TOKEN`, is ignored (`git check-ignore -v .env` → `.gitignore:1:.env`) and is not in any commit.

*Review.* The `reviewer` agent file was not yet loaded as an agent type in the session that created it, so a general-purpose agent ran with that file as its brief, on `git diff main...HEAD`. One blocking finding, fixed in this phase:

- **Blocking: the hook-skipping flag could be used in its short form anywhere but first** (`git commit -m "x" -n` matched the allow rule and no deny rule). Deny rules added for `-n` alone, at the end and in the middle. Combined short flags such as `-nm` cannot be matched by a glob; for that form CI is the backstop, since it runs the same `make check`. The new rules were seen working: they refused a command of mine whose text merely contained the flag.

Non-blocking, fixed anyway: more force-push forms denied (`-f` mid-command, `+ref`); the edit hook now protects every `.env.*` except `.env.example`; `make setup` enables the pre-commit hook so a fresh clone has the gate; a test now checks that every backend name in `.env.example` is a setting; `.env.example` says to keep the token to letters and digits, because `make dev` reads the file as shell.

Carried forward: Phase 1 must lint and type-check `scripts/seed.py` (today `make check` only looks inside `backend/`). Phase 2's token check must reject an empty configured token.

Known and accepted: `make dev` keeps the other process running if one dies at startup. The edit hook does not guard `.githooks/` or `.claude/settings.json`, as in ytscribe.

**Gate: passed.**

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
