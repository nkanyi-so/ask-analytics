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

- [x] One live run of `make evals`, with its table in the log. *Done on 16 Nov 2026, once a key existed: see the entry at the end of this phase's log.*

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

*Second entry, 16 Nov 2026: the live run.* The human added a key and said yes to `claude-haiku-5-5`. Five runs, about $0.38 in all. The last one:

```
$ make evals
Evals, live, claude-haiku-5-5:

| Tier | Questions | Passed all 3 runs | Rate | Single runs passed |
|---|---|---|---|---|
| direct | 12 | 12 | 100% | 36 of 36 |
| indirect | 10 | 10 | 100% | 30 of 30 |
| comparison | 8 | 8 | 100% | 24 of 24 |
| refusal | 10 | 10 | 100% | 30 of 30 |
| all | 40 | 40 | 100% | 120 of 120 |

Failures (any run):
None.
```

The first run scored 70% (and a run before that had every request rejected, over a tool schema the API does not accept). `docs/eval-results.md` has every run, each failure with the answer that showed it, and each fix. In short: the model was missing facts (which tools exist, which lookup holds a total, what days a window covers), the scorer misjudged some correct answers, and the number check needed to read numbers written as words. The `reviewer` agent then found two blocking problems in those fixes: an allowance that let an invented previous value past the number check, and a scorer rule that passed a wrong direction. Both were tightened, with tests, before the fifth run. The refusal tier was 30 of 30 in every run.

The 100% is partly fitted to these forty questions, because the fixes were tested on them. SPEC says to add harder questions when a first run is perfect; the first run was not, but the same advice now applies. `claude-opus-5-5` has not been run.

**Gate: passed, live run included.**

---

## Phase 4: dashboard

- [x] Overview and Reliability pages, window switch, "Data as of" line.
- [x] Ask box with three suggested questions; each answer shows the lookup and window used.
- [x] Server-side route handlers holding the admin token. No token in any client bundle (grep the build output and show it).
- [x] Clean and readable only. No visual polish pass.

**Gate:** `make dev` serves the page on seeded data. Screenshots or text dumps of both pages are in the log. The three suggested questions answer correctly and a fourth, unanswerable one is refused (shown with the fixture client when no key is set; repeat live once a key exists). `make check` exits 0.

**Log:**

16 Nov 2026. Branch `phase-4-dashboard-v2`, pull request #7. It replaces pull request #6 (branch `phase-4-dashboard`), closed unmerged for the same reason as #3 in Phase 2: a test line with a fake key next to a fake token tripped CI's secret scan, and the scan covers the whole history. No secret was involved. This time the cause is fixed as well: the pre-commit hook now scans staged changes, so a flagged line is stopped before it is committed. That is the one place the hook now differs from ytscribe's.

*What was built.* In `frontend/src`: `lib/backend.ts` (the only module that reads the admin token; marked `server-only`), `lib/backend-call.ts` (how the server calls the backend, testable without the environment), `lib/types.ts` (hand-written to match the API), `app/page.tsx` (Overview), `app/reliability/page.tsx`, `app/api/ask/route.ts` (the proxy), `components/` (Ask box, tiles, window switch, header) and `app/error.tsx`. `make check` now also runs `next build`. On the backend, `/health` now reports `demo_mode`, so the page can label recorded answers before anything is asked.

*How the rules are kept.*

- **No aggregation in the frontend.** Every number on the page is a field from the API. `formatChange` only words the sign the backend sent. Lists are joined, never counted.
- **The token never reaches the browser.** Pages are server components. The Ask box is the only client component and it talks to the route handler, which adds the token on the server and returns the backend's JSON body and nothing else. Importing `lib/backend.ts` from a client component fails the build.
- **Types.** `backend/tests/test_frontend_contract.py` compares the field names of each API model with its TypeScript interface, and checks that the three suggested questions are the ones with recorded answers.

*Where the library differs from the docs.* Next.js 16: `searchParams` is a Promise; `next lint` is gone; `cacheComponents` (on by default in a new app) is off, because pages read fresh numbers per request and the backend owns the cache. ARCHITECTURE says pages call the backend through route handlers under `/app/api/*`; reads are done in server components instead, which is the app router's way to keep them on the server, and the one write (Ask) has the route handler.

*Gate evidence.* All of it with `make dev` running (backend on :8000, frontend on :3000), seeded data, demo mode.

