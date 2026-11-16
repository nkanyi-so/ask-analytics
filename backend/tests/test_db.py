from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import func, inspect, select

from app.config import DATA_DIR
from app.db import Database, clients, events, load_database, tools, users
from app.sources.base import Event, Tool, Workspace
from app.sources.file import FileEventSource


@pytest.fixture(scope="module")
def database() -> Database:
    return load_database(FileEventSource(DATA_DIR / "events.jsonl"))


def count(database: Database, table: object) -> int:
    with database.engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()  # type: ignore[arg-type]


def test_every_record_is_loaded(database: Database) -> None:
    workspace = FileEventSource(DATA_DIR / "events.jsonl").load()

    assert database.as_of == date(2026, 10, 30)
    assert count(database, clients) == 6
    assert count(database, tools) == 8
    assert count(database, users) == 40
    assert count(database, events) == len(workspace.events)


def test_events_have_the_indexes_the_lookups_need(database: Database) -> None:
    indexed = {
        tuple(index["column_names"]) for index in inspect(database.engine).get_indexes("events")
    }

    assert {("ts",), ("tool_id", "name"), ("user_id",)} <= indexed


def test_logins_have_no_tool_and_errors_have_a_source(database: Database) -> None:
    with database.engine.connect() as connection:
        logins_with_tool = connection.execute(
            select(func.count()).where(events.c.name == "login", events.c.tool_id.is_not(None))
        ).scalar_one()
        errors_without_source = connection.execute(
            select(func.count()).where(events.c.name == "error", events.c.error_source.is_(None))
        ).scalar_one()

    assert logins_with_tool == 0
    assert errors_without_source == 0


def test_each_load_gets_its_own_database() -> None:
    source = FileEventSource(DATA_DIR / "events.jsonl")

    assert load_database(source).engine is not load_database(source).engine


class FixedSource:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def load(self) -> Workspace:
        return self._workspace


@pytest.fixture(scope="module")
def workspace() -> Workspace:
    return FileEventSource(DATA_DIR / "events.jsonl").load()


def test_a_source_with_a_tool_the_registry_does_not_know_is_rejected(workspace: Workspace) -> None:
    extra = Tool(id="ninth_tool", name="Ninth tool", headline_event="ninth_done")

    with pytest.raises(ValueError, match="registry"):
        load_database(FixedSource(replace(workspace, tools=(*workspace.tools, extra))))


def test_a_source_with_a_different_headline_event_is_rejected(workspace: Workspace) -> None:
    first, *rest = workspace.tools
    changed = replace(first, headline_event="something_else")

    with pytest.raises(ValueError, match="registry"):
        load_database(FixedSource(replace(workspace, tools=(changed, *rest))))


def test_an_error_event_without_a_tool_or_source_is_rejected(workspace: Workspace) -> None:
    error = next(event for event in workspace.events if event.name == "error")
    for broken in (replace(error, tool_id=None), replace(error, error_source=None)):
        with pytest.raises(ValueError, match="Error event"):
            load_database(FixedSource(replace(workspace, events=(broken,))))


def test_an_event_on_an_unknown_tool_is_rejected(workspace: Workspace) -> None:
    stray = Event(1, workspace.events[0].ts, "u001", "c01", "mystery_tool", "tool_opened", None)

    with pytest.raises(ValueError, match="unknown tool"):
        load_database(FixedSource(replace(workspace, events=(stray,))))


def test_a_source_with_no_events_yet_still_loads(workspace: Workspace) -> None:
    database = load_database(FixedSource(replace(workspace, events=())))

    assert count(database, events) == 0
    assert count(database, users) == 40
