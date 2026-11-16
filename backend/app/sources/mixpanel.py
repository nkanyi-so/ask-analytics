"""Mixpanel-backed source: the same workspace, tracked into Mixpanel and read back.

Writing uses the import API; reading uses the raw export API, with a service account
for both. A load is one export request covering every window and its previous window,
so no lookup ever triggers a download.

Three things about Mixpanel shape this file:

- The export is not deduplicated, so events are deduplicated here by their own id.
- Older projects shift `time` and the export's date range into the project's timezone.
  So each event carries its own timestamp as a property, which is what is read back,
  and the date range is padded by a day on each side.
- The roster has people with no events, and the lookups need clients and tools too.
  They travel as `workspace_*` events, so one export returns the whole workspace.
"""

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx2

from app.registry import CATALOG
from app.sources.base import Client, Event, Tool, User, Workspace

Region = Literal["us", "eu", "in"]
IMPORT_HOSTS: dict[Region, str] = {
    "us": "https://api.mixpanel.com",
    "eu": "https://api-eu.mixpanel.com",
    "in": "https://api-in.mixpanel.com",
}
EXPORT_HOSTS: dict[Region, str] = {
    "us": "https://data.mixpanel.com",
    "eu": "https://data-eu.mixpanel.com",
    "in": "https://data-in.mixpanel.com",
}

HISTORY_DAYS = 60  # the 30-day window and the 30 days before it
IMPORT_BATCH = 2000  # Mixpanel's limit per import request
ATTEMPTS = 3
BACKOFF_SECONDS = (2.0, 4.0)  # Mixpanel asks for 2s, doubling
RETRY_STATUSES = {429, 502, 503}
EXPORT_DEADLINE_SECONDS = 60.0  # hard limit on a whole load: every attempt and wait
READ_SECONDS, CONNECT_SECONDS = 30.0, 10.0
REQUEST_TIMEOUT = httpx2.Timeout(READ_SECONDS, connect=CONNECT_SECONDS)

META, CLIENT, TOOL, USER = "workspace_meta", "workspace_client", "workspace_tool", "workspace_user"
ACTIVITY_NAMES = ("login", "tool_opened", "error", *(entry.headline_event for entry in CATALOG))
EVENT_NAMES = (META, CLIENT, TOOL, USER, *ACTIVITY_NAMES)


class MixpanelUnavailable(Exception):
    """Mixpanel could not be reached, kept failing, or took too long."""


@dataclass(frozen=True)
class MixpanelConfig:
    project_id: str
    username: str
    # Kept out of repr, so a traceback or a debug line cannot print it.
    secret: str = field(repr=False)
    as_of: date
    region: Region = "us"

    def auth(self) -> httpx2.BasicAuth:
        return httpx2.BasicAuth(self.username, self.secret)


# --- wire format ---------------------------------------------------------------------


def _epoch(moment: datetime) -> int:
    """The workspace clock has no timezone; on the wire it is sent as if it were UTC."""
    return int(moment.replace(tzinfo=UTC).timestamp())


def _record(name: str, key: str, at: datetime, /, **properties: Any) -> dict[str, Any]:
    return {
        "event": name,
        "properties": {
            "time": _epoch(at),
            "distinct_id": properties.pop("distinct_id"),
            # Letters, digits and "-" only, at most 36 bytes: Mixpanel's rule.
            "$insert_id": f"aa-{key}".replace("_", "-"),
            **{k: v for k, v in properties.items() if v is not None},
        },
    }


