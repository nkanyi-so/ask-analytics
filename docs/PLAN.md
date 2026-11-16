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

- [x] `scripts/seed.py`: deterministic generator for clients, users, tools and sixty days of events, containing every pattern listed in `docs/SPEC.md`.
- [x] `data/ground_truth.json`: `as_of`, the seed value, and expected results for every lookup in every window, computed independently of `lookups.py` (plain Python over the events, no SQL).
- [x] `EventSource` protocol and the file source. `db.py` loads a source into SQLite at startup.
- [x] Tests: same seed gives byte-identical output; each required pattern is present.

**Gate:** `make seed` twice gives identical checksums. Pattern tests pass. `make check` exits 0.

**Log:**

16 Nov 2026. Branch `phase-1-seed`, pull request #2.

*What was built.* `scripts/seed.py` (generator and ground truth, standard library only), `backend/app/sources/` (the `EventSource` protocol, the file source, and `build_source`, the only place that knows which source is in use), `backend/app/db.py` (schema, indexes, one load into in-memory SQLite at startup). The workspace: 6 clients, 40 people, 8 tools, 9,039 events from 1 Sep to 30 Oct 2026. `AS_OF` is Friday 30 Oct 2026. `data/events.jsonl` is 1.4 MB.

*Docs changed first.* `docs/ARCHITECTURE.md` gained "The data file" and "Definitions". The definitions are the ones agreed in the plan; the lookups (Phase 2) and the ground truth implement them separately. Two things differ from the original text and are now written down: the roster travels in the data file as `client`, `tool` and `user` lines, because people who never logged in have no events; and the app reads `AS_OF` from the source, not from `ground_truth.json`, which exists only to check answers.

*Carried from Phase 0.* `make check` now formats, lints and type-checks `scripts/` with the backend's config, and the format hook uses the same config.

*Gate evidence.*

`make seed` twice gives identical checksums:

```
$ make seed && shasum -a 256 data/events.jsonl data/ground_truth.json
seed 20261030: 9094 lines, as of 2026-10-30
bbbe2aeb3de95a78ec704ebe1e3208d4fcc986b46d72940b3c854fc47f8049fd  data/events.jsonl
aba457bbee3efe870c176c4228ec50341c4e63b167edd11b016c6627790fdce6  data/ground_truth.json
$ make seed && shasum -a 256 data/events.jsonl data/ground_truth.json
seed 20261030: 9094 lines, as of 2026-10-30
bbbe2aeb3de95a78ec704ebe1e3208d4fcc986b46d72940b3c854fc47f8049fd  data/events.jsonl
aba457bbee3efe870c176c4228ec50341c4e63b167edd11b016c6627790fdce6  data/ground_truth.json
```

Pattern tests pass. Each one reads the raw event lines, not the seed's own ground-truth code:

```
$ cd backend && uv run pytest tests/test_seed.py -o addopts="" -v
tests/test_seed.py::test_same_seed_gives_byte_identical_output PASSED
tests/test_seed.py::test_a_different_seed_gives_different_events PASSED
tests/test_seed.py::test_tracked_data_files_are_what_the_seed_produces PASSED
tests/test_seed.py::test_workspace_shape PASSED
tests/test_seed.py::test_every_tool_has_one_distinct_headline_event PASSED
tests/test_seed.py::test_events_cover_sixty_days_ending_on_as_of PASSED
tests/test_seed.py::test_events_use_only_known_names_and_ids PASSED
tests/test_seed.py::test_one_tool_nobody_uses PASSED
tests/test_seed.py::test_one_person_stopped_logging_in PASSED
tests/test_seed.py::test_quiet_person_is_the_only_one_gone_quiet_over_thirty_days PASSED
tests/test_seed.py::test_three_people_never_logged_in PASSED
tests/test_seed.py::test_error_spike_in_the_last_week_from_one_source PASSED
tests/test_seed.py::test_weekdays_are_busier_than_weekends PASSED
tests/test_seed.py::test_usage_is_uneven_across_clients PASSED
tests/test_seed.py::test_today_is_not_empty PASSED
============================== 15 passed in 0.34s ==============================
```

What the patterns look like in the data (from `ground_truth.json`): contact enrichment has 104 headline events in days 1 to 30 and 0 in the last 30; `u014` was last seen on 25 Sep and is the only person gone quiet over 30 days; `u011`, `u027` and `u037` never logged in; the invoice generator has 86 `pdf_renderer` errors in the last 7 days against 0 the week before, hitting 21 people, while its invoices fell from 51 to 10.