Overview, `curl -s "localhost:3000/?window=7d"`, as text (first part):

```
Overview
Data as of 2026-10-30. Seeded demo data, not a live system.
today | the last 7 days | the last 30 days
Ask
Demo mode: recorded answers, live model not connected
Ask about the numbers on this page
How many invoices were issued in the last 7 days?
Which tool is nobody touching?
Did email usage go up or down this week, and by how much?
People in the app, the last 7 days
Active
35
no change vs the 7 days before
Went quiet
2
no change vs the 7 days before
Never showed up
3
Invited
40
Went quiet: Xena Jarrah, Yara Quill
Never showed up: Yara Dunmore, Otto Thackeray, Sami Holt
Headline number per tool, the last 7 days
Call agenda
46
−8 vs the 7 days before
Contact enrichment
0
no change vs the 7 days before
Email drafter
91
+5 vs the 7 days before
Invoice generator
10
−41 vs the 7 days before
```

The window switch works: with `?window=30d` the same page shows Active 36 (−1 vs the 30 days before) and Went quiet 1 with "no earlier data", which is the definition, not a bug.

Reliability, `curl -s "localhost:3000/reliability?window=7d"`, as text (first rows):

```
Reliability
Data as of 2026-10-30. Seeded demo data, not a live system.
Errors by source, the last 7 days
Source | Tool | Errors | Change vs the 7 days before | People affected | Who was affected
pdf_renderer | Invoice generator | 86 | +86 | 21 | Dara Okoro, Elio Holt, Faye Abara, Hana Abara, Ivo Penrose, Juno Dunmore, ...
input_validation | Media plan builder | 1 | +1 | 1 | Faye Abara
input_validation | Proposal writer | 1 | +1 | 1 | Kofi Eklund
rate_limit | Email drafter | 1 | no change | 1 | Tess Marlow
```

The three suggested questions and a fourth that must be refused, asked through the frontend's proxy. The caller sends no token. **These answers come from the fixture client, because no API key is set.** They show the page, the proxy, the loop and the lookups working together. They do not show a model choosing the right lookup; that needs the live run.

```
$ ask "How many invoices were issued in the last 7 days?"
  answer:      In the last 7 days, 10 invoices were issued.
  refused:     False | window: 7d | lookups: ['usage_by_tool'] | demo_mode: True
$ ask "Which tool is nobody touching?"
  answer:      Nobody has used Contact enrichment in the last 7 days.
  refused:     False | window: 7d | lookups: ['usage_by_tool'] | demo_mode: True
$ ask "Did email usage go up or down this week, and by how much?"
  answer:      Emails sent are up by 5 in the last 7 days compared with the 7 days before.
  refused:     False | window: 7d | lookups: ['usage_by_tool'] | demo_mode: True
$ ask "What will usage look like next month?"
  answer:      I can't answer that from this dashboard. I can answer questions about usage by tool, activity by person, activity by client, errors seen, and the roster (who is in, who never showed up, who went quiet), for today, the last 7 days or the last 30 days.
  refused:     True | window: None | lookups: [] | demo_mode: True
```

Each of the three answers matches ground truth (10 invoices, contact enrichment unused, emails up by 5).

No token in any client bundle. After `next build`, counting files only (the token value is never printed):

```
served pages containing the token: 0
files under frontend/.next: 215
files under frontend/.next containing the token value: 0
files under frontend/.next/static (what browsers download): 15
...containing the token value: 0
...mentioning ADMIN_TOKEN or BACKEND_URL by name: 0
server files mentioning ADMIN_TOKEN by name (it is read there at request time): 4
control, the grep can find things: files containing 'Demo mode': 1
```

`make check`:

```
$ make check
All checks passed!
Success: no issues found in 19 source files
272 passed in 13.80s
| all | 40 | 40 | 100% |
 Test Files  3 passed (3)
      Tests  30 passed (30)
✓ Compiled successfully
$ echo $?
0
```

*Review.* The `reviewer` agent built the frontend itself, found no way for the token or the backend URL to reach a browser, confirmed the `server-only` guard fails a build that breaks it, and found no aggregation in the frontend. One blocking finding, fixed:

- **Blocking: `server-only` was added without a line in `docs/decisions/`.** Added.

Non-blocking, all fixed:

