"""An MCP client sees the five lookups, and a call returns what the API returns."""

import json
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp import Client, StdioServerParameters

from app.assistant import TOOL_SPECS
from app.cache import TTLCache
from app.config import Settings
from app.db import Database
from app.lookups import Lookups
from app.main import create_app
from app.mcp_server import build_server
from tests.conftest import TEST_TOKEN

BACKEND = Path(__file__).resolve().parents[1]
FIVE = ["usage_by_tool", "activity_by_person", "activity_by_client", "errors_seen", "roster"]
ARGUMENTS = {"window": "7d", "with_previous": True}


def api_overview(settings: Settings) -> dict[str, Any]:
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/overview?window=7d", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
    body: dict[str, Any] = response.json()
    return body


def without_nulls(row: dict[str, Any]) -> dict[str, Any]:
    # Tool results leave out empty fields; the API spells them as null.
    return {key: value for key, value in row.items() if value is not None}


def test_a_client_lists_the_five_lookups_with_the_assistants_schemas(database: Database) -> None:
    async def run() -> None:
        async with Client(build_server(Lookups(database, TTLCache()))) as client:
            listed = (await client.list_tools()).tools
        assert [tool.name for tool in listed] == FIVE
        for tool, spec in zip(listed, TOOL_SPECS, strict=True):
            assert tool.input_schema == spec["input_schema"]
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True

    anyio.run(run)


def test_a_bad_call_is_a_tool_error_not_a_crash(database: Database) -> None:
    async def run() -> None:
        async with Client(build_server(Lookups(database, TTLCache()))) as client:
            wrong_window = await client.call_tool("usage_by_tool", {"window": "90d"})
            unknown = await client.call_tool("raw_events", {"window": "7d"})
        assert wrong_window.is_error is True
        assert unknown.is_error is True
        assert "Unknown tool" in unknown.content[0].text  # type: ignore[union-attr]

    anyio.run(run)


@pytest.mark.parametrize("name", ["usage_by_tool", "activity_by_person", "activity_by_client"])
def test_a_call_in_process_returns_what_the_api_returns(
    database: Database, settings: Settings, name: str
) -> None:
    async def run() -> dict[str, Any]:
        async with Client(build_server(Lookups(database, TTLCache()))) as client:
            result = await client.call_tool(name, ARGUMENTS)
        assert result.is_error is not True
        structured: dict[str, Any] = result.structured_content
        assert json.loads(result.content[0].text) == structured  # type: ignore[union-attr]
        return structured

    structured = anyio.run(run)

    assert structured["rows"] == [without_nulls(row) for row in api_overview(settings)[name]]
    assert structured["as_of"] == "2026-10-30"


def test_the_real_server_over_stdio_lists_five_tools_and_matches_the_api(
    settings: Settings,
) -> None:
    """The server end to end: a separate process, spoken to over stdin and stdout."""
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(BACKEND),
        # The child gets a bare environment. Pin the file source so a local .env that
        # points at Mixpanel can never make a test reach an outside service.
        env={"EVENT_SOURCE": "file"},
    )

    async def run() -> tuple[list[str], dict[str, Any]]:
        async with Client(server) as client:
            names = [tool.name for tool in (await client.list_tools()).tools]
            result = await client.call_tool("usage_by_tool", ARGUMENTS)
        structured: dict[str, Any] = result.structured_content
        return names, structured

    names, structured = anyio.run(run)

    assert names == FIVE
    assert structured["rows"] == [
        without_nulls(row) for row in api_overview(settings)["usage_by_tool"]
    ]