def to_records(workspace: Workspace, days: int) -> list[dict[str, Any]]:
    """The whole workspace as Mixpanel import records."""
    at = datetime.combine(workspace.as_of, datetime.min.time())
    records = [
        _record(
            META, "meta", at, distinct_id="workspace", as_of=workspace.as_of.isoformat(), days=days
        )
    ]
    for client in workspace.clients:
        records.append(
            _record(
                CLIENT,
                f"c-{client.id}",
                at,
                distinct_id=f"client-{client.id}",
                id=client.id,
                name=client.name,
            )
        )
    for tool in workspace.tools:
        records.append(
            _record(
                TOOL,
                f"t-{tool.id}",
                at,
                distinct_id=f"tool-{tool.id}",
                id=tool.id,
                name=tool.name,
                headline_event=tool.headline_event,
            )
        )
    for user in workspace.users:
        records.append(
            _record(
                USER,
                f"u-{user.id}",
                at,
                distinct_id=user.id,
                id=user.id,
                name=user.name,
                client_id=user.client_id,
                role=user.role,
                invited_at=user.invited_at.isoformat(),
            )
        )
    for event in workspace.events:
        records.append(
            _record(
                event.name,
                f"e-{event.id}",
                event.ts,
                distinct_id=event.user_id,
                event_id=event.id,
                # Read back from here: Mixpanel may rewrite distinct_id when it merges identities.
                user_id=event.user_id,
                ts=event.ts.isoformat(),
                client_id=event.client_id,
                tool_id=event.tool_id,
                error_source=event.error_source,
            )
        )
    return records


def from_lines(lines: Iterator[str], expected_as_of: date) -> Workspace:
    """Rebuild the workspace from export lines, dropping duplicates."""
    as_of: date | None = None
    clients: dict[str, Client] = {}
    tools: dict[str, Tool] = {}
    users: dict[str, User] = {}
    events: dict[int, Event] = {}
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        name, p = record["event"], record["properties"]
        try:
            if name == META:
                as_of = date.fromisoformat(p["as_of"])
            elif name == CLIENT:
                clients.setdefault(p["id"], Client(p["id"], p["name"]))
            elif name == TOOL:
                tools.setdefault(p["id"], Tool(p["id"], p["name"], p["headline_event"]))
            elif name == USER:
                invited_at = date.fromisoformat(p["invited_at"])
                users.setdefault(
                    p["id"], User(p["id"], p["name"], p["client_id"], p["role"], invited_at)
                )
            elif name in ACTIVITY_NAMES:
                events.setdefault(
                    int(p["event_id"]),
                    Event(
                        id=int(p["event_id"]),
                        ts=datetime.fromisoformat(p["ts"]),
                        user_id=p["user_id"],
                        client_id=p["client_id"],
                        tool_id=p.get("tool_id"),
                        name=name,
                        error_source=p.get("error_source"),
                    ),
                )
            else:
                raise ValueError(f"Mixpanel returned an event this app does not know: {name!r}")
        except KeyError as missing:
            # An event with one of our names that we did not send: refuse, do not guess.
            raise ValueError(
                f"Mixpanel event {name!r} lacks {missing}. Was it tracked by something else? "
                "Use a project that holds only this workspace."
            ) from missing
    if as_of is None:
        raise ValueError(
            "Mixpanel returned no workspace_meta event in the date range. "
            "Run `make mixpanel-push` and check MIXPANEL_AS_OF."
        )
    if as_of != expected_as_of:
        raise ValueError(f"MIXPANEL_AS_OF is {expected_as_of} but the data says {as_of}.")
    return Workspace(
        as_of,
        tuple(clients[key] for key in sorted(clients)),
        tuple(tools[key] for key in sorted(tools)),
        tuple(users[key] for key in sorted(users)),
        tuple(events[key] for key in sorted(events)),
    )


# --- HTTP ----------------------------------------------------------------------------


class _Retry(Exception):
    """Worth another attempt: Mixpanel was busy or the connection dropped."""


def _with_retries[T](
    attempt: Callable[[], T],
    sleep: Callable[[float], None],
    time_left: Callable[[], float] = lambda: float("inf"),
) -> T:
    """Run `attempt`, retrying with backoff, but never past the time that is left."""
    for number in range(ATTEMPTS):
        try:
            return attempt()
        except _Retry as retry:
            last = number == ATTEMPTS - 1
            if last or BACKOFF_SECONDS[number] >= time_left():
                raise MixpanelUnavailable(f"Mixpanel kept failing: {retry}") from retry
            sleep(BACKOFF_SECONDS[number])
    raise AssertionError("unreachable")


