"""What a deployed build must refuse, and the scheduled cache warm."""

import asyncio
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import lookups as lookup_module
from app.cache import TTLCache
from app.config import Settings
from app.db import Database
from app.lookups import Lookups
from app.main import WARM_EVERY_SECONDS, check_deployable, create_app, keep_warm
from tests.conftest import TEST_TOKEN

LONG_TOKEN = "a-long-test-token-that-is-not-a-secret"
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


def deployed(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "deployed": True,
        "admin_token": LONG_TOKEN,
        "anthropic_api_key": "not-a-real-key",
    } | overrides
    return Settings(_env_file=None, **values)


def test_a_deployed_build_refuses_to_start_in_demo_mode() -> None:
    with (
        pytest.raises(RuntimeError, match="demo mode is for local use only"),
        TestClient(create_app(deployed(anthropic_api_key=""))),
    ):
        pass


@pytest.mark.parametrize("token", ["", "short"])
def test_a_deployed_build_needs_a_real_admin_token(token: str) -> None:
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        check_deployable(deployed(admin_token=token))


def test_a_deployed_build_reads_the_file_source_only() -> None:
    with pytest.raises(RuntimeError, match="EVENT_SOURCE must be file"):
        check_deployable(deployed(event_source="mixpanel"))


def test_running_on_railway_counts_as_deployed_even_without_the_image() -> None:
    on_railway = Settings(
        _env_file=None,
        deployed=False,
        railway_environment_name="production",
        admin_token=LONG_TOKEN,
        anthropic_api_key="",
    )

    with pytest.raises(RuntimeError, match="demo mode"):
        check_deployable(on_railway)


def test_a_token_of_spaces_is_not_a_token() -> None:
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        check_deployable(deployed(admin_token=" " * 40))


def test_a_refusal_never_prints_a_secret_that_is_set() -> None:
    with pytest.raises(RuntimeError) as refusal:
        check_deployable(deployed(event_source="mixpanel"))

    assert LONG_TOKEN not in str(refusal.value)
    assert "not-a-real-key" not in str(refusal.value)


def test_every_problem_is_named_at_once_and_no_secret_is_printed() -> None:
    with pytest.raises(RuntimeError) as refusal:
        check_deployable(deployed(anthropic_api_key="", admin_token="short"))

    assert "ANTHROPIC_API_KEY" in str(refusal.value)
    assert "ADMIN_TOKEN" in str(refusal.value)
    assert "short" not in str(refusal.value).replace("shorter", "")


def test_a_complete_deployed_build_passes_and_local_demo_mode_is_still_allowed() -> None:
    check_deployable(deployed())
    check_deployable(
        Settings(
            _env_file=None,
            anthropic_api_key="",
            admin_token="",
            deployed=False,
            railway_environment_name="",
        )
    )


def count_queries(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every time a lookup really runs against the database."""
    ran: list[str] = []
    for name in (
        "usage_by_tool",
        "activity_by_person",
        "activity_by_client",
        "errors_seen",
        "roster",
    ):
        real = getattr(lookup_module, name)

        def counted(*args: Any, _real: Any = real, _name: str = name, **kwargs: Any) -> Any:
            ran.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(lookup_module, name, counted)
    return ran


def test_the_first_visitor_after_a_start_reads_only_from_the_cache(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = count_queries(monkeypatch)

    with TestClient(create_app(settings)) as client:
        warmed = len(ran)
        for path in (
            "/api/overview?window=today",
            "/api/overview?window=7d",
            "/api/overview?window=30d",
            "/api/reliability?window=7d",
            "/api/summary",
        ):
            assert client.get(path, headers=AUTH).status_code == 200

    assert warmed == 15  # five lookups in three windows
    assert len(ran) == warmed


def test_a_warm_replaces_entries_before_they_expire(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 0.0
    lookups = Lookups(database, TTLCache(ttl_seconds=600, clock=lambda: now))
    lookups.warm()
    now = WARM_EVERY_SECONDS
    lookups.warm()  # the scheduled run, while the first entries are still alive
    ran = count_queries(monkeypatch)

    now = 700.0  # past the first warm's lifetime, inside the second's
    lookups.usage_by_tool("7d", with_previous=True)
    lookups.roster("30d", with_previous=True)

    assert ran == []


def test_warmed_values_are_what_a_cold_read_returns(database: Database) -> None:
    warm, cold = Lookups(database, TTLCache()), Lookups(database, TTLCache())
    warm.warm()

    for window in lookup_module.WINDOWS:
        assert warm.usage_by_tool(window, True) == cold.usage_by_tool(window, True)
        assert warm.activity_by_person(window, None, True) == cold.activity_by_person(
            window, None, True
        )
        assert warm.activity_by_client(window, True) == cold.activity_by_client(window, True)
        assert warm.errors_seen(window, None, True) == cold.errors_seen(window, None, True)
        assert warm.roster(window, True) == cold.roster(window, True)


def test_the_schedule_keeps_running_after_a_failed_warm() -> None:
    class Flaky:
        def __init__(self) -> None:
            self.runs = 0

        def warm(self) -> None:
            self.runs += 1
            if self.runs == 1:
                raise RuntimeError("database hiccup")

    flaky = Flaky()

    async def run() -> None:
        task = asyncio.create_task(keep_warm(flaky, every_seconds=0.01))  # type: ignore[arg-type]
        deadline = time.monotonic() + 2
        while flaky.runs < 3 and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        task.cancel()

    asyncio.run(run())

    assert flaky.runs >= 3
