"""SQLite schema and the one-time load from an event source.

Plain SQLAlchemy Core, nothing SQLite-specific, so moving to Postgres is a connection
string (docs/decisions/0001-sqlite-for-the-demo.md).
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date

from sqlalchemy import (
    Column,
    Connection,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.pool import StaticPool

from app.registry import CATALOG
from app.sources.base import EventSource, Workspace

metadata = MetaData()

clients = Table(
    "clients",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
)

tools = Table(
    "tools",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("headline_event", String, nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("client_id", String, ForeignKey("clients.id"), nullable=False),
    Column("role", String, nullable=False),
    Column("invited_at", Date, nullable=False),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ts", DateTime, nullable=False),
    Column("user_id", String, ForeignKey("users.id"), nullable=False),
    Column("client_id", String, ForeignKey("clients.id"), nullable=False),
    Column("tool_id", String, ForeignKey("tools.id"), nullable=True),
    Column("name", String, nullable=False),
    Column("error_source", String, nullable=True),
    Index("ix_events_ts", "ts"),
    Index("ix_events_tool_id_name", "tool_id", "name"),
    Index("ix_events_user_id", "user_id"),
)


@dataclass(frozen=True)
class Database:
    """The loaded data and the day it runs up to. `as_of` is "today" for every lookup."""

    engine: Engine
    as_of: date
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """One reader at a time.

        The in-memory database is a single shared connection, and two threads reading
        results from it at once corrupt each other's cursors. Lookups take milliseconds
        and are cached, so waiting in line costs nothing that matters here.
        """
        with self._lock, self.engine.connect() as connection:
            yield connection


def check_workspace(workspace: Workspace) -> None:
    """Refuse data the typed registry or the lookups cannot account for.

    The type check proves every tool in the registry has a headline event. This is
    what extends that proof to the numbers: a source may not bring its own tools.
    """
    in_data = {(tool.id, tool.name, tool.headline_event) for tool in workspace.tools}
    in_registry = {(entry.id, entry.name, entry.headline_event) for entry in CATALOG}
    if in_data != in_registry:
        raise ValueError(f"Tools in the data do not match the registry: {in_data ^ in_registry}")
    tool_ids = {tool.id for tool in workspace.tools}
    for event in workspace.events:
        if event.tool_id is not None and event.tool_id not in tool_ids:
            raise ValueError(f"Event {event.id} names an unknown tool: {event.tool_id!r}")
        if event.name == "error" and (event.tool_id is None or event.error_source is None):
            raise ValueError(f"Error event {event.id} needs both a tool and an error source")


def load_database(source: EventSource) -> Database:
    """Read a source once and hold it in an in-memory SQLite database."""
    if sqlite3.threadsafety != 3:
        # 3 means "serialized": one connection may be used from several threads.
        raise RuntimeError("This Python's SQLite is not built for sharing a connection.")
    workspace = source.load()
    check_workspace(workspace)
    # One shared connection: an in-memory SQLite database lives and dies with its
    # connection, and the API reads it from several threads.
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        for table, rows in (
            (clients, workspace.clients),
            (tools, workspace.tools),
            (users, workspace.users),
            (events, workspace.events),
        ):
            if rows:  # an insert with no rows would add one row of defaults
                connection.execute(table.insert(), [asdict(row) for row in rows])
    return Database(engine=engine, as_of=workspace.as_of)
