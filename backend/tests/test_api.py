from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import ModelReply, ModelUnavailable
from app.main import api_router, create_app, visitor_of
from tests.conftest import TEST_TOKEN

AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/api/overview?window=7d", "/api/reliability?window=7d"])
def test_data_routes_need_the_token(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(path, headers={"Authorization": TEST_TOKEN}).status_code == 401
    assert client.get(path, headers=AUTH).status_code == 200


def test_unauthorised_reply_carries_no_data(client: TestClient) -> None:
    response = client.get("/api/overview?window=7d")

    assert response.json() == {"detail": "Missing or invalid admin token."}


def test_an_unset_admin_token_lets_nobody_in() -> None:
    # An empty configured token must not match an empty bearer value.
    unset = Settings(_env_file=None, admin_token="")
    with TestClient(create_app(unset)) as client:
        for header in ({"Authorization": "Bearer "}, {"Authorization": "Bearer"}, {}):
            assert client.get("/api/overview?window=7d", headers=header).status_code == 401


def test_health_needs_no_token(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_overview_is_the_lookups_and_nothing_else(
    client: TestClient, truth: dict[str, Any]
) -> None:
    body = client.get("/api/overview?window=7d", headers=AUTH).json()

    assert body["as_of"] == truth["as_of"]
    assert body["window"] == "7d"
    for name in ("usage_by_tool", "activity_by_person", "activity_by_client", "roster"):
        assert body[name] == truth["lookups"][name]["7d"]
    assert set(body) == {
        "as_of",
        "window",
        "usage_by_tool",
        "activity_by_person",
        "activity_by_client",
        "roster",
    }


def test_reliability_is_errors_seen(client: TestClient, truth: dict[str, Any]) -> None:
    body = client.get("/api/reliability?window=30d", headers=AUTH).json()

    assert body == {
        "as_of": truth["as_of"],
        "window": "30d",
        "errors": truth["lookups"]["errors_seen"]["30d"],
    }


def test_unknown_window_is_rejected(client: TestClient) -> None:
    assert client.get("/api/overview?window=90d", headers=AUTH).status_code == 422
    assert client.get("/api/overview", headers=AUTH).status_code == 422


def test_cors_allows_only_the_frontend_origin(client: TestClient, settings: Settings) -> None:
    allowed = client.get("/health", headers={"Origin": settings.frontend_origin})
    other = client.get("/health", headers={"Origin": "http://elsewhere.test"})

    assert allowed.headers["access-control-allow-origin"] == settings.frontend_origin
    assert "access-control-allow-origin" not in other.headers


def test_every_api_route_refuses_a_request_without_the_token(client: TestClient) -> None:
    # Walks the router's own table, so a route added later is covered without
    # anyone remembering to list it here.
    api_routes = [
        (method, route.path)
        for route in api_router().routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]

    assert len(api_routes) >= 2
    assert all(path.startswith("/api/") for _, path in api_routes)
    for method, path in api_routes:
        assert client.request(method, path).status_code == 401, f"{method} {path}"


def test_health_is_the_only_route_outside_the_protected_router(client: TestClient) -> None:
    direct = [route.path for route in client.app.routes if isinstance(route, APIRoute)]  # type: ignore[attr-defined]

    assert direct == ["/health"]


def test_the_token_is_checked_before_the_query_is_validated(client: TestClient) -> None:
    assert client.get("/api/overview?window=90d").status_code == 401


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_not_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


# --- /api/ask ------------------------------------------------------------------------


class CostlyClient:
    """Refuses everything, and bills like a real model while doing it."""

    model = "claude-opus-5-5"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    def cannot_answer(self, question: str) -> str | None:
        return None

    def complete(self, system: str, tools: list[Any], messages: list[Any]) -> ModelReply:
        self.calls += 1
        if self._fail:
            raise ModelUnavailable("APITimeoutError")
        return ModelReply(
            text="REFUSE",
            tool_calls=(),
            stop_reason="end_turn",
            input_tokens=2000,
            output_tokens=500,
        )


def ask(client: TestClient, question: str, visitor: str = "203.0.113.7") -> Any:
    headers = {**AUTH, "X-Forwarded-For": visitor}
    return client.post("/api/ask", json={"question": question}, headers=headers)


def test_ask_needs_the_token(client: TestClient) -> None:
    assert client.post("/api/ask", json={"question": "anything"}).status_code == 401


def test_demo_mode_answers_a_recorded_question_and_says_it_is_a_demo(
    client: TestClient, truth: dict[str, Any]
) -> None:
    invoices = next(
        row["headline_count"]
        for row in truth["lookups"]["usage_by_tool"]["7d"]
        if row["tool_id"] == "invoice_generator"
    )

    body = ask(client, "How many invoices were issued in the last 7 days?").json()

    assert body["demo_mode"] is True
    assert body["refused"] is False
    assert body["answer"] == f"In the last 7 days, {invoices} invoices were issued."
    assert body["window"] == "7d"
    assert [call["name"] for call in body["lookups_called"]] == ["usage_by_tool"]
    assert set(body) == {
        "answer",
        "window",
        "lookups_called",
        "refused",
        "latency_ms",
        "cost_usd",
        "demo_mode",
    }


def test_demo_mode_says_so_for_a_question_it_has_no_recording_for(client: TestClient) -> None:
    body = ask(client, "What is the meaning of life?").json()

    assert body["demo_mode"] is True
    assert body["refused"] is True
    assert "live model is not connected" in body["answer"]


def test_a_live_client_is_not_demo_mode(settings: Settings) -> None:
    with TestClient(create_app(settings, model_client=CostlyClient())) as client:
        assert ask(client, "anything").json()["demo_mode"] is False


def test_rate_limit_is_per_visitor_and_returns_a_clear_message(settings: Settings) -> None:
    limited = settings.model_copy(update={"ask_rate_per_minute": 2})
    with TestClient(create_app(limited)) as client:
        statuses = [ask(client, "Who has gone quiet?").status_code for _ in range(3)]
        blocked = ask(client, "Who has gone quiet?")
        other_visitor = ask(client, "Who has gone quiet?", visitor="198.51.100.9")

    assert statuses == [200, 200, 429]
    assert blocked.json() == {"detail": "Too many questions. Wait a minute and try again."}
    assert other_visitor.status_code == 200


def test_daily_budget_stops_the_endpoint_before_the_model_is_called(settings: Settings) -> None:
    # On this client one refusal costs 2000 * $4/M + 500 * $20/M = $0.018, and the worst
    # case reserved per question is 5 calls * (15000 * $4/M + 4096 * $20/M) = $0.7096.
    # With $0.73 a day: 0 + 0.7096 fits, 0.018 + 0.7096 fits, 0.036 + 0.7096 does not.
    capped = settings.model_copy(update={"ask_daily_budget_usd": 0.73, "ask_rate_per_minute": 100})
    model = CostlyClient()
    with TestClient(create_app(capped, model_client=model)) as client:
        first = ask(client, "one")
        second = ask(client, "two")
        third = ask(client, "three")
        spent = client.app.state.budget.spent_usd  # type: ignore[attr-defined]

    assert first.json()["cost_usd"] == pytest.approx(0.018)
    assert (first.status_code, second.status_code, third.status_code) == (200, 200, 429)
    assert third.json() == {"detail": "The demo has used its budget for today. Ask again tomorrow."}
    assert model.calls == 2, "the third question never reached the model"
    assert spent == pytest.approx(0.036)


def test_a_question_that_cannot_fit_its_worst_case_is_not_started(settings: Settings) -> None:
    # $0.03 would cover one cheap answer, but nothing guarantees the answer is cheap.
    tight = settings.model_copy(update={"ask_daily_budget_usd": 0.03})
    model = CostlyClient()
    with TestClient(create_app(tight, model_client=model)) as client:
        assert ask(client, "one").status_code == 429
    assert model.calls == 0


def test_a_failed_model_call_is_still_charged_to_the_budget(settings: Settings) -> None:
    with TestClient(create_app(settings, model_client=CostlyClient(fail=True))) as client:
        assert ask(client, "anything").status_code == 503
        spent = client.app.state.budget.spent_usd  # type: ignore[attr-defined]

    # One worst-case call: 15000 * $4/M + 4096 * $20/M.
    assert spent == pytest.approx(0.14192)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("198.51.100.1, 203.0.113.7", "203.0.113.7"),
        ("2001:db8:1:2:aaaa:bbbb:cccc:dddd", "2001:db8:1:2::/64"),
        ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
        ("not-an-address", "not-an-address"),
    ],
)
def test_visitor_key(header: str, expected: str) -> None:
    request = Request({"type": "http", "headers": [(b"x-forwarded-for", header.encode())]})

    assert visitor_of(request) == expected


