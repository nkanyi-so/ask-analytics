"""File-backed source: reads the seeded `data/events.jsonl`."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.sources.base import Client, Event, Tool, User, Workspace


class FileEventSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Workspace:
        as_of: date | None = None
        clients: list[Client] = []
        tools: list[Tool] = []
        users: list[User] = []
        events: list[Event] = []
        with self._path.open() as lines:
            for line in lines:
                record: dict[str, Any] = json.loads(line)
                match record.pop("kind"):
                    case "meta":
                        as_of = date.fromisoformat(record["as_of"])
                    case "client":
                        clients.append(Client(**record))
                    case "tool":
                        tools.append(Tool(**record))
                    case "user":
                        invited_at = date.fromisoformat(record.pop("invited_at"))
                        users.append(User(invited_at=invited_at, **record))
                    case "event":
                        ts = datetime.fromisoformat(record.pop("ts"))
                        events.append(Event(ts=ts, **record))
                    case kind:
                        raise ValueError(f"{self._path}: unknown record kind {kind!r}")
        if as_of is None:
            raise ValueError(f"{self._path}: no meta line, so AS_OF is unknown")
        return Workspace(as_of, tuple(clients), tuple(tools), tuple(users), tuple(events))