- Another site could make its visitors' browsers post questions to the Ask route and drain the budget. The route now turns away requests that are not JSON, that the browser marks as coming from another site, or that are larger than a question can be. Seen on the running app: same-origin JSON 200, cross-site 403, `text/plain` 415, not JSON 400, `GET` 405.
- A visitor could pick their own rate-limit key by sending `x-real-ip` when the frontend is not on Vercel. The address is now believed only on Vercel; anywhere else everyone shares one key. Seen locally: five asks with five different `x-real-ip` values gave `200 200 200 200 429`.
- Proxies between frontend and backend rewrite `X-Forwarded-For`, which would have made every visitor one visitor after deploy. The visitor's address now travels in `X-Visitor-Address`, a header of our own.
- The answer area is now a live region that exists before the answer arrives, so screen readers announce the first answer.

For Phase 6: check on the real platforms that `x-real-ip` on Vercel and `X-Visitor-Address` through Railway behave as assumed.

**Gate: passed.** The Ask evidence is from the fixture client; repeat it live once a key exists.

---

## Phase 5: real source, MCP, summary (second session)

- [x] Mixpanel source: track via ingestion, read via raw export with a service account, one download per window, retry with backoff and a hard timeout.
- [x] MCP server (stdio) exposing the five lookups; Claude Desktop config in the README. *The config is in `docs/mcp.md` until Phase 6 writes the README.*
- [x] Monday summary endpoint.

**Gate:** with Mixpanel keys set locally, lookups over the Mixpanel source equal ground truth. An MCP client lists five tools and one call returns the same result as the API.

**Log:**

16 Nov 2026. Branch `phase-5-sources-mcp-summary`. **The gate is not passed: its Mixpanel half needs keys that do not exist yet.** The MCP half is shown below.

*What was built.* `backend/app/sources/mixpanel.py` (the source, the wire format, the push), `backend/app/sources/mixpanel_push.py` (`make mixpanel-push`), `backend/app/mcp_server.py` (`make mcp`), `backend/app/summary.py` and `GET /api/summary`, `docs/mcp.md` (Claude Desktop config). New settings: `MIXPANEL_PROJECT_ID`, `MIXPANEL_SERVICE_ACCOUNT_USERNAME`, `MIXPANEL_SERVICE_ACCOUNT_SECRET`, `MIXPANEL_REGION`, `MIXPANEL_AS_OF`. ARCHITECTURE has new sections for the Mixpanel source and the MCP server.

*Where the libraries differ from the docs, and what was decided.*

- **"One download per window" is one download per load.** Every window is answered from one in-memory database, so a load is a single export request for the 30-day window and the 30 days before it. No lookup triggers a download.
- **Mixpanel's export is not deduplicated** and older projects shift times into the project's timezone. Events carry their own id and timestamp as properties, duplicates are dropped by id, and the date range is padded by a day each side.
- **The roster travels as events** (`workspace_user`, `workspace_client`, `workspace_tool`, `workspace_meta`), because people who never logged in have no events.
- **The export needs a date range before anything is read**, so `MIXPANEL_AS_OF` is a setting. The data carries the same day, and a mismatch stops the load.
- **The MCP SDK is 2.x.** The low-level server takes handlers as constructor arguments, and passing a server object to `Client` is the in-memory test transport. The server reuses the assistant's `TOOL_SPECS` and `run_lookup`, so the two cannot drift.
- **The MCP server has no token and no number check.** It is a local child process of its client, and the client's model words its own answers. `docs/mcp.md` says so.
- **Summary sending is not built.** SPEC calls it optional. The endpoint returns HTML; nothing emails it.
- **The Claude Desktop config is in `docs/mcp.md`, not the README**, because the README is Phase 6 work. Phase 6 should lift it in.
- `mcp` sits in its own dependency group (it brings about a dozen packages), so a deployed API image can leave it out. `httpx2` became a runtime dependency.

*Gate evidence.*

**Mixpanel half: not shown.** No Mixpanel project or service account exists, so nothing has been sent to or read from Mixpanel. What exists instead is a test against a fake Mixpanel (an in-process HTTP handler that stores what is imported and serves it back as an export, filtered by event name and date range as the real one is). Over that fake, the pushed workspace comes back identical and all five lookups in all three windows equal ground truth:

```
tests/test_mixpanel.py::test_a_workspace_pushed_to_mixpanel_comes_back_identical PASSED
tests/test_mixpanel.py::test_every_lookup_over_the_mixpanel_source_equals_ground_truth PASSED
tests/test_mixpanel.py::test_a_load_is_one_download_with_a_padded_date_range PASSED
tests/test_mixpanel.py::test_duplicates_in_the_export_are_dropped PASSED
tests/test_mixpanel.py::test_retries_and_waits_share_one_deadline PASSED
```

