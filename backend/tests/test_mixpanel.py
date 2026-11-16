"""The Mixpanel source against a fake Mixpanel. No test reaches the real service."""

import base64
import json
import re
from datetime import UTC, date, datetime
from typing import Any

import httpx2
import pytest

from app import lookups
from app.config import DATA_DIR, Settings
from app.db import load_database
from app.lookups import WINDOWS
from app.sources import build_source
from app.sources.base import Workspace
from app.sources.file import FileEventSource
from app.sources.mixpanel import (
    EXPORT_DEADLINE_SECONDS,
    MixpanelConfig,
    MixpanelEventSource,
    MixpanelUnavailable,
    push_workspace,
    to_records,
)
from tests.test_lookups import dump

AS_OF = date(2026, 10, 30)
CONFIG = MixpanelConfig("4242", "svc.user", "svc-pass-not-real", AS_OF)
EXPECTED_AUTH = "Basic " + base64.b64encode(b"svc.user:svc-pass-not-real").decode()


DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")


def as_mixpanel_stores(record: dict[str, Any]) -> dict[str, Any]:
    """What the real Mixpanel did to a record on the first real run (16 Nov 2026).

    A property that is just a date came back as a date-time, and a `$user_id` and
    several `$mp_*` properties were added. Everything else came back as sent.
    """
    properties = {
        key: f"{value}T00:00:00" if isinstance(value, str) and DATE_ONLY.fullmatch(value) else value
        for key, value in record["properties"].items()
    }
    properties |= {"$import": True, "$user_id": properties["distinct_id"], "$mp_event_size": 200}
    return {"event": record["event"], "properties": properties}


