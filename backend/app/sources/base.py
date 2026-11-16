"""The one interface every event source sits behind.

Nothing outside this package knows whether events come from a file or from Mixpanel.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Client:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Tool:
    id: str
    name: str
    headline_event: str


@dataclass(frozen=True, slots=True)
class User:
    id: str
    name: str
    client_id: str
    role: str
    invited_at: date


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    ts: datetime
    user_id: str
    client_id: str
    tool_id: str | None
    name: str
    error_source: str | None


@dataclass(frozen=True, slots=True)
class Workspace:
    """Everything a source knows: who exists, what happened, and what day it is."""

    as_of: date
    clients: tuple[Client, ...]
    tools: tuple[Tool, ...]
    users: tuple[User, ...]
    events: tuple[Event, ...]


class EventSource(Protocol):
    def load(self) -> Workspace: ...