That proves the code on this side of the wire. It does not prove Mixpanel behaves as its documentation says. To close the gate: create a Mixpanel project that holds nothing else and a service account, fill the five `MIXPANEL_*` names in `.env`, run `make mixpanel-push`, set `EVENT_SOURCE=mixpanel`, then compare the lookups with ground truth.

**MCP half: shown.** A real MCP client, talking to `python -m app.mcp_server` as a separate process over stdin and stdout:

```
tools: ['usage_by_tool', 'activity_by_person', 'activity_by_client', 'errors_seen', 'roster']
invoice_generator via MCP: {"headline_count": 10, "headline_count_previous": 51, "headline_count_change": -41, "errors": 86}
```

Those are the numbers the dashboard shows for the last 7 days. The test that holds this in place compares the MCP result with `/api/overview` row for row:

```
tests/test_mcp_server.py::test_the_real_server_over_stdio_lists_five_tools_and_matches_the_api PASSED
tests/test_mcp_server.py::test_a_call_in_process_returns_what_the_api_returns[usage_by_tool] PASSED
tests/test_mcp_server.py::test_a_client_lists_the_five_lookups_with_the_assistants_schemas PASSED
```

Not done: the config has not been tried in Claude Desktop itself.

**Summary.** `GET /api/summary` is 401 without the token and `text/html` with it. As text (first part):

```
Weekly summary
The last 7 days, ending 2026-10-30, next to the 7 days before. Seeded demo data.
People
 | Last 7 days | 7 days before | Change |
Active | 35 | 35 | no change |
Went quiet | 2 | 2 | no change |
Invited: 40. Never showed up: 3 (Yara Dunmore, Otto Thackeray, Sami Holt).
Went quiet: Xena Jarrah, Yara Quill.
Headline number per tool
Tool | Last 7 days | 7 days before | Change | Active people | Errors |
Call agenda | 46 | 54 | -8 | 26 | 1 |
Contact enrichment | 0 | 0 | no change | 0 | 0 |
Email drafter | 91 | 86 | +5 | 31 | 1 |
Invoice generator | 10 | 51 | -41 | 22 | 86 |
```

`make check`:

```
$ make check
All checks passed!
Success: no issues found in 23 source files
306 passed in 12.41s
| all | 40 | 40 | 100% |
 Test Files  3 passed (3)
      Tests  30 passed (30)
$ echo $?
0
```

*Review.* The `reviewer` agent found two blocking problems. Both were real and are fixed:

1. **A local `make check` could have called the real Mixpanel.** The fixture evals read `.env`, and this is the phase where `.env` gets pointed at Mixpanel. Fixture mode now ignores `.env` and always scores the seeded file. CI was never affected (it has no `.env`).
2. **The hard timeout was not hard.** The 60-second limit was per attempt and a stalled read was retried, so a silent Mixpanel could block startup for about two minutes. A load now has one deadline covering every attempt and wait, no single wait may outlast what is left, and a timeout at the deadline is not retried.

Non-blocking, all fixed: the person is read back from an explicit `user_id` property, since Mixpanel may rewrite `distinct_id`; the service-account secret is kept out of the config's `repr`; the fake Mixpanel now applies the date range, so a range that is too narrow fails the test; `anyio` has its line in the dependency record.

**Gate: not passed** (as of the first entry above). MCP half shown; Mixpanel half waited for keys.

*Second entry, 16 Nov 2026: the Mixpanel half, against the real service.* The human created a Mixpanel project that holds nothing else (US residency, free plan) and a service account with the project role Admin, and put the five `MIXPANEL_*` names in `.env`.

`make mixpanel-push`:

```
Sent 9094 records to Mixpanel project <project id> (us).
```

Then the source, read through the real export API, compared with the seeded file and with ground truth (`EVENT_SOURCE` forced to `mixpanel` for the comparison):

