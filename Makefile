.PHONY: setup seed dev check evals evals-heldout browser-test mixpanel-push mcp

setup:
	git config core.hooksPath .githooks
	cd backend && uv sync
	cd frontend && npm ci

# Regenerates data/events.jsonl and data/ground_truth.json from the fixed seed,
# then the eval questions and fixtures that are derived from ground truth.
seed:
	cd backend && uv run python ../scripts/seed.py
	cd backend && uv run python -m evals.build

# Backend on :8000, frontend on :3000. Both read the root .env; the token stays server-side.
dev:
	@test -f .env || { echo "dev: copy .env.example to .env first" >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --port 8000) & \
	(cd frontend && npm run dev -- --port 3000) & \
	wait

check:
	cd backend && uv run ruff format --config pyproject.toml --check . ../scripts
	cd backend && uv run ruff check --config pyproject.toml . ../scripts
	cd backend && uv run mypy
	cd backend && uv run pytest
	cd backend && uv run python -m evals.run
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test
	cd frontend && npm run build

# Live model run: every question three times, table written to docs/EVALS.md.
# Spends API credits: never run without being asked. `make evals MODEL=claude-opus-5-5`
# runs another priced model, so two tables can sit side by side.
evals:
	cd backend && uv run python -m evals.run --live $(if $(MODEL),--model $(MODEL),)

# Live run of the held-out set (backend/evals/questions_heldout.json) on claude-haiku-5-5:
# every question three times, same scorer. Spends API credits: never run without being asked.
# It refuses to run while the prompt, the tool descriptions or the number check (all in
# app/assistant.py; the tool catalog in app/registry.py), the scorer, or the held-out
# questions and their generator differ from the last commit, so a score always belongs to
# a committed assistant, scorer and question set. Never tune on its result.
HELDOUT_GUARDED := backend/app/assistant.py backend/app/registry.py backend/evals/scoring.py \
	backend/evals/questions_heldout.json backend/evals/heldout.py
evals-heldout:
	@test -z "$$(git status --porcelain -- $(HELDOUT_GUARDED))" || { \
		echo "evals-heldout: uncommitted changes to the prompt, the tool descriptions, the number check, the scorer or the held-out questions ($(HELDOUT_GUARDED)). Commit or revert them first." >&2; exit 1; }
	cd backend && uv run python -m evals.run --live --heldout --model claude-haiku-5-5

# One journey in a real Chromium against the app in demo mode: no key, no model call.
# CI's `browser` job runs it. Needs Playwright's Chromium (`npx playwright install chromium`).
browser-test:
	@bash scripts/browser-test.sh

# Sends the seeded workspace to the Mixpanel project named in .env. Writes to an
# outside service: only run it yourself, on a project that holds nothing else.
mixpanel-push:
	cd backend && uv run python -m app.sources.mixpanel_push

# The MCP server over stdio, for a quick look. Claude Desktop starts it itself: docs/mcp.md.
mcp:
	cd backend && uv run python -m app.mcp_server
