from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
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