```
export: one request, 7.5s
clients 6 tools 8 users 40 events 9039 as_of 2026-10-30
workspace identical to the file source: True
  activity_by_client   today  equals ground truth
  activity_by_client   7d     equals ground truth
  activity_by_client   30d    equals ground truth
  activity_by_person   today  equals ground truth
  activity_by_person   7d     equals ground truth
  activity_by_person   30d    equals ground truth
  errors_seen          today  equals ground truth
  errors_seen          7d     equals ground truth
  errors_seen          30d    equals ground truth
  roster               today  equals ground truth
  roster               7d     equals ground truth
  roster               30d    equals ground truth
  usage_by_tool        today  equals ground truth
  usage_by_tool        7d     equals ground truth
  usage_by_tool        30d    equals ground truth
15 of 15 lookup results equal ground truth
```

What the real service showed that the fake could not:

- **Mixpanel rewrites dates.** A property sent as `2026-07-01` came back as `2026-07-01T00:00:00`, and the first real load failed on it. Dates are now read in either form, and the fake Mixpanel in the tests now does the same rewriting, so this cannot come back unnoticed. Timestamps (`ts`) came back exactly as sent.
- **The first export after an import is slow.** Straight after the first push, a one-day export took 109 seconds to send its first byte, so the load hit its 60-second deadline and stopped, as designed. Minutes later the full 62-day export took 7 seconds. The deadline stays at 60 seconds, because an app that hangs at startup is worse than one that says why it cannot start. If a load fails right after a first push, wait a few minutes.
- **A repeated push is harmless.** After a second `make mixpanel-push` the export still held 9,094 records with no duplicate ids, and the comparison above passed again unchanged.
- Mixpanel adds properties of its own (`$user_id`, `$import`, several `$mp_*`). The source ignores them.

Still not done: the MCP config has not been tried in Claude Desktop itself.

**Gate: passed.** Lookups over the real Mixpanel source equal ground truth, and an MCP client lists five tools and gets the same result as the API.

---

## Phase 6: CI, deploy, README (second session)

- [ ] `main` protected; CI (in place since Phase 0) required to pass before merge.
- [x] Startup check: a deployed build must refuse to start in demo mode (no `ANTHROPIC_API_KEY`). Demo mode answers from recorded fixtures and is for local use only. Added to the plan in Phase 3, when demo mode was built.
- [ ] Docker. Backend on Railway, frontend on Vercel. Scheduled cache warm. *Docker and the cache warm are done; the deploy is not.*
- [ ] README on the seven-section spine from `job-search/portfolio/README.md`, with the live eval table and its date. *Written, with the live rows empty and the "Before" section marked as a draft.*

**Gate:** hosted page loads in under two seconds. CI is green on `main`. No key in the repo or its history.

**Log:**

16 Nov 2026. Branch `phase-6-deploy-readme`, stacked on the Phase 5 branch. **Partial, out of order, at the human's request**: Phase 5's gate is still open (it waits for Mixpanel keys), and the human asked for the Phase 6 parts that need neither Mixpanel nor a hosting account. The gate below is not passed and cannot be until there is a deploy.

*Done.*

- **Startup check.** A deployed build refuses to start in demo mode, without an admin token of at least 32 characters, or on any source but the file (`check_deployable` in `backend/app/main.py`). "Deployed" means the Docker image (it sets `DEPLOYED=1`) or anything running on Railway (which sets `RAILWAY_ENVIRONMENT_NAME`). The refusal names every problem at once and prints no secret.
- **Scheduled cache warm.** In the backend's own process: at startup, then every five minutes, it recomputes the fifteen results the dashboard and the summary use and stores them fresh. No platform scheduler. SPEC's "one scheduled warm" assumed a cron; this needs none and cannot be forgotten at deploy time.
- **Docker.** `backend/Dockerfile` (built from the repo root, runtime packages only, non-root user) and an allow-list `.dockerignore`, so `.env` and git history cannot enter an image. A new CI job, `image`, builds it and checks that it refuses demo mode and serves when configured.
- **README** on the seven-section spine, and `docs/deploy.md`.

*Not done, and why.*

- [ ] **`main` protected.** GitHub refused: "Upgrade to GitHub Pro or make this repository public to enable this feature." The repo is private on the free plan. Do it when the repo goes public: require the `check`, `secrets` and `image` jobs.
- [ ] **Deploy** to Railway and Vercel. Needs the human's accounts. `docs/deploy.md` has the steps; none have been run.
- [ ] **README's live eval table.** The live rows say "not run yet". No key, no run.
- [ ] **README's "Before" section** is a draft written from project notes, marked as such in the file. The human should rewrite it in their own words before the repo is public.

