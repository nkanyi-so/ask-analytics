"""The Monday summary: last week next to the week before, straight from the lookups."""

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.cache import TTLCache
from app.config import Settings
from app.db import Database
from app.lookups import Lookups
from app.main import create_app
from app.summary import change, render_summary
from tests.conftest import TEST_TOKEN

AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def rows_of(html: str) -> list[list[str]]:
    return [re.findall(r"<td>(.*?)</td>", row) for row in re.findall(r"<tr>(.*?)</tr>", html)]


def test_the_summary_needs_the_token_and_is_html(client: TestClient) -> None:
    assert client.get("/api/summary").status_code == 401

    response = client.get("/api/summary", headers=AUTH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "week ending 2026-10-30" in response.text


def test_every_tool_row_is_ground_truth_for_this_week_and_the_week_before(
    client: TestClient, truth: dict[str, Any]
) -> None:
    rows = rows_of(client.get("/api/summary", headers=AUTH).text)

    for expected in truth["lookups"]["usage_by_tool"]["7d"]:
        assert [
            expected["tool_name"],
            str(expected["headline_count"]),
            str(expected["headline_count_previous"]),
            change(expected["headline_count_change"]),
            str(expected["active_people"]),
            str(expected["errors"]),
        ] in rows


def test_people_and_errors_come_from_the_roster_and_errors_lookups(
    client: TestClient, truth: dict[str, Any]
) -> None:
    html = client.get("/api/summary", headers=AUTH).text
    rows = rows_of(html)
    roster = truth["lookups"]["roster"]["7d"]
    worst = truth["lookups"]["errors_seen"]["7d"][0]

    assert [
        "Active",
        str(roster["active_count"]),
        str(roster["active_count_previous"]),
        change(roster["active_count_change"]),
    ] in rows
    assert f"Never showed up: {roster['never_showed_up_count']} (" in html
    for person in roster["never_showed_up"] + roster["went_quiet"]:
        assert person["name"] in html
    assert [
        worst["source"],
        worst["tool_name"],
        str(worst["count"]),
        str(worst["count_previous"]),
        change(worst["count_change"]),
        str(worst["people_affected"]),
    ] in rows


def test_a_change_is_worded_not_recomputed() -> None:
    assert change(5) == "+5"
    assert change(-41) == "-41"
    assert change(0) == "no change"
    assert change(None) == "no earlier data"


def test_names_are_escaped(database: Database) -> None:
    class Hostile(Lookups):
        def usage_by_tool(self, window: Any, with_previous: bool = False) -> Any:
            rows = super().usage_by_tool(window, with_previous)
            return [rows[0].model_copy(update={"tool_name": "<script>x</script>"}), *rows[1:]]

    html = render_summary(Hostile(database, TTLCache()))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