def test_a_browser_supplied_forwarded_entry_does_not_dodge_the_rate_limit(
    settings: Settings,
) -> None:
    limited = settings.model_copy(update={"ask_rate_per_minute": 1})
    with TestClient(create_app(limited)) as client:
        first = ask(client, "Who has gone quiet?", visitor="10.0.0.1, 203.0.113.7")
        second = ask(client, "Who has gone quiet?", visitor="10.9.9.9, 203.0.113.7")

    assert (first.status_code, second.status_code) == (200, 429)


def test_a_model_failure_is_reported_not_guessed(settings: Settings) -> None:
    with TestClient(create_app(settings, model_client=CostlyClient(fail=True))) as client:
        response = ask(client, "anything")

    assert response.status_code == 503
    assert response.json() == {"detail": "The assistant is unavailable right now."}


@pytest.mark.parametrize("question", ["", "x" * 501])
def test_empty_and_oversized_questions_are_rejected(client: TestClient, question: str) -> None:
    assert ask(client, question).status_code == 422


def test_an_unpriced_model_stops_a_live_app_from_starting() -> None:
    live = Settings(
        _env_file=None,
        admin_token=TEST_TOKEN,
        anthropic_api_key="not-a-real-key",
        anthropic_model="claude-made-up-9",
    )

    with pytest.raises(ValueError, match="no price"), TestClient(create_app(live)):
        pass
