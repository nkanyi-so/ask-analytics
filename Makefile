.PHONY: setup seed dev check evals

setup:
	cd backend && uv sync
	cd frontend && npm ci

# Regenerates data/events.jsonl and data/ground_truth.json from the fixed seed.
seed:
	@test -f scripts/seed.py || { echo "seed: scripts/seed.py arrives in Phase 1" >&2; exit 1; }
	cd backend && uv run python ../scripts/seed.py

# Backend on :8000, frontend on :3000. Both read the root .env; the token stays server-side.
dev:
	@test -f .env || { echo "dev: copy .env.example to .env first" >&2; exit 1; }
	@set -a; . ./.env; set +a; \
	trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --port 8000) & \
	(cd frontend && npm run dev -- --port 3000) & \
	wait

check:
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run mypy
	cd backend && uv run pytest
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test

# Live model run. Spends API credits: never run without being asked.
evals:
	@test -f backend/evals/run.py || { echo "evals: backend/evals/run.py arrives in Phase 3" >&2; exit 1; }
	cd backend && uv run python -m evals.run --live
