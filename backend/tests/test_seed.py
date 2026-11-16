"""The seed is deterministic and contains every pattern the demo and the evals depend on.

Patterns are checked here straight from the raw event lines, not through the seed's own
ground-truth code, so a bug there cannot hide a missing pattern.
"""

import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

import pytest

from app.config import DATA_DIR
from scripts import seed

Record = dict[str, Any]


@pytest.fixture(scope="module")
def built() -> tuple[bytes, bytes]:
    return seed.build(seed.SEED)


@pytest.fixture(scope="module")
def records(built: tuple[bytes, bytes]) -> dict[str, list[Record]]:
    by_kind: dict[str, list[Record]] = {}
    for line in built[0].decode().splitlines():
        record: Record = json.loads(line)
        by_kind.setdefault(record["kind"], []).append(record)
    return by_kind


@pytest.fixture(scope="module")
def truth(built: tuple[bytes, bytes]) -> Record:
    loaded: Record = json.loads(built[1])
    return loaded


def day_of(event: Record) -> date:
    return date.fromisoformat(event["ts"][:10])


def last_days(count: int, offset: int = 0) -> set[date]:
    """The `count` days ending `offset` days before AS_OF."""
    end = seed.AS_OF - timedelta(days=offset)
    return {end - timedelta(days=i) for i in range(count)}


# --- determinism ---------------------------------------------------------------------


def test_same_seed_gives_byte_identical_output(built: tuple[bytes, bytes]) -> None:
    assert seed.build(seed.SEED) == built


def test_a_different_seed_gives_different_events(built: tuple[bytes, bytes]) -> None:
    assert seed.build(seed.SEED + 1)[0] != built[0]


def test_tracked_data_files_are_what_the_seed_produces(built: tuple[bytes, bytes]) -> None:
    # Guards against hand edits: the files in data/ must come from `make seed`.
    assert (DATA_DIR / "events.jsonl").read_bytes() == built[0]
    assert (DATA_DIR / "ground_truth.json").read_bytes() == built[1]


# --- shape ---------------------------------------------------------------------------


def test_workspace_shape(records: dict[str, list[Record]], truth: Record) -> None:
    assert len(records["meta"]) == 1
    assert len(records["tool"]) == 8
    assert len(records["client"]) == 6
    assert len(records["user"]) == 40
    assert {user["role"] for user in records["user"]} == {"admin", "manager", "member"}
    assert truth["as_of"] == records["meta"][0]["as_of"] == seed.AS_OF.isoformat()
    assert truth["seed"] == seed.SEED


def test_every_tool_has_one_distinct_headline_event(records: dict[str, list[Record]]) -> None:
    headlines = [tool["headline_event"] for tool in records["tool"]]
    assert len(set(headlines)) == 8
    assert all(headlines)


def test_events_cover_sixty_days_ending_on_as_of(records: dict[str, list[Record]]) -> None:
    days = {day_of(event) for event in records["event"]}
    assert max(days) == seed.AS_OF
    assert min(days) == seed.AS_OF - timedelta(days=59)
    assert seed.AS_OF.weekday() < 5, "AS_OF must be a weekday so `today` is not empty"


def test_events_use_only_known_names_and_ids(records: dict[str, list[Record]]) -> None:
    tools = {tool["id"]: tool["headline_event"] for tool in records["tool"]}
    users = {user["id"]: user["client_id"] for user in records["user"]}
    ids = [event["id"] for event in records["event"]]
    assert ids == sorted(set(ids))
    for event in records["event"]:
        assert users[event["user_id"]] == event["client_id"]
        if event["name"] == "login":
            assert event["tool_id"] is None
        else:
            allowed = {"tool_opened", "error", tools[event["tool_id"]]}
            assert event["name"] in allowed
        assert (event["error_source"] is not None) == (event["name"] == "error")


# --- required patterns ---------------------------------------------------------------


def test_one_tool_nobody_uses(records: dict[str, list[Record]], truth: Record) -> None:
    recent = last_days(30)
    used_recently = {e["tool_id"] for e in records["event"] if e["tool_id"] and day_of(e) in recent}
    unused = {tool["id"] for tool in records["tool"]} - used_recently

    assert unused == {truth["patterns"]["unused_tool"]}
    # It was used before, so the comparison with the previous window shows the drop.
    assert any(e["tool_id"] in unused for e in records["event"])