*Where the platforms differ from the docs.* PLAN says "Scheduled cache warm" next to the deploy; it is in-process instead (above). Railway's `railway.toml` stops working for existing services on 1 December 2026 and cannot be used for new ones, so no Railway config file is committed and the settings are listed for the dashboard. Docker is not installed on the development machine, so the image has only ever been built by CI.

*Evidence.*

The app from a runtime-only install (`uv sync --no-default-groups`, the same package set as the image), with `DEPLOYED=1` and no key:

```
RuntimeError: Refusing to start a deployed build: ANTHROPIC_API_KEY is not set (demo mode is for local use only).
ERROR:    Application startup failed. Exiting.
```

The same with a placeholder key (no model is called by starting):

```
{"status":"ok","demo_mode":false}
overview without token: 401
```

Tests by name:

```
tests/test_deploy.py::test_a_deployed_build_refuses_to_start_in_demo_mode PASSED
tests/test_deploy.py::test_running_on_railway_counts_as_deployed_even_without_the_image PASSED
tests/test_deploy.py::test_the_first_visitor_after_a_start_reads_only_from_the_cache PASSED
tests/test_deploy.py::test_a_warm_replaces_entries_before_they_expire PASSED
tests/test_deploy.py::test_the_schedule_keeps_running_after_a_failed_warm PASSED
```

`make check`:

```
$ make check
All checks passed!
Success: no issues found in 23 source files
319 passed in 14.59s
| all | 40 | 40 | 100% |
 Test Files  3 passed (3)
      Tests  30 passed (30)
$ echo $?
0
```

*Review.* The `reviewer` agent found nothing blocking in the code, the Dockerfile or the CI job, and two false sentences in the README, both corrected: demo mode answers all forty eval questions, not only the three suggested ones; and `make check` does not run CI's image build or secret scan. Also fixed: the deployed check now covers a Railway service built without the Dockerfile; a token of spaces is refused; the test fixture is no longer affected by a `DEPLOYED` left in a developer's shell; the image layer no longer keeps uv's cache.

**Gate: not passed.** Nothing is hosted.

---

## Phase 7: design pass

Added on 16 Nov 2026 at the human's request. SPEC calls visual polish "a later layer"; this is that layer. No backend behaviour, API contract or existing test may change.

- [x] `docs/DESIGN.md` written first and approved: direction, tokens, every screen state.
- [x] Built with all tokens in `frontend/src/app/tokens.css`.
- [x] Every state photographed at 375, 768 and 1280 in light and dark; reviewed against DESIGN.md; fixed; repeated once.
- [x] `npx impeccable detect` run, and what it found fixed.

**Gate:** `make check` exits 0 with no change under `backend/app`, `backend/evals` or any existing test. Every state in DESIGN.md has a screenshot, or DESIGN.md says why not. Contrast passes AA. Every control is reachable by keyboard with a visible focus ring. The detector reports nothing.

**Log:**

16 Nov 2026. Branch `design-pass`. Done at the human's request while Phase 6's gate is still open: that gate waits for a deploy, which the human has put last. Nothing under `backend/app` or `backend/evals` changed, and no existing test was edited.

*What was built.* `docs/DESIGN.md` first, approved before any code. Then: `frontend/src/app/tokens.css` (every colour, size and space), a rewritten `globals.css`, the Ask panel (`components/AskPanel.tsx`), both pages as figures and tables instead of cards, and one new route on the frontend's own server, `GET /api/evidence`, with `lib/evidence.ts` and `lib/answer.ts` behind it. Old components `AskBox`, `Tile` and `PageHeader` are gone.

*The one thing the brief could not have as asked.* "Show what the lookup returned" needs the lookup's result, which the API does not send with an answer, and the brief ruled out API changes. The page re-reads the lookup through the existing endpoints instead. It marks a number in the answer only when the number is in a row shown and the answer uses that measure's words; otherwise it shows the row and marks nothing.

*Gate evidence.*

`make check`, with no change under `backend/app` or `backend/evals`:

```
$ make check
All checks passed!
Success: no issues found in 23 source files
332 passed
| all | 40 | 40 | 100% |
 Test Files  6 passed (6)
      Tests  53 passed (53)
$ echo $?
0
$ git diff main --stat -- backend/app backend/evals
$
```

