"""SQLite schema and the one-time load from an event source.

Plain SQLAlchemy Core, nothing SQLite-specific, so moving to Postgres is a connection
string (docs/decisions/0001-sqlite-for-the-demo.md).
"""

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import (
    Column,
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

from app.sources.base import EventSource

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


def load_database(source: EventSource) -> Database:
    """Read a source once and hold it in an in-memory SQLite database."""
    if sqlite3.threadsafety != 3:
        # 3 means "serialized": one connection may be used from several threads.
        raise RuntimeError("This Python's SQLite is not built for sharing a connection.")
    workspace = source.load()
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
            connection.execute(table.insert(), [asdict(row) for row in rows])
    return Database(engine=engine, as_of=workspace.as_of)
