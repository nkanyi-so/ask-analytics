.PHONY: setup seed dev check evals mixpanel-push mcp

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

# Sends the seeded workspace to the Mixpanel project named in .env. Writes to an
# outside service: only run it yourself, on a project that holds nothing else.
mixpanel-push:
	cd backend && uv run python -m app.sources.mixpanel_push

# The MCP server over stdio, for a quick look. Claude Desktop starts it itself: docs/mcp.md.
mcp:
	cd backend && uv run python -m app.mcp_server
