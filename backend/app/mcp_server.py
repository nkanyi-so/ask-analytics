"""The five lookups as an MCP server over stdio: `python -m app.mcp_server`.

It offers exactly what the assistant has: the same tool definitions, the same argument
check and the same lookups (`TOOL_SPECS` and `run_lookup` in assistant.py). So an MCP
client gets the numbers the dashboard shows, and nothing here computes anything.

There is no token: stdio means the server is a child process of the client on the
same machine, which can already read the data file. The tools only read.
"""

import json
from typing import Any

import anyio
from mcp import stdio_server
from mcp.server import Server, ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)

from app.assistant import TOOL_SPECS, ToolError, run_lookup
from app.cache import TTLCache
from app.config import get_settings
from app.db import load_database
from app.lookups import Lookups
from app.sources import build_source

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def tools() -> list[Tool]:
    return [
        Tool(
            name=spec["name"],
            description=spec["description"],
            input_schema=spec["input_schema"],
            annotations=READ_ONLY,
        )
        for spec in TOOL_SPECS
    ]


def build_server(lookups: Lookups) -> Server[Any]:
    async def list_tools(
        ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(tools=tools())

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        try:
            _, text = run_lookup(lookups, params.name, params.arguments or {})
        except ToolError as error:
            # Told to the client's model as a tool error, so it can correct the call.
            return CallToolResult(
                content=[TextContent(type="text", text=str(error))], is_error=True
            )
        return CallToolResult(
            content=[TextContent(type="text", text=text)], structured_content=json.loads(text)
        )

    return Server(
        "ask-analytics",
        instructions=(
            "Usage numbers for a seeded demo workspace of eight tools and forty people. "
            f"The data ends on {lookups.as_of.isoformat()}; windows end on that day. "
            "Every number must be copied from a tool result. To compare with the period "
            "before, set with_previous to true rather than subtracting."
        ),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve() -> None:
    lookups = Lookups(load_database(build_source(get_settings())), TTLCache())
    server = build_server(lookups)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(serve)
