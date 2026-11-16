"""Every lookup, in every window, must equal ground truth exactly.

Ground truth is computed by scripts/seed.py with plain Python loops; the lookups are SQL.
Agreement between the two is the evidence that the numbers are right.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from pydantic import BaseModel

from app import lookups
from app.db import Database
from app.lookups import WINDOWS, Window

Row = dict[str, Any]


def dump(result: BaseModel | list[Any]) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return [row.model_dump(mode="json") for row in result]


def without_previous(row: Row) -> Row:
    """What a row looks like when the caller did not ask for the previous window."""
    return {
        key: None if key.endswith(("_previous", "_change")) else value for key, value in row.items()
    }


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize(
    "name", ["usage_by_tool", "activity_by_person", "activity_by_client", "errors_seen", "roster"]
)
def test_lookup_with_previous_equals_ground_truth(
    database: Database, truth: dict[str, Any], name: str, window: Window
) -> None:
    result = getattr(lookups, name)(database, window, with_previous=True)

    assert dump(result) == truth["lookups"][name][window]


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("name", ["usage_by_tool", "activity_by_person", "activity_by_client"])
def test_lookup_without_previous_equals_ground_truth(
    database: Database, truth: dict[str, Any], name: str, window: Window
) -> None:
    result = getattr(lookups, name)(database, window)

    assert dump(result) == [without_previous(row) for row in truth["lookups"][name][window]]


@pytest.mark.parametrize("window", WINDOWS)
def test_errors_without_previous_lists_only_groups_with_errors(
    database: Database, truth: dict[str, Any], window: Window
) -> None:
    expected = [
        without_previous(row) for row in truth["lookups"]["errors_seen"][window] if row["count"] > 0
    ]

    assert dump(lookups.errors_seen(database, window)) == expected


@pytest.mark.parametrize("window", WINDOWS)
def test_roster_without_previous_equals_ground_truth(
    database: Database, truth: dict[str, Any], window: Window
) -> None:
    assert dump(lookups.roster(database, window)) == without_previous(
        truth["lookups"]["roster"][window]
    )


def test_one_person_filter_returns_just_their_row(
    database: Database, truth: dict[str, Any]
) -> None:
    quiet = truth["patterns"]["quiet_user"]
    expected = [r for r in truth["lookups"]["activity_by_person"]["30d"] if r["user_id"] == quiet]

    result = lookups.activity_by_person(database, "30d", user_id=quiet, with_previous=True)

    assert dump(result) == expected
    assert result[0].logins == 0
    assert result[0].last_seen is not None


def test_unknown_person_gives_no_rows(database: Database) -> None:
    assert lookups.activity_by_person(database, "7d", user_id="u999") == []


def test_tool_filter_on_errors(database: Database, truth: dict[str, Any]) -> None:
    tool = truth["patterns"]["error_tool"]
    expected = [r for r in truth["lookups"]["errors_seen"]["7d"] if r["tool_id"] == tool]

    result = lookups.errors_seen(database, "7d", tool_id=tool, with_previous=True)

    assert dump(result) == expected
    assert result[0].source == truth["patterns"]["error_source"]


def test_time_is_pinned_to_as_of_not_the_wall_clock(
    database: Database, truth: dict[str, Any]
) -> None:
    # The seed ends weeks before any real "today". If a lookup read the wall clock,
    # the `today` window would be empty.
    today = lookups.roster(database, "today")

    assert today.active_count == truth["lookups"]["roster"]["today"]["active_count"] > 0


def test_lookups_are_safe_from_several_threads(database: Database, truth: dict[str, Any]) -> None:
    # The API serves requests from a thread pool over one in-memory connection.
    # Without the lock in `Database.connect`, this fails within a few hundred calls.
    names = ["usage_by_tool", "activity_by_person", "activity_by_client", "errors_seen", "roster"]

    def run(index: int) -> tuple[str, Any]:
        name = names[index % len(names)]
        return name, dump(getattr(lookups, name)(database, "30d", with_previous=True))

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(run, range(400)))

    assert all(result == truth["lookups"][name]["30d"] for name, result in results)