class FakeMixpanel:
    """Keeps what is imported and serves it back as an export, like the real thing."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.requests: list[httpx2.Request] = []
        self.fail_with: list[int] = []  # statuses to answer with before behaving
        self.duplicate_export = False

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.headers.get("authorization") != EXPECTED_AUTH:
            return httpx2.Response(401, json={"error": "Invalid credentials"})
        if self.fail_with:
            return httpx2.Response(self.fail_with.pop(0), text="try later")
        if request.url.path == "/import":
            batch = json.loads(request.content)
            self.records.extend(as_mixpanel_stores(record) for record in batch)
            return httpx2.Response(200, json={"code": 200, "num_records_imported": len(batch)})
        if request.url.path == "/api/2.0/export":
            wanted = set(json.loads(request.url.params["event"]))
            first = date.fromisoformat(request.url.params["from_date"])
            last = date.fromisoformat(request.url.params["to_date"])
            lines = [
                json.dumps(r)
                for r in self.records
                # Like the real export: only the named events, only inside the date range.
                if r["event"] in wanted
                and first <= datetime.fromtimestamp(r["properties"]["time"], UTC).date() <= last
            ]
            if self.duplicate_export:
                lines = lines + lines[:500]
            return httpx2.Response(200, text="\n".join(lines) + "\n")
        return httpx2.Response(404)

    @property
    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@pytest.fixture(scope="module")
def workspace() -> Workspace:
    return FileEventSource(DATA_DIR / "events.jsonl").load()


@pytest.fixture
def loaded(workspace: Workspace) -> FakeMixpanel:
    fake = FakeMixpanel()
    fake.records = [as_mixpanel_stores(record) for record in to_records(workspace, days=60)]
    return fake


def source(fake: FakeMixpanel, **overrides: Any) -> MixpanelEventSource:
    return MixpanelEventSource(
        CONFIG, transport=fake.transport, **{"sleep": lambda _: None} | overrides
    )


def test_a_workspace_pushed_to_mixpanel_comes_back_identical(workspace: Workspace) -> None:
    fake = FakeMixpanel()

    sent = push_workspace(workspace, 60, CONFIG, transport=fake.transport)

    assert sent == len(workspace.events) + 40 + 6 + 8 + 1
    assert source(fake).load() == workspace


def test_every_lookup_over_the_mixpanel_source_equals_ground_truth(
    loaded: FakeMixpanel, truth: dict[str, Any]
) -> None:
    database = load_database(source(loaded))

    for name, by_window in truth["lookups"].items():
        for window in WINDOWS:
            result = getattr(lookups, name)(database, window, with_previous=True)
            assert dump(result) == by_window[window], (name, window)


def test_a_load_is_one_download_with_a_padded_date_range(loaded: FakeMixpanel) -> None:
    source(loaded).load()

    assert loaded.paths() == ["/api/2.0/export"]
    request = loaded.requests[0]
    assert request.url.host == "data.mixpanel.com"
    assert request.url.params["project_id"] == "4242"
    assert request.url.params["from_date"] == "2026-08-31"
    assert request.url.params["to_date"] == "2026-10-31"


def test_the_region_picks_the_hosts(workspace: Workspace) -> None:
    fake = FakeMixpanel()
    europe = MixpanelConfig("4242", "svc.user", "svc-pass-not-real", AS_OF, region="eu")

    push_workspace(workspace, 60, europe, transport=fake.transport)
    MixpanelEventSource(europe, transport=fake.transport).load()

    assert {request.url.host for request in fake.requests} == {
        "api-eu.mixpanel.com",
        "data-eu.mixpanel.com",
    }


def test_imports_go_in_batches_mixpanel_accepts(workspace: Workspace) -> None:
    fake = FakeMixpanel()

    push_workspace(workspace, 60, CONFIG, transport=fake.transport)

    assert len(fake.requests) == 5
    for request in fake.requests:
        assert request.url.params["strict"] == "1"
        assert request.url.params["project_id"] == "4242"
        assert len(json.loads(request.content)) <= 2000
    for record in fake.records:
        insert_id = record["properties"]["$insert_id"]
        assert len(insert_id) <= 36
        assert insert_id.replace("-", "").isalnum()
    assert len({r["properties"]["$insert_id"] for r in fake.records}) == len(fake.records)


def test_duplicates_in_the_export_are_dropped(loaded: FakeMixpanel, workspace: Workspace) -> None:
    loaded.duplicate_export = True

    assert source(loaded).load() == workspace


@pytest.mark.parametrize("status", [429, 502, 503])
def test_a_busy_mixpanel_is_retried_with_backoff(
    loaded: FakeMixpanel, workspace: Workspace, status: int
) -> None:
    loaded.fail_with = [status, status]
    waits: list[float] = []

    assert source(loaded, sleep=waits.append).load() == workspace
    assert waits == [2.0, 4.0]
    assert len(loaded.requests) == 3


def test_it_gives_up_after_three_attempts(loaded: FakeMixpanel) -> None:
    loaded.fail_with = [429, 429, 429, 429]

    with pytest.raises(MixpanelUnavailable, match="kept failing"):
        source(loaded).load()
    assert len(loaded.requests) == 3


def test_a_dropped_connection_is_retried(workspace: Workspace) -> None:
    fake = FakeMixpanel()
    fake.records = [as_mixpanel_stores(record) for record in to_records(workspace, 60)]
    calls = 0

    def flaky(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx2.ConnectError("no route")
        return fake.handle(request)

    flaky_source = MixpanelEventSource(
        CONFIG, transport=httpx2.MockTransport(flaky), sleep=lambda _: None
    )

    assert flaky_source.load() == workspace


def test_rejected_records_are_not_retried(workspace: Workspace) -> None:
    fake = FakeMixpanel()
    fake.fail_with = [400]

    with pytest.raises(MixpanelUnavailable, match="400"):
        push_workspace(workspace, 60, CONFIG, transport=fake.transport, sleep=lambda _: None)
    assert len(fake.requests) == 1


def test_wrong_credentials_fail_at_once_and_the_secret_stays_out_of_the_error(
    loaded: FakeMixpanel,
) -> None:
    wrong = MixpanelConfig("4242", "svc.user", "another-pass-not-real", AS_OF)

    with pytest.raises(MixpanelUnavailable) as failure:
        MixpanelEventSource(wrong, transport=loaded.transport).load()

    assert "401" in str(failure.value)
    assert "another-pass-not-real" not in str(failure.value)
    assert len(loaded.requests) == 1


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_download_that_runs_past_the_deadline_is_stopped(loaded: FakeMixpanel) -> None:
    clock = Clock()

    def slow(request: httpx2.Request) -> httpx2.Response:
        clock.now += EXPORT_DEADLINE_SECONDS + 1  # the body arrives too late
        return loaded.handle(request)

    slow_source = MixpanelEventSource(CONFIG, transport=httpx2.MockTransport(slow), clock=clock)

    with pytest.raises(MixpanelUnavailable, match="longer than"):
        slow_source.load()
    assert len(loaded.requests) == 1


def test_a_read_that_times_out_at_the_deadline_is_not_retried() -> None:
    clock = Clock()
    requests = 0

    def stalls(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        clock.now += EXPORT_DEADLINE_SECONDS
        raise httpx2.ReadTimeout("stalled")

    stalled = MixpanelEventSource(CONFIG, transport=httpx2.MockTransport(stalls), clock=clock)

    with pytest.raises(MixpanelUnavailable, match="longer than"):
        stalled.load()
    assert requests == 1


def test_retries_and_waits_share_one_deadline(loaded: FakeMixpanel) -> None:
    clock = Clock()
    waits: list[float] = []
    timeouts: list[float] = []

    def busy(request: httpx2.Request) -> httpx2.Response:
        timeouts.append(request.extensions["timeout"]["read"])
        clock.now += 28  # each attempt uses up 28 seconds before Mixpanel says "busy"
        return httpx2.Response(429)

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock.now += seconds

    busy_source = MixpanelEventSource(
        CONFIG, transport=httpx2.MockTransport(busy), clock=clock, sleep=sleep
    )

    with pytest.raises(MixpanelUnavailable, match="kept failing"):
        busy_source.load()
    # 28s, wait 2s, 28s: 2s are left, less than the 4s wait, so there is no third attempt.
    assert waits == [2.0]
    assert timeouts == [30.0, 30.0]
    assert clock.now <= EXPORT_DEADLINE_SECONDS


def test_no_single_wait_outlasts_what_is_left(loaded: FakeMixpanel) -> None:
    clock = Clock()
    timeouts: list[float] = []

    def busy_then_fine(request: httpx2.Request) -> httpx2.Response:
        timeouts.append(request.extensions["timeout"]["read"])
        if len(timeouts) == 1:
            clock.now += 48
            return httpx2.Response(503)
        return loaded.handle(request)

    def sleep(seconds: float) -> None:
        clock.now += seconds

    MixpanelEventSource(
        CONFIG, transport=httpx2.MockTransport(busy_then_fine), clock=clock, sleep=sleep
    ).load()

    assert timeouts == [30.0, 10.0]


def test_the_secret_is_not_in_the_config_repr() -> None:
    assert "svc-pass-not-real" not in repr(CONFIG)


def test_an_event_tracked_by_something_else_is_refused(loaded: FakeMixpanel) -> None:
    loaded.records.append(
        {"event": "login", "properties": {"time": 1793318400, "distinct_id": "x"}}  # 30 Oct 2026
    )

    with pytest.raises(ValueError, match="tracked by something else"):
        source(loaded).load()


def test_data_for_another_day_is_refused(loaded: FakeMixpanel) -> None:
    other_day = MixpanelConfig("4242", "svc.user", "svc-pass-not-real", date(2026, 10, 29))

    with pytest.raises(ValueError, match="MIXPANEL_AS_OF"):
        MixpanelEventSource(other_day, transport=loaded.transport).load()


def test_an_empty_project_is_refused() -> None:
    with pytest.raises(ValueError, match="mixpanel-push"):
        source(FakeMixpanel()).load()


def test_settings_choose_the_mixpanel_source_and_name_what_is_missing() -> None:
    bare = Settings(_env_file=None, event_source="mixpanel", mixpanel_project_id="4242")

    with pytest.raises(ValueError, match="MIXPANEL_SERVICE_ACCOUNT_SECRET, MIXPANEL_AS_OF"):
        build_source(bare)

    full = Settings(
        _env_file=None,
        event_source="mixpanel",
        mixpanel_project_id="4242",
        mixpanel_service_account_username="svc.user",
        mixpanel_region="",
        mixpanel_as_of="2026-10-30",  # type: ignore[arg-type]
        mixpanel_service_account_secret="svc-pass-not-real",
    )
    assert isinstance(build_source(full), MixpanelEventSource)


def test_dates_are_read_back_in_the_form_mixpanel_returns_them(loaded: FakeMixpanel) -> None:
    user = next(r for r in loaded.records if r["event"] == "workspace_user")
    assert user["properties"]["invited_at"].endswith("T00:00:00")  # what the real export returns

    workspace = source(loaded).load()

    assert workspace.as_of == AS_OF
    assert all(isinstance(person.invited_at, date) for person in workspace.users)