Screenshots: `frontend/scripts/screenshots.mjs` took 126 in demo mode (21 states, three widths, light and dark) and 18 against the live model (12 real questions, $0.008). Two states have none, and DESIGN.md says why: an answer using two lookups (no recorded answer does, and the live model did not for any question tried) and Reliability with no errors (the seeded data has errors in every window).

Contrast: every text pair computed, lowest 4.69 (captions on the sunken surface, light); control borders 3.37 at lowest. All pass AA.

Keyboard, driven by Playwright:

```
a "ask-analytics" ring=true
a "Overview" ring=true
a "Reliability" ring=true
input "How many invoices were issued in the las" ring=true
button "Ask" ring=true
button "How many invoices were issued in the las" ring=true
button "Which tool is nobody touching?" ring=true
button "Did email usage go up or down this week," ring=true
a "Today" ring=true
a "7 days" ring=true
a "30 days" ring=true
Enter in the field sends the question: Nobody has used Contact enrichment in the last 7 days.
Ask with nothing typed moves focus to: question
While waiting, focus stays on: question
Sideways scroll on Reliability at 800 wide: 0 px (was 83)
```

`npx impeccable detect`, on the source and on both pages at 1280 and 390 wide: nothing reported. Its first run found two things, both fixed: a thick rule down the side of notices, and the typeface (Instrument Sans, on its overused list; now Hanken Grotesk).

*Self-review of the screenshots, two rounds.* Round one: the question field collapsed on a phone; a full-width accent button was too loud in dark mode; table columns were spread too wide; the rate-limit notice said the same thing three times; notices sat in half of a two-column layout; the Ask button was greyed out on first visit, so the page opened with no accent. Round two: phone tables were eleven screens long (one line per figure), now one wrapped line per row; a heading touched its paragraph on the error page.

*Review.* The `reviewer` agent found three blocking problems, all fixed:

1. **The panel said numbers were marked when none were**, for any answer without a number.
2. **The refusal line could be untrue.** "No answer passed the check" is one of five reasons a lookup can run and no answer be shown. The line now claims only what is known.
3. **The new route returned more than the page shows** (ids, the full list of active people), while the docs said otherwise. It now returns titled rows of figures only, and the docs name the one extra thing it serves: previous-window values.

Non-blocking, fixed: a number could be marked as checked against a different measure that happened to share it ("22 errors" against "active people 22"), so marking now needs the measure's words as well; keyboard focus was lost on submit; heading order; phone tables were read twice by screen readers; Reliability scrolled sideways between 768 and 850 wide; hard-coded values moved into the token file; a new test pins the two backend messages the panel reads.

**Gate: passed.**

*Second entry, 17 Nov 2026: recomposed.* The human reviewed the first build and asked for the composition of the product this is rebuilt from: a dashboard of key values, and an assistant in a side panel that is there on every view. Structure only was taken from that product; no names, terms or data. Same branch, same pull request. Still no change under `backend/app` or `backend/evals`, and no existing test edited.

*What changed.* One frame mounted in the root layout (`components/Shell.tsx`) holds the header, the view and the assistant, so the assistant keeps its answers when the view changes. Overview is now eight tiles (one headline number per tool) and three cards; Reliability is one card. The assistant is docked and open at 1280 wide or more, and a dialog over the page below that.

*Two deliberate differences from the original.* Its assistant floats over the dashboard and covers about two fifths of it; this one is docked, so nothing is covered. Its answers show no trace of how they were reached; this one keeps the working.

*Two things given up, with the human's agreement.* The answer is no longer a page-wide headline: its number is still the largest on the screen, but it shares the stage with the dashboard. And the panel looks like a chat but is not one: each question stands alone, because the backend keeps no memory, and the panel says so. Real follow-ups are a later piece of work.

*Evidence.*

```
$ make check
All checks passed!
Success: no issues found in 23 source files
332 passed
| all | 40 | 40 | 100% |
 Test Files  6 passed (6)
      Tests  53 passed (53)
$ echo $?
0
$ git diff main --stat -- backend/app backend/evals
$
```

Screenshots: 144 in demo mode (24 states, three widths, light and dark) and 30 live. Behaviour, driven by Playwright:

