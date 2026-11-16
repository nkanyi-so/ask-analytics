# The MCP server

The five lookups are also available to any MCP client, over stdio. It is the same code path as the assistant: the same tool definitions, the same argument check, the same lookups. Nothing in the server computes a number.

Tools: `usage_by_tool`, `activity_by_person`, `activity_by_client`, `errors_seen`, `roster`. Each takes `window` (`today`, `7d`, `30d`) and `with_previous`. All are read-only.

## Claude Desktop

Open Settings, then Developer, then "Edit Config". On macOS the file is `~/Library/Application Support/Claude/claude_desktop_config.json`. Add this entry, with the path to your clone, then quit and reopen Claude Desktop:

```json
{
  "mcpServers": {
    "ask-analytics": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/ask-analytics/backend",
        "python",
        "-m",
        "app.mcp_server"
      ]
    }
  }
}
```

If Claude Desktop cannot find `uv`, give its full path as `command` (`which uv` prints it). The server's own log lines go to `~/Library/Logs/Claude/mcp-server-ask-analytics.log`.

The server reads the same `.env` as the backend, so it serves the file source unless `EVENT_SOURCE=mixpanel` is set there.

## What it is not

- It has no token. A stdio server is a child process of the client on your own machine, which can already read `data/events.jsonl`. It is not a network service and must not be exposed as one.
- It does not enforce the assistant's number check. That check lives in this project's own Ask loop; an MCP client's model words its own answer. The server's instructions tell it to copy numbers from tool results and to use `with_previous` instead of subtracting, but nothing can force a client to.

To see it start by hand: `make mcp` (it waits on stdin; Ctrl-C to stop).
