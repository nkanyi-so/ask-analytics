from typing import Any

from sqlalchemy import event

from app.cache import TTLCache
from app.db import Database
from app.lookups import Lookups


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def count_queries(database: Database) -> list[str]:
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", record)
    return statements


def test_cached_call_does_not_hit_the_database_twice(database: Database) -> None:
    lookups = Lookups(database, TTLCache(ttl_seconds=600, clock=FakeClock()))
    statements = count_queries(database)

    first = lookups.usage_by_tool("7d")
    after_first = len(statements)
    second = lookups.usage_by_tool("7d")

    assert after_first > 0
    assert len(statements) == after_first
    assert second == first


def test_different_arguments_are_cached_separately(database: Database) -> None:
    lookups = Lookups(database, TTLCache(ttl_seconds=600, clock=FakeClock()))
    statements = count_queries(database)

    lookups.usage_by_tool("7d")
    after_first = len(statements)
    lookups.usage_by_tool("30d")
    lookups.usage_by_tool("7d", with_previous=True)
    lookups.errors_seen("7d", tool_id="invoice_generator")

    assert len(statements) > after_first
    assert lookups.usage_by_tool("7d") != lookups.usage_by_tool("30d")


def test_entry_expires_after_ten_minutes(database: Database) -> None:
    clock = FakeClock()
    lookups = Lookups(database, TTLCache(ttl_seconds=600, clock=clock))
    statements = count_queries(database)

    lookups.roster("7d")
    after_first = len(statements)
    clock.now = 599.0
    lookups.roster("7d")
    assert len(statements) == after_first

    clock.now = 601.0
    lookups.roster("7d")
    assert len(statements) > after_first


def test_cache_computes_once_per_key() -> None:
    cache = TTLCache(ttl_seconds=600, clock=FakeClock())
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return 42

    assert cache.get_or_compute(("k",), compute) == 42
    assert cache.get_or_compute(("k",), compute) == 42
    assert len(calls) == 1
