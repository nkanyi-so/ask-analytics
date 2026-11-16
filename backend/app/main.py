"""FastAPI app. Routes stay thin: every number comes from `lookups.py`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import load_database
from app.sources import build_source


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Read the source once; every request after this reads the in-memory database.
    app.state.database = load_database(build_source(get_settings()))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ask-analytics", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