def test_one_person_stopped_logging_in(records: dict[str, list[Record]], truth: Record) -> None:
    quiet = truth["patterns"]["quiet_user"]
    first_day = seed.AS_OF - timedelta(days=59)
    theirs = [e for e in records["event"] if e["user_id"] == quiet]
    login_days = {(day_of(e) - first_day).days + 1 for e in theirs if e["name"] == "login"}
    event_days = {(day_of(e) - first_day).days + 1 for e in theirs}

    assert len(login_days) >= 10, "the quiet person must have been properly active once"
    assert max(event_days) <= 25, "nothing at all after day 25"


def test_quiet_person_is_the_only_one_gone_quiet_over_thirty_days(
    records: dict[str, list[Record]], truth: Record
) -> None:
    recent = last_days(30)
    logins = [e for e in records["event"] if e["name"] == "login"]
    before = {e["user_id"] for e in logins if day_of(e) not in recent}
    inside = {e["user_id"] for e in logins if day_of(e) in recent}

    assert before - inside == {truth["patterns"]["quiet_user"]}


def test_three_people_never_logged_in(records: dict[str, list[Record]], truth: Record) -> None:
    logged_in = {e["user_id"] for e in records["event"] if e["name"] == "login"}
    never = {user["id"] for user in records["user"]} - logged_in

    assert len(never) == 3
    assert never == set(truth["patterns"]["never_logged_in"])
    assert not [e for e in records["event"] if e["user_id"] in never]


def test_error_spike_in_the_last_week_from_one_source(
    records: dict[str, list[Record]], truth: Record
) -> None:
    tool = truth["patterns"]["error_tool"]
    source = truth["patterns"]["error_source"]
    errors = [e for e in records["event"] if e["name"] == "error"]
    this_week = Counter(
        (e["tool_id"], e["error_source"]) for e in errors if day_of(e) in last_days(7)
    )
    week_before = Counter(
        (e["tool_id"], e["error_source"]) for e in errors if day_of(e) in last_days(7, offset=7)
    )

    spike = this_week[(tool, source)]
    assert spike >= 30
    assert spike >= 5 * max(week_before[(tool, source)], 1)
    # The spike is the largest group by a wide margin, and that source hits only that tool.
    others = [count for key, count in this_week.items() if key != (tool, source)]
    assert spike >= 4 * max(others, default=0)
    assert {e["tool_id"] for e in errors if e["error_source"] == source} == {tool}
    # Several people hit it, so "who was affected" has an answer worth showing.
    assert len({e["user_id"] for e in errors if e["error_source"] == source}) >= 5


def test_weekdays_are_busier_than_weekends(records: dict[str, list[Record]]) -> None:
    logins_per_day = Counter(day_of(e) for e in records["event"] if e["name"] == "login")
    weekdays = [n for day, n in logins_per_day.items() if day.weekday() < 5]
    weekend_days = [d for d in last_days(60) if d.weekday() >= 5]
    weekend_total = sum(logins_per_day.get(day, 0) for day in weekend_days)

    weekday_average = sum(weekdays) / len(weekdays)
    weekend_average = weekend_total / len(weekend_days)
    assert weekend_average > 0, "weekends are quiet, not dead"
    assert weekday_average >= 3 * weekend_average


def test_usage_is_uneven_across_clients(records: dict[str, list[Record]]) -> None:
    headline_events = {tool["headline_event"] for tool in records["tool"]}
    outputs = Counter(e["client_id"] for e in records["event"] if e["name"] in headline_events)
    members = Counter(user["client_id"] for user in records["user"])
    per_person = {client: outputs[client] / members[client] for client in members}

    assert len(outputs) == 6, "every client produces something"
    assert max(outputs.values()) >= 4 * min(outputs.values())
    # Uneven beyond headcount: some clients simply use the product more.
    assert max(per_person.values()) >= 2 * min(per_person.values())


def test_today_is_not_empty(records: dict[str, list[Record]]) -> None:
    today = [e for e in records["event"] if day_of(e) == seed.AS_OF]
    assert len({e["user_id"] for e in today if e["name"] == "login"}) >= 10