`make check` exits 0:

```
$ make check
16 files already formatted
All checks passed!
Success: no issues found in 9 source files
37 passed in 0.92s
 Test Files  1 passed (1)
      Tests  3 passed (3)
$ echo $?
0
```

*Review.* The `reviewer` agent ran on `git diff main...HEAD`. It recomputed usage by tool, activity by person and activity by client for every window on its own and found no mismatch with the ground truth. One blocking finding, fixed:

- **Blocking: the ground truth for `errors_seen` only fitted calls with `with_previous`, while a comment said it fitted both.** Groups at zero are listed only because they had errors in the previous window. The comment and ARCHITECTURE now say that the plain call leaves those groups out, and a test checks that every zero row has a previous count.

Non-blocking, fixed: the tie-break for error groups (count, then source, then tool id) and the `affected` name list are now in ARCHITECTURE; "went quiet" has no previous value for `30d`, because nothing precedes that previous window and a zero there would be an artefact (the fields are empty, and the definition says so); the loader refuses to run unless this Python's SQLite allows one connection across threads; the file source reads as UTF-8.

Carried forward: Phase 2 adds a test that runs lookups from several threads.

**Gate: passed.**

---

## Phase 2: lookups, registry, API

- [x] The five lookups as SQL group-bys, with the `Window` type, pinned time and `with_previous`.
- [x] Tests: every lookup, every window, equals ground truth exactly.
- [x] Typed headline registry and the test proving a tool without a headline event fails `mypy`.
- [x] TTL cache. API routes with the admin-token dependency. Health endpoint.
- [x] Tests: 401 without the token; cached call does not hit the database twice.

**Gate:** all lookup tests equal ground truth. The registry failure test passes. `curl` output for `/health`, `/api/overview?window=7d` with and without the token is in the log.

**Log:**

16 Nov 2026. Branch `phase-2-lookups-v2`, pull request #4. It replaces pull request #3 (branch `phase-2-lookups`), which was closed unmerged; the reason is under "Secret scan" below.

*What was built.* `backend/app/registry.py` (typed catalog), `backend/app/lookups.py` (the five lookups as SQL group-bys, the `Window` type, `with_previous`, and the cached `Lookups` class the API and the assistant share), `backend/app/cache.py` (ten-minute TTL cache), and the routes in `backend/app/main.py`: `GET /health`, `GET /api/overview`, `GET /api/reliability`.

*Docs changed.* The Registry section of `docs/ARCHITECTURE.md` is rewritten. The original said mypy enforces that a `dict[ToolId, HeadlineEvent]` is total. It does not. The registry is now an exhaustive `match` ending in `assert_never`, with a required `headline_event` field, and the section says why.

*A bug found while building.* The first full `make check` after the lookups passed, the second failed: `ValueError: not enough values to unpack (expected 4, got 0)`. The in-memory database is one shared connection, and two threads reading it at once corrupted each other's results. The Phase 1 review had flagged the risk. `Database.connect()` now takes a lock, every lookup goes through it, and the thread test was widened to 400 calls over all five lookups. With the lock bypassed that test fails; with it, it passed five runs in a row:

```
$ uv run pytest tests/test_lookups.py -k threads      # lock bypassed
1 failed, 34 deselected in 0.50s
$ uv run pytest tests/test_lookups.py -k threads      # with the lock
1 passed, 34 deselected in 2.88s
```

*Gate evidence.*

All lookup tests equal ground truth, and the registry failure tests pass. Every lookup, every window, with and without the previous window:

```
$ cd backend && uv run pytest tests/test_lookups.py tests/test_registry.py -o addopts="" -v
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[usage_by_tool-today] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[usage_by_tool-7d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[usage_by_tool-30d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_person-today] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_person-7d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_person-30d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_client-today] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_client-7d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[activity_by_client-30d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[errors_seen-today] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[errors_seen-7d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[errors_seen-30d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[roster-today] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[roster-7d] PASSED
tests/test_lookups.py::test_lookup_with_previous_equals_ground_truth[roster-30d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[usage_by_tool-today] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[usage_by_tool-7d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[usage_by_tool-30d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_person-today] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_person-7d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_person-30d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_client-today] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_client-7d] PASSED
tests/test_lookups.py::test_lookup_without_previous_equals_ground_truth[activity_by_client-30d] PASSED
tests/test_lookups.py::test_errors_without_previous_lists_only_groups_with_errors[today] PASSED
tests/test_lookups.py::test_errors_without_previous_lists_only_groups_with_errors[7d] PASSED
tests/test_lookups.py::test_errors_without_previous_lists_only_groups_with_errors[30d] PASSED
tests/test_lookups.py::test_roster_without_previous_equals_ground_truth[today] PASSED
tests/test_lookups.py::test_roster_without_previous_equals_ground_truth[7d] PASSED
tests/test_lookups.py::test_roster_without_previous_equals_ground_truth[30d] PASSED
tests/test_lookups.py::test_one_person_filter_returns_just_their_row PASSED
tests/test_lookups.py::test_unknown_person_gives_no_rows PASSED
tests/test_lookups.py::test_tool_filter_on_errors PASSED
tests/test_lookups.py::test_time_is_pinned_to_as_of_not_the_wall_clock PASSED
tests/test_lookups.py::test_lookups_are_safe_from_several_threads PASSED
tests/test_registry.py::test_the_unaltered_registry_type_checks PASSED
tests/test_registry.py::test_a_ninth_tool_without_a_headline_event_fails_mypy PASSED
tests/test_registry.py::test_a_catalog_entry_without_a_headline_event_fails_mypy PASSED
tests/test_registry.py::test_a_made_up_headline_event_fails_mypy PASSED
tests/test_registry.py::test_catalog_covers_eight_tools_with_distinct_headline_events PASSED
tests/test_registry.py::test_catalog_matches_the_tools_in_the_data PASSED
============================== 41 passed in 4.50s ==============================
```

`curl` against the running backend (`uv run uvicorn app.main:app --port 8000`, token from `.env`, never printed):

```
$ curl -s -i localhost:8000/health
HTTP/1.1 200 OK
server: uvicorn
content-length: 15
content-type: application/json
vary: Origin

{"status":"ok"}

$ curl -s -i "localhost:8000/api/overview?window=7d"
HTTP/1.1 401 Unauthorized
server: uvicorn
content-length: 44
content-type: application/json
vary: Origin

{"detail":"Missing or invalid admin token."}

$ curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "localhost:8000/api/overview?window=7d" | python3 -m json.tool | head -19
HTTP 200, 16676 bytes
{
    "as_of": "2026-10-30",
    "window": "7d",
    "usage_by_tool": [
        {
            "tool_id": "call_agenda",
            "tool_name": "Call agenda",
            "headline_event": "agenda_created",
            "headline_count": 46,
            "active_people": 26,
            "errors": 1,
            "headline_count_previous": 54,
            "headline_count_change": -8,
            "active_people_previous": 28,
            "active_people_change": -2,
            "errors_previous": 0,
            "errors_change": 1
        },
```

The four lookup sections of that live reply were compared with `ground_truth.json` for `7d`: `{'usage_by_tool': True, 'activity_by_person': True, 'activity_by_client': True, 'roster': True}`.

`make check` after the review fixes:

```
$ make check
All checks passed!
Success: no issues found in 12 source files
103 passed in 6.53s
 Test Files  1 passed (1)
      Tests  3 passed (3)
$ echo $?
0
```

*Review.* The `reviewer` agent reported no blocking findings. It bypassed the lock itself and saw the thread test fail three times out of three, probed the window edges with synthetic events (midnight on `AS_OF` counts; midnight the next day does not), and ran every lookup on an empty events table without a crash. Its eight non-blocking findings were all fixed in this phase:

1. The token check now sits on the `/api` router, so a route added later cannot forget it. A test walks the router's table and requires a 401 from every route.
2. `/docs`, `/redoc` and `/openapi.json` are no longer served.
3. The typed registry now reaches the numbers: `load_database` refuses a source whose tools differ from the registry. Before, only a test tied the two together.
4. The cache test now checks each argument is part of the key (window, `with_previous`, `user_id`, `tool_id`).
5. The names in `affected` are sorted in Python, not by the database, so the order survives a move to Postgres.
6. A source with no events yet loads instead of crashing.
7. Events on an unknown tool, and error events without a tool or a source, are rejected at load with a clear message.
8. The cache drops expired entries and is capped at 512, since part of a key can come from a question.

Carried from Phase 0 and done here: an unset `ADMIN_TOKEN` lets nobody in (tested with `Bearer `, `Bearer` and no header).

*Secret scan.* CI's gitleaks job failed on pull request #3. It was a false positive: a test fixture line passed an empty model key right after a fake admin token, and the scanner read the next argument's name as the token's value. No secret was involved. Because the scan covers the whole history, rewording the line could not clear it, and a first attempt to list the finding in an ignore file was itself flagged (its comment quoted the line). Rather than suppress a scanner finding, the branch was rebuilt from `main` with the fixture reworded, so the flagged line never reaches `main` and the scan passes with no ignore list. The work is the same; the cost is that #3's two commits and their review trail live on the closed pull request, not in `main`.

