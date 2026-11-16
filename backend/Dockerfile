# The API image. Build from the repo root, because the seeded data lives there:
#   docker build -f backend/Dockerfile -t ask-analytics-api .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.4 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/backend/.venv/bin:$PATH" \
    # Marks this as a deployed build: it refuses to start in demo mode, without a real
    # admin token, or on any source but the file. See check_deployable in app/main.py.
    DEPLOYED=1

WORKDIR /srv/backend

# Dependencies first, so a code change does not reinstall them. Runtime packages only:
# no test tools and no MCP SDK, which the API never imports.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
# No cache kept: it would double the size of this layer.
RUN uv sync --locked --no-default-groups --no-cache

COPY backend/app ./app
# No recorded answers in the image: only demo mode reads them, and this build refuses it.
COPY data/events.jsonl /srv/data/events.jsonl

RUN useradd --system --no-create-home api
USER api

EXPOSE 8000
# The platform injects PORT; 8000 is for running the image by hand.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
