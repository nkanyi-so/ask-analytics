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


def test_each_argument_is_part_of_the_cache_key(database: Database) -> None:
    lookups = Lookups(database, TTLCache(ttl_seconds=600, clock=FakeClock()))
    statements = count_queries(database)

    def runs_new_queries(call: Any) -> Any:
        before = len(statements)
        result = call()
        assert len(statements) > before, "served from another call's cache entry"
        return result

    plain = runs_new_queries(lambda: lookups.usage_by_tool("7d"))
    assert plain[0].headline_count_previous is None
    compared = runs_new_queries(lambda: lookups.usage_by_tool("7d", with_previous=True))
    assert compared[0].headline_count_previous is not None
    month = runs_new_queries(lambda: lookups.usage_by_tool("30d"))
    assert month != plain

    everyone = runs_new_queries(lambda: lookups.activity_by_person("7d"))
    one = runs_new_queries(lambda: lookups.activity_by_person("7d", user_id="u001"))
    assert (len(everyone), len(one)) == (40, 1)

    all_errors = runs_new_queries(lambda: lookups.errors_seen("7d"))
    one_tool = runs_new_queries(lambda: lookups.errors_seen("7d", tool_id="invoice_generator"))
    assert len(all_errors) > len(one_tool) == 1


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


def test_expired_entries_are_dropped_and_the_cache_is_capped() -> None:
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=600, clock=clock)

    for index in range(10):
        cache.get_or_compute(("old", index), lambda: 0)
    clock.now = 601.0
    cache.get_or_compute(("new",), lambda: 0)
    assert len(cache) == 1

    for index in range(2000):
        cache.get_or_compute(("flood", index), lambda: 0)
    assert len(cache) <= 512