While diagnosing this, a local scan run without redaction printed the `ADMIN_TOKEN` from `.env` into the build session's output. The token was never committed or pushed and only guards a local demo, but it should be replaced; see the final report.

Known and accepted: cached results are shared lists. The models are frozen, and nothing sorts or filters them in place.

**Gate: passed.**

---

## Phase 3: assistant and evals

- [x] `ModelClient`, `AnthropicClient`, `FixtureClient`.
- [x] Tool-use loop over the five lookups, the refusal rule, and the after-generation number check.
- [x] Cost and latency logging. Rate limit and daily budget on `/api/ask`.
- [x] `evals/questions.json` generated from ground truth: thirty answerable in three tiers, ten refusals including three adversarial (see `docs/SPEC.md`). Results reported per tier. `evals/run.py` with fixture and live modes, writing `docs/eval-results.md`.
- [x] Tests (fixture client): a correct answer, a refusal, a made-up number replaced by a refusal, the rate limit, the budget cap.

- [ ] One live run of `make evals`, with its table in the log. Not done: no API key yet.

**Gate:** fixture evals run inside `make check` and pass. One live run of `make evals` is done only if `ANTHROPIC_API_KEY` is set and the human has said yes; its table goes in the log. If there is no key, say so and leave the live run unticked.

**Log:**

16 Nov 2026. Branch `phase-3-assistant`, pull request #5.

*What was built.* `backend/app/llm.py` (`ModelClient`, `AnthropicClient`, `FixtureClient`, the price table), `backend/app/assistant.py` (system prompt, strict tool schemas for the five lookups, the loop, the refusal rule, the number check, cost and latency logging), `backend/app/limits.py` (per-visitor rate limit, daily budget), `POST /api/ask`, and `backend/evals/` (`build.py` generates `questions.json` and `fixtures.json` from ground truth; `scoring.py`; `run.py` with fixture and live modes). `make seed` now also regenerates the eval files; `make check` now runs the fixture evals.

*Decisions from the plan, as built.*

- Default model `claude-haiku-5-5`. The price table also has `claude-opus-5-5`. A model without a price stops a live app at startup (`test_an_unpriced_model_stops_a_live_app_from_starting`).
- `make evals` runs the configured model; `make evals MODEL=claude-opus-5-5` runs another. Each model gets its own section in `docs/eval-results.md`.
- Demo mode: with no `ANTHROPIC_API_KEY` the app answers from fixtures and every `/api/ask` reply carries `demo_mode: true`. A question with no recording gets a plain "live model is not connected" reply, worded differently from a refusal. Phase 6 has a new item: a deployed build must refuse to start in demo mode.
- Server-side model fallbacks are off.

*Where the library differs from the docs* (now written into ARCHITECTURE, "What the API allows"): the Anthropic SDK is 2.x; current models reject a forced tool choice and sampling parameters, so there is no determinism knob; a reply can stop with `stop_reason: "refusal"`; thinking blocks must go back unchanged, so the assistant turn is appended exactly as received. "Hard timeout, one retry with backoff" is the SDK's own `timeout=30` and `max_retries=1`.

*What fixture evals do and do not show.* The fixture client plays the model from a script: which lookup to call, and which field of the result to put in the answer. The number still comes from the real lookup and is scored against ground truth. That proves the lookups, the loop, the number check and the scorer. It does not show that a model picks the right lookup. Only a live run does.

*Gate evidence.*

Fixture evals run inside `make check` and pass:

```
$ make check
All checks passed!
Success: no issues found in 19 source files
259 passed in 9.21s
Evals, fixture mode (no model was called):

| Tier | Questions | Passed | Rate |
|---|---|---|---|
| direct | 12 | 12 | 100% |
| indirect | 10 | 10 | 100% |
| comparison | 8 | 8 | 100% |
| refusal | 10 | 10 | 100% |
| all | 40 | 40 | 100% |
 Test Files  1 passed (1)
      Tests  3 passed (3)
$ echo $?
0
```

The tests the plan names, by name:

```
tests/test_assistant.py::test_a_correct_answer_carries_the_number_from_the_lookup PASSED
tests/test_assistant.py::test_a_question_no_lookup_covers_is_refused_and_names_what_can_be_answered PASSED
tests/test_assistant.py::test_a_made_up_number_is_replaced_by_the_refusal_and_logged PASSED
tests/test_api.py::test_rate_limit_is_per_visitor_and_returns_a_clear_message PASSED
tests/test_api.py::test_daily_budget_stops_the_endpoint_before_the_model_is_called PASSED
```

