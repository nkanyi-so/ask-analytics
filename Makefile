.PHONY: setup seed dev check evals

setup:
	git config core.hooksPath .githooks
	cd backend && uv sync
	cd frontend && npm ci

# Regenerates data/events.jsonl and data/ground_truth.json from the fixed seed,
# then the eval questions and fixtures that are derived from ground truth.
seed:
	@test -f scripts/seed.py || { echo "seed: scripts/seed.py arrives in Phase 1" >&2; exit 1; }
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

# Live model run: every question three times, table written to docs/eval-results.md.
# Spends API credits: never run without being asked. `make evals MODEL=claude-opus-5-5`
# runs another priced model, so two tables can sit side by side.
evals:
	cd backend && uv run python -m evals.run --live $(if $(MODEL),--model $(MODEL),)