def _check(response: httpx2.Response, what: str) -> None:
    if response.status_code in RETRY_STATUSES:
        raise _Retry(f"{what} returned {response.status_code}")
    if response.status_code == 401:
        raise MixpanelUnavailable(f"{what}: Mixpanel rejected the service account (401).")
    if response.status_code != 200:
        response.read()
        raise MixpanelUnavailable(f"{what} returned {response.status_code}: {response.text[:300]}")


class MixpanelEventSource:
    def __init__(
        self,
        config: MixpanelConfig,
        *,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    def load(self) -> Workspace:
        # One deadline for the whole load, retries and waits included.
        deadline = self._clock() + EXPORT_DEADLINE_SECONDS
        return _with_retries(
            lambda: self._download(deadline), self._sleep, lambda: deadline - self._clock()
        )

    def _too_slow(self) -> MixpanelUnavailable:
        return MixpanelUnavailable(
            f"Export took longer than {EXPORT_DEADLINE_SECONDS:.0f}s in total; stopped."
        )

    def _download(self, deadline: float) -> Workspace:
        config = self._config
        left = deadline - self._clock()
        if left <= 0:
            raise self._too_slow()
        params = {
            "project_id": config.project_id,
            # A day either side: older projects read these dates in their own timezone.
            "from_date": (config.as_of - timedelta(days=HISTORY_DAYS)).isoformat(),
            "to_date": (config.as_of + timedelta(days=1)).isoformat(),
            # Only our own event names, so anything else in the project is left out.
            "event": json.dumps(EVENT_NAMES),
        }
        # No single wait may outlast what is left of the deadline.
        timeout = httpx2.Timeout(min(READ_SECONDS, left), connect=min(CONNECT_SECONDS, left))
        try:
            with (
                httpx2.Client(
                    auth=config.auth(), timeout=timeout, transport=self._transport
                ) as http,
                http.stream(
                    "GET", f"{EXPORT_HOSTS[config.region]}/api/2.0/export", params=params
                ) as response,
            ):
                _check(response, "Export")
                return from_lines(self._until(deadline, response.iter_lines()), config.as_of)
        except httpx2.TransportError as error:
            if self._clock() >= deadline:
                raise self._too_slow() from error
            raise _Retry(f"export failed: {type(error).__name__}") from error

    def _until(self, deadline: float, lines: Iterator[str]) -> Iterator[str]:
        for line in lines:
            if self._clock() > deadline:
                raise self._too_slow()
            yield line


def push_workspace(
    workspace: Workspace,
    days: int,
    config: MixpanelConfig,
    *,
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Send the workspace to Mixpanel. Safe to repeat: `$insert_id` makes it idempotent."""
    if workspace.as_of != config.as_of:
        raise ValueError(f"MIXPANEL_AS_OF is {config.as_of} but the data says {workspace.as_of}.")
    records = to_records(workspace, days)
    url = f"{IMPORT_HOSTS[config.region]}/import"
    params = {"strict": "1", "project_id": config.project_id}
    imported = 0
    with httpx2.Client(auth=config.auth(), timeout=REQUEST_TIMEOUT, transport=transport) as http:
        for start in range(0, len(records), IMPORT_BATCH):
            batch = records[start : start + IMPORT_BATCH]

            def send(batch: list[dict[str, Any]] = batch) -> int:
                try:
                    response = http.post(url, params=params, json=batch)
                except httpx2.TransportError as error:
                    raise _Retry(f"import failed: {type(error).__name__}") from error
                # A 400 means records failed validation; retrying would fail the same way.
                _check(response, "Import")
                return int(response.json()["num_records_imported"])

            imported += _with_retries(send, sleep)
    if imported != len(records):
        raise MixpanelUnavailable(f"Mixpanel took {imported} of {len(records)} records.")
    return imported