`/api/ask` on the running backend, in demo mode (token from `.env`, never printed):

```
$ ask "How many invoices were issued in the last 7 days?"
{"answer":"In the last 7 days, 10 invoices were issued.","window":"7d","lookups_called":[{"name":"usage_by_tool","window":"7d","args":{"window":"7d","with_previous":false}}],"refused":false,"latency_ms":4,"cost_usd":0.0,"demo_mode":true}
$ ask "What will usage look like next month?"
{"answer":"I can't answer that from this dashboard. I can answer questions about usage by tool, activity by person, activity by client, errors seen, and the roster (who is in, who never showed up, who went quiet), for today, the last 7 days or the last 30 days.","window":null,"lookups_called":[],"refused":true,"latency_ms":0,"cost_usd":0.0,"demo_mode":true}
$ ask "What is the weather like?"
{"answer":"Demo mode: the live model is not connected, and this question has no recorded answer. Try one of the suggested questions.","window":null,"lookups_called":[],"refused":true,"latency_ms":0,"cost_usd":0.0,"demo_mode":true}
$ curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/api/ask -d '{"question":"x"}'     # no token
401
$ # four more questions from the same visitor, with ASK_RATE_PER_MINUTE=5
200 200 429 429
```

Cost and latency are logged per model call (stderr of the backend):

```
2026-11-16 11:45:42,439 INFO ask_analytics.assistant model_call model=fixture latency_ms=0 input_tokens=0 output_tokens=0 cost_usd=0.000000 stop_reason=tool_use
2026-11-16 11:45:42,448 INFO ask_analytics.assistant model_call model=fixture latency_ms=0 input_tokens=0 output_tokens=0 cost_usd=0.000000 stop_reason=end_turn
```

**Live run: not done, box left unticked.** `ANTHROPIC_API_KEY` is empty, as agreed, so `make evals` was not run and no model was called at any point in this phase. `docs/eval-results.md` says "None yet" under live runs. SPEC's "`make evals` produces a results table" is therefore not met yet. A test checks that a live run without a key stops before any client is built.

*Review.* The `reviewer` agent found four blocking problems. All four were real and are fixed:

1. **The number check let small invented counts through.** It collected every run of digits in the raw result text, so digits inside ids (`u001` to `u040`) and dates (`2026-10-30`) excused any count from 1 to 40, plus 10, 30 and 2026. Most counts in this data are in that range. Now only JSON numbers in the results count. Digits are otherwise allowed only inside a date or an id that is itself in the results, or in a window phrase. New tests: "12 errors" fails against a roster result; "10 invoices" fails against a result whose only 10 is the month in `as_of`.
2. **A model error after billed calls was never charged to the budget.** Cost is now reported per model call, and a call that fails or times out is charged as a worst-case call.
3. **A burst of questions could overshoot the budget**, because the check looked only at what was already spent. A question now reserves its worst-case cost before the model is called and settles afterwards. Worst case per question is about $0.02 on Haiku and $0.71 on Opus, so the endpoint stops that far short of the limit rather than going over it.
4. **The eval scorer passed a wrong direction when the answer echoed both words** ("more or less? It went up"). The direction word must now be near the number, and the opposite word must not be.

Non-blocking, fixed: the visitor key uses the last `X-Forwarded-For` entry and groups IPv6 by /64; one model outage no longer aborts a live eval run; `REFUSE` anywhere in a reply is a refusal; superscript digits are read as digits; dates and window phrases are stripped before eval numbers are matched; "what is failing most" is scored on the count alone, since naming the tool or the error source is equally right.

Known and accepted, noted in `docs/eval-results.md`: a few expected numbers are small (1, 3, 5), and "Who has gone quiet?" measures the choice of window as much as the count.

**Gate: passed, with the live run outstanding.**

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
- [ ] Startup check: a deployed build must refuse to start in demo mode (no `ANTHROPIC_API_KEY`). Demo mode answers from recorded fixtures and is for local use only. Added to the plan in Phase 3, when demo mode was built.
- [ ] Docker. Backend on Railway, frontend on Vercel. Scheduled cache warm.
- [ ] README on the seven-section spine from `job-search/portfolio/README.md`, with the live eval table and its date.

**Gate:** hosted page loads in under two seconds. CI is green on `main`. No key in the repo or its history.

**Log:**
