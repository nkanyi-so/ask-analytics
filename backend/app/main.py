"""FastAPI app. Routes stay thin: every number comes from `lookups.py`."""

import ipaddress
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.assistant import MAX_MODEL_TURNS, AskResult, answer_question
from app.cache import TTLCache
from app.config import EVALS_DIR, Settings, get_settings
from app.db import load_database
from app.limits import DailyBudget, RateLimiter
from app.llm import (
    AnthropicClient,
    FixtureClient,
    ModelClient,
    ModelUnavailable,
    load_fixtures,
    worst_case_call_usd,
)
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


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AskResponse(AskResult):
    # True when answers are recorded fixtures because no live model is connected.
    demo_mode: bool


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


def configure_logging() -> None:
    """Send the app's own log lines (cost and latency per model call) to stderr."""
    logger = logging.getLogger("ask_analytics")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def visitor_of(request: Request) -> str:
    """Who is asking, for the rate limit.

    Only the frontend's server calls this API, so the socket address is always the
    same. The frontend sets X-Forwarded-For to the visitor's address as its platform
    reports it. The header is trusted only because this runs after the admin-token
    check. If it holds a list, the last entry is used: that is the one the nearest
    proxy added, and the earlier ones are whatever the browser claimed.
    """
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
    address = forwarded or (request.client.host if request.client else "unknown")
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return address
    if parsed.version == 6:
        # One IPv6 customer holds a whole /64 and could otherwise rotate through it.
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return address


def build_model_client(settings: Settings) -> ModelClient:
    if settings.demo_mode:
        # No key: recorded answers only. Never for a deployed build (Phase 6 enforces it).
        return FixtureClient(load_fixtures(EVALS_DIR / "fixtures.json"))
    # Raises at startup if the model has no price: a budget cannot count an unpriced model.
    return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging()
    # Read the source once; every request after this reads the in-memory database.
    database = load_database(build_source(settings))
    app.state.database = database
    app.state.lookups = Lookups(database, TTLCache())
    if app.state.model_client is None:
        app.state.model_client = build_model_client(settings)
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

    @router.post("/ask")
    def ask(body: AskRequest, request: Request, lookups: Data) -> AskResponse:
        state = request.app.state
        client: ModelClient = state.model_client
        budget: DailyBudget = state.budget
        if not state.rate_limiter.allow(visitor_of(request)):
            raise HTTPException(429, "Too many questions. Wait a minute and try again.")
        # Hold the worst case before calling the model, so a burst cannot overshoot.
        call_estimate = worst_case_call_usd(client.model)
        estimate = MAX_MODEL_TURNS * call_estimate
        if not budget.reserve(estimate):
            raise HTTPException(429, "The demo has used its budget for today. Ask again tomorrow.")
        spent: list[float] = []
        try:
            result = answer_question(body.question, client, lookups, on_cost=spent.append)
        except ModelUnavailable as error:
            # A call that failed or timed out may still be billed; assume it was.
            spent.append(call_estimate)
            raise HTTPException(503, "The assistant is unavailable right now.") from error
        finally:
            budget.settle(estimate, sum(spent))
        return AskResponse(**result.model_dump(), demo_mode=isinstance(client, FixtureClient))

    return router


def create_app(
    settings: Settings | None = None, model_client: ModelClient | None = None
) -> FastAPI:
    # No /docs or /openapi.json: only the frontend's server calls this API, and a
    # public deployment has no reason to publish its shape.
    app = FastAPI(
        title="ask-analytics", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = settings or get_settings()
    # None means "build it at startup from the settings"; tests pass their own.
    app.state.model_client = model_client
    app.state.rate_limiter = RateLimiter(app.state.settings.ask_rate_per_minute)
    app.state.budget = DailyBudget(app.state.settings.ask_daily_budget_usd)
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
