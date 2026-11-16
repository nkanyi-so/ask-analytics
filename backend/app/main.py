"""FastAPI app. Routes stay thin: every number comes from `lookups.py`."""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.cache import TTLCache
from app.config import Settings, get_settings
from app.db import load_database
from app.lookups import (
    ClientActivity,
    ErrorGroup,
    Lookups,
    PersonActivity,
    Roster,
    ToolUsage,
    Window,
)
from app.sources import build_source


class OverviewResponse(BaseModel):
    as_of: date
    window: Window
    usage_by_tool: list[ToolUsage]
    activity_by_person: list[PersonActivity]
    activity_by_client: list[ClientActivity]
    roster: Roster


class ReliabilityResponse(BaseModel):
    as_of: date
    window: Window
    errors: list[ErrorGroup]


def token_is_valid(authorization: str | None, admin_token: str) -> bool:
    if not admin_token:
        # An unset token must lock everyone out, not match an empty bearer value.
        return False
    scheme, _, presented = (authorization or "").partition(" ")
    if scheme != "Bearer":
        return False
    # Constant time, so the response time says nothing about how close a guess was.
    return secrets.compare_digest(presented.encode(), admin_token.encode())


def require_admin(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
    settings: Settings = request.app.state.settings
    if not token_is_valid(authorization, settings.admin_token):
        raise HTTPException(status_code=401, detail="Missing or invalid admin token.")


def get_lookups(request: Request) -> Lookups:
    lookups: Lookups = request.app.state.lookups
    return lookups


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Read the source once; every request after this reads the in-memory database.
    database = load_database(build_source(app.state.settings))
    app.state.database = database
    app.state.lookups = Lookups(database, TTLCache())
    yield


def api_router() -> APIRouter:
    # The token check sits on the router, so a route added here cannot forget it.
    router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])
    Data = Annotated[Lookups, Depends(get_lookups)]

    @router.get("/overview")
    def overview(window: Window, lookups: Data) -> OverviewResponse:
        return OverviewResponse(
            as_of=lookups.as_of,
            window=window,
            usage_by_tool=lookups.usage_by_tool(window, with_previous=True),
            activity_by_person=lookups.activity_by_person(window, with_previous=True),
            activity_by_client=lookups.activity_by_client(window, with_previous=True),
            roster=lookups.roster(window, with_previous=True),
        )

    @router.get("/reliability")
    def reliability(window: Window, lookups: Data) -> ReliabilityResponse:
        return ReliabilityResponse(
            as_of=lookups.as_of,
            window=window,
            errors=lookups.errors_seen(window, with_previous=True),
        )

    return router


def create_app(settings: Settings | None = None) -> FastAPI:
    # No /docs or /openapi.json: only the frontend's server calls this API, and a
    # public deployment has no reason to publish its shape.
    app = FastAPI(
        title="ask-analytics", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = settings or get_settings()
    # The browser never calls this API (the frontend's server does), so this is a
    # second lock: only the frontend origin, only the methods the API has.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app.state.settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router())
    return app


app = create_app()