```
1280, docked. Tab order: brand, Overview, Reliability, Today, 7 days, 30 days,
  Close the Ask panel, three suggested questions, the field, Ask. Every one with a focus ring.
Enter sends the question: Nobody has used Contact enrichment in the last 7 days.
After changing view, answers kept: 1
Escape while docked leaves it open: true
While waiting, focus stays on: question
375: nine Tabs land in: panel, browser | role: dialog | page scrolled behind: 0 px
768: nine Tabs land in: panel, browser | role: dialog | page scrolled behind: 0 px
768: Escape closes it and focus returns to: Ask a question
375: Escape closes it and focus returns to: Ask a question
1280: after Try again, entries: 1 | failure notices left: 0
No sideways scroll on either view at 320, 375, 768, 1024, 1279, 1280 or 1440 (measured by the reviewer).
```

`npx impeccable detect` on the source and both pages at 1280 and 390: nothing reported.

*Review.* The `reviewer` agent confirmed the frame at seven widths, that nothing from the token-holding module reaches the browser, and that the server-rendered page contains the dashboard. One blocking finding, fixed: **on a small screen, Tab could move focus to links hidden behind the open assistant.** It is now a dialog there and the page behind it is inert. Non-blocking, fixed: the page scrolled behind the overlay; "Try again" left the failed entry in the list; a tile's number came before its heading for screen readers; the close button was a small touch target; leftover tokens; four claims in DESIGN.md that no longer matched the code.

**Gate: passed.**

*Third entry, 17 Nov 2026: made to explain itself, and raised.* Writing a narrated explainer for someone who had never seen the app showed what the page did not say for itself. The human then asked for those gaps to be closed and for the interface to be looked at again against the standard of a major company's product, without being bound by earlier decisions. With the human's agreement this pass also changed backend wording (the prompt) and added tests.

*For a stranger.* One plain line at the top of the dashboard, linking to a new About view (the problem, the method, the eval results, the source). The assistant's empty state says "An assistant that cannot make a number up" and offers a question it should refuse next to the three it can answer. "Seeded" became "made-up"; "one headline number per tool" became "one number per tool". The model is told to write dates, time ranges and event names the way a person would.

*For finish.* A header that stays in reach. Four lead figures without boxes. Tiles with half the text. With a live model, a tile is a button that asks the assistant about that tool. "Not showing up" as its own card. The long table starts at eight rows. Links dim between the press and the new view. The assistant slides in when it opens over the page. Page titles, and an icon in the browser tab.

*What the eval caught.* The reworded prompt took the live score from 100% to 92% (run 6). Both causes were the number check refusing correct answers that used the new wording: a span of days written once ("17 to 23 October"), and "all eight tools", a number the model took from its instructions. Both fixed with tests; run 7 scored 100%. The `reviewer` agent then found the first fix too loose: any two dates in a result made a span, so in an answer about people an invented count could pass in front of a real date ("28 – 30 October"). Narrowed to a window's own first and last day, with a test; run 8 scored 100%. Details in `docs/eval-results.md`.

*Review of this pass.* Four blocking findings, all fixed: the loose span rule above; ARCHITECTURE not describing the new rule; a tile on a small screen opening the assistant as a dialog without moving focus into it; and two stale claims on the About view. Non-blocking, fixed: a tile's question was dropped if another was still being answered (it now waits in the field); the tile's spoken name now contains its visible hint; anchors no longer scroll under the header.

*Evidence.*

```
$ make check
All checks passed!
Success: no issues found in 23 source files
336 passed
| all | 40 | 40 | 100% |
 Test Files  6 passed (6)
      Tests  53 passed (53)
$ echo $?
0

$ make evals
| all | 40 | 40 | 100% | 120 of 120 |
Failures (any run):
None.
```

Screenshots: 156 in demo mode (26 states) and 36 live. `npx impeccable detect` on the source and on all three views at 1280 and 390: nothing reported (its first run on About flagged lines of about 89 characters; the reading width is now about 70). Keyboard and overlay checks as in the second entry, all passing, plus: nothing takes focus on load at 375, 768 or 1280; "Show all" takes the table from 8 visible rows to 40.

An explainer video is produced by `frontend/scripts/explainer.mjs`: it drives the live app, speaks each scene and captions it. It is written to `screenshots/explainer.mp4`, which is not tracked.

*What the video caught.* A frame from the first recording showed the answer's headline number as 24. The model had written "the last 7 days (24 to 30 October 2026)" and the page took the first day of that span as the number. The page's answer reader now treats a span of days as a date, with a test built from that sentence; six varied live questions then gave the right headline each time (10, 382, 91, 2, 21, 632). The recording was also changed so that a line describing an answer is spoken only once the answer is on screen.

**Gate: passed.**
