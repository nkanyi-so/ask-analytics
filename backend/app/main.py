"""FastAPI app. Routes stay thin: every number comes from `lookups.py`."""

import asyncio
import contextlib
import ipaddress
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
    ActivityOverTime,
    ClientActivity,
    ErrorGroup,
    Lookups,
    PersonActivity,
    Roster,
    ToolUsage,
    Window,
)
from app.sources import build_source
from app.summary import render_summary


class OverviewResponse(BaseModel):
    as_of: date
    window: Window
    usage_by_tool: list[ToolUsage]
    activity_by_person: list[PersonActivity]
    activity_by_client: list[ClientActivity]
    roster: Roster
    # For the charts: activity bucket by bucket, and totals across all tools.
    trend: ActivityOverTime


class ReliabilityResponse(BaseModel):
    as_of: date
    window: Window
    errors: list[ErrorGroup]
    trend: ActivityOverTime


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool


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
    same. The frontend sends the visitor's address in X-Visitor-Address, a header of
    our own: proxies between the two rewrite X-Forwarded-For, which would turn every
    visitor into one. The header is trusted only because this runs after the
    admin-token check, so only the frontend can have set it.
    """
    forwarded = request.headers.get("x-visitor-address", "").strip()
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
        # No key: recorded answers only. Never for a deployed build (check_deployable enforces it).
        return FixtureClient(load_fixtures(EVALS_DIR / "fixtures.json"))
    # Raises at startup if the model has no price: a budget cannot count an unpriced model.
    return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)


MIN_TOKEN_LENGTH = 32
# Shorter than the cache's ten minutes, so a warmed entry never expires between runs.
WARM_EVERY_SECONDS = 300.0


def check_deployable(settings: Settings) -> None:
    """Stop a deployed build that would mislead visitors or be open to them.

    Demo mode answers from recorded fixtures and is for local use only: a public page
    that looks live but is not would be a lie. The other two are what a hosted demo
    is specified to be: a real token, and the file source that needs no analytics keys.
    """
    if not settings.is_deployed:
        return
    problems = []
    if settings.demo_mode:
        problems.append("ANTHROPIC_API_KEY is not set (demo mode is for local use only)")
    if len(settings.admin_token.strip()) < MIN_TOKEN_LENGTH:
        problems.append(f"ADMIN_TOKEN is missing or shorter than {MIN_TOKEN_LENGTH} characters")
    if settings.event_source != "file":
        problems.append("EVENT_SOURCE must be file (the hosted demo reads no analytics service)")
    if problems:
        raise RuntimeError("Refusing to start a deployed build: " + "; ".join(problems) + ".")


async def keep_warm(lookups: Lookups, every_seconds: float) -> None:
    """The scheduled cache warm. One failed run is logged and the next one still happens."""
    while True:
        await asyncio.sleep(every_seconds)
        try:
            await asyncio.to_thread(lookups.warm)
        except Exception:
            logging.getLogger("ask_analytics.warm").exception("cache warm failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging()
    check_deployable(settings)
    # Read the source once; every request after this reads the in-memory database.
    database = load_database(build_source(settings))
    app.state.database = database
    app.state.lookups = Lookups(database, TTLCache())
    if app.state.model_client is None:
        app.state.model_client = build_model_client(settings)
    # Warm now, so the first visitor after a start reads from the cache, then keep it warm.
    app.state.lookups.warm()
    warming = asyncio.create_task(keep_warm(app.state.lookups, app.state.warm_every_seconds))
    yield
    warming.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await warming


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
            trend=lookups.activity_over_time(window),
        )

    @router.get("/reliability")
    def reliability(window: Window, lookups: Data) -> ReliabilityResponse:
        return ReliabilityResponse(
            as_of=lookups.as_of,
            window=window,
            errors=lookups.errors_seen(window, with_previous=True),
            trend=lookups.activity_over_time(window),
        )

    @router.get("/summary", response_class=HTMLResponse)
    def summary(lookups: Data) -> str:
        # The Monday summary as HTML. Nothing sends it; a scheduler or a person fetches it.
        return render_summary(lookups)

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
    app.state.warm_every_seconds = WARM_EVERY_SECONDS
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
    def health() -> HealthResponse:
        # Public and data-free. `demo_mode` lets the page label recorded answers as such.
        return HealthResponse(status="ok", demo_mode=app.state.settings.demo_mode)

    app.include_router(api_router())
    return app


app = create_app()
