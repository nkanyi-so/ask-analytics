"""The five lookups. Every number on the page and in an answer comes from here.

Each lookup takes a window (`today`, `7d`, `30d`) ending on `AS_OF` and can also return
the previous window of the same length with the change, so differences are computed
here and never by the model. The meaning of each measure is in docs/ARCHITECTURE.md,
"Definitions"; scripts/seed.py computes the same things without SQL, and the tests
require the two to agree.
"""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict
from sqlalchemy import ColumnElement, Connection, and_, case, distinct, func, select

from app.cache import TTLCache
from app.db import Database, clients, events, tools, users
from app.registry import ToolId

Window = Literal["today", "7d", "30d"]
WINDOWS: tuple[Window, ...] = get_args(Window)
WINDOW_DAYS: dict[Window, int] = {"today": 1, "7d": 7, "30d": 30}

Span = tuple[datetime, datetime]  # first moment inside, first moment after


class Row(BaseModel):
    model_config = ConfigDict(frozen=True)


class ToolUsage(Row):
    tool_id: str
    tool_name: str
    headline_event: str
    headline_count: int
    active_people: int
    errors: int
    headline_count_previous: int | None = None
    headline_count_change: int | None = None
    active_people_previous: int | None = None
    active_people_change: int | None = None
    errors_previous: int | None = None
    errors_change: int | None = None


class PersonActivity(Row):
    user_id: str
    name: str
    client_id: str
    client_name: str
    role: str
    logins: int
    outputs: int
    last_seen: date | None
    logins_previous: int | None = None
    logins_change: int | None = None
    outputs_previous: int | None = None
    outputs_change: int | None = None


class ClientActivity(Row):
    client_id: str
    client_name: str
    active_people: int
    outputs: int
    active_people_previous: int | None = None
    active_people_change: int | None = None
    outputs_previous: int | None = None
    outputs_change: int | None = None


class ErrorGroup(Row):
    source: str
    tool_id: str
    tool_name: str
    count: int
    people_affected: int
    affected: list[str]
    count_previous: int | None = None
    count_change: int | None = None
    people_affected_previous: int | None = None
    people_affected_change: int | None = None


class RosterPerson(Row):
    user_id: str
    name: str
    client_name: str
    last_seen: date | None


class Roster(Row):
    invited_count: int
    active_count: int
    never_showed_up_count: int
    went_quiet_count: int
    active: list[RosterPerson]
    never_showed_up: list[RosterPerson]
    went_quiet: list[RosterPerson]
    active_count_previous: int | None = None
    active_count_change: int | None = None
    went_quiet_count_previous: int | None = None
    went_quiet_count_change: int | None = None


# --- windows -------------------------------------------------------------------------


def window_span(as_of: date, window: Window, previous: bool = False) -> Span:
    """The window ending on AS_OF, or the equally long stretch just before it."""
    days = WINDOW_DAYS[window]
    last_day = as_of - timedelta(days=days) if previous else as_of
    start = datetime.combine(last_day - timedelta(days=days - 1), time.min)
    return start, datetime.combine(last_day + timedelta(days=1), time.min)


def in_span(span: Span) -> ColumnElement[bool]:
    return and_(events.c.ts >= span[0], events.c.ts < span[1])


def count_if(condition: ColumnElement[bool]) -> ColumnElement[int]:
    return func.count(case((condition, 1)))


def changes(current: dict[str, int], previous: dict[str, int] | None) -> dict[str, int]:
    """`<measure>_previous` and `<measure>_change` for each measure, if asked for."""
    if previous is None:
        return {}
    fields: dict[str, int] = {}
    for measure, value in current.items():
        fields[f"{measure}_previous"] = previous[measure]
        fields[f"{measure}_change"] = value - previous[measure]
    return fields


def last_seen_by_user(connection: Connection, as_of: date) -> dict[str, date]:
    end = datetime.combine(as_of + timedelta(days=1), time.min)
    query = (
        select(events.c.user_id, func.max(events.c.ts))
        .where(events.c.name == "login", events.c.ts < end)
        .group_by(events.c.user_id)
    )
    return {user_id: latest.date() for user_id, latest in connection.execute(query)}


# --- usage by tool -------------------------------------------------------------------


def _tool_measures(connection: Connection, span: Span) -> dict[str, dict[str, int]]:
    query = (
        select(
            tools.c.id,
            count_if(events.c.name == tools.c.headline_event),
            func.count(distinct(events.c.user_id)),
            count_if(events.c.name == "error"),
        )
        .select_from(tools.outerjoin(events, and_(events.c.tool_id == tools.c.id, in_span(span))))
        .group_by(tools.c.id)
    )
    return {
        tool_id: {"headline_count": headline, "active_people": people, "errors": errors}
        for tool_id, headline, people, errors in connection.execute(query)
    }


def usage_by_tool(db: Database, window: Window, with_previous: bool = False) -> list[ToolUsage]:
    with db.connect() as connection:
        current = _tool_measures(connection, window_span(db.as_of, window))
        previous = (
            _tool_measures(connection, window_span(db.as_of, window, previous=True))
            if with_previous
            else None
        )
        catalog = connection.execute(
            select(tools.c.id, tools.c.name, tools.c.headline_event).order_by(tools.c.id)
        ).all()
    return [
        ToolUsage(
            tool_id=tool_id,
            tool_name=name,
            headline_event=headline_event,
            **current[tool_id],
            **changes(current[tool_id], previous[tool_id] if previous else None),
        )
        for tool_id, name, headline_event in catalog
    ]


# --- activity by person --------------------------------------------------------------


def _person_measures(connection: Connection, span: Span) -> dict[str, dict[str, int]]:
    query = (
        select(
            users.c.id,
            count_if(events.c.name == "login"),
            count_if(events.c.name == tools.c.headline_event),
        )
        .select_from(
            users.outerjoin(events, and_(events.c.user_id == users.c.id, in_span(span))).outerjoin(
                tools, tools.c.id == events.c.tool_id
            )
        )
        .group_by(users.c.id)
    )
    return {
        user_id: {"logins": logins, "outputs": outputs}
        for user_id, logins, outputs in connection.execute(query)
    }


def activity_by_person(
    db: Database, window: Window, user_id: str | None = None, with_previous: bool = False
) -> list[PersonActivity]:
    with db.connect() as connection:
        current = _person_measures(connection, window_span(db.as_of, window))
        previous = (
            _person_measures(connection, window_span(db.as_of, window, previous=True))
            if with_previous
            else None
        )
        last_seen = last_seen_by_user(connection, db.as_of)
        people_query = (
            select(users.c.id, users.c.name, users.c.client_id, clients.c.name, users.c.role)
            .join(clients, clients.c.id == users.c.client_id)
            .order_by(users.c.id)
        )
        if user_id is not None:
            people_query = people_query.where(users.c.id == user_id)
        people = connection.execute(people_query).all()
    return [
        PersonActivity(
            user_id=uid,
            name=name,
            client_id=client_id,
            client_name=client_name,
            role=role,
            last_seen=last_seen.get(uid),
            **current[uid],
            **changes(current[uid], previous[uid] if previous else None),
        )
        for uid, name, client_id, client_name, role in people
    ]


# --- activity by client --------------------------------------------------------------


def _client_measures(connection: Connection, span: Span) -> dict[str, dict[str, int]]:
    query = (
        select(
            clients.c.id,
            func.count(distinct(case((events.c.name == "login", events.c.user_id)))),
            count_if(events.c.name == tools.c.headline_event),
        )
        .select_from(
            clients.outerjoin(
                events, and_(events.c.client_id == clients.c.id, in_span(span))
            ).outerjoin(tools, tools.c.id == events.c.tool_id)
        )
        .group_by(clients.c.id)
    )
    return {
        client_id: {"active_people": people, "outputs": outputs}
        for client_id, people, outputs in connection.execute(query)
    }


def activity_by_client(
    db: Database, window: Window, with_previous: bool = False
) -> list[ClientActivity]:
    with db.connect() as connection:
        current = _client_measures(connection, window_span(db.as_of, window))
        previous = (
            _client_measures(connection, window_span(db.as_of, window, previous=True))
            if with_previous
            else None
        )
        names = connection.execute(select(clients.c.id, clients.c.name).order_by(clients.c.id))
        return [
            ClientActivity(
                client_id=client_id,
                client_name=name,
                **current[client_id],
                **changes(current[client_id], previous[client_id] if previous else None),
            )
            for client_id, name in names
        ]


# --- errors seen ---------------------------------------------------------------------

GroupKey = tuple[str, str]  # (error source, tool id)
NO_ERRORS = {"count": 0, "people_affected": 0}


def _error_filter(span: Span, tool_id: str | None) -> ColumnElement[bool]:
    conditions = [events.c.name == "error", in_span(span)]
    if tool_id is not None:
        conditions.append(events.c.tool_id == tool_id)
    return and_(*conditions)


def _error_measures(
    connection: Connection, span: Span, tool_id: str | None
) -> dict[GroupKey, dict[str, int]]:
    query = (
        select(
            events.c.error_source,
            events.c.tool_id,
            func.count(),
            func.count(distinct(events.c.user_id)),
        )
        .where(_error_filter(span, tool_id))
        .group_by(events.c.error_source, events.c.tool_id)
    )
    return {
        (source, tool): {"count": count, "people_affected": people}
        for source, tool, count, people in connection.execute(query)
    }


def _affected_names(
    connection: Connection, span: Span, tool_id: str | None
) -> dict[GroupKey, list[str]]:
    query = (
        select(events.c.error_source, events.c.tool_id, users.c.name)
        .join(users, users.c.id == events.c.user_id)
        .where(_error_filter(span, tool_id))
        .distinct()
    )
    names: dict[GroupKey, list[str]] = {}
    for source, tool, name in connection.execute(query):
        names.setdefault((source, tool), []).append(name)
    # Sorted here rather than by the database: collations differ between engines.
    return {key: sorted(group) for key, group in names.items()}


def errors_seen(
    db: Database, window: Window, tool_id: ToolId | None = None, with_previous: bool = False
) -> list[ErrorGroup]:
    span = window_span(db.as_of, window)
    with db.connect() as connection:
        current = _error_measures(connection, span, tool_id)
        previous = (
            _error_measures(connection, window_span(db.as_of, window, previous=True), tool_id)
            if with_previous
            else None
        )
        affected = _affected_names(connection, span, tool_id)
        tool_names: dict[str, str] = {}
        for tid, name in connection.execute(select(tools.c.id, tools.c.name)):
            tool_names[tid] = name
    # With a previous window, a group that has gone away still shows, at zero.
    keys = set(current) | set(previous or {})
    groups = [
        ErrorGroup(
            source=source,
            tool_id=tool,
            tool_name=tool_names[tool],
            affected=affected.get((source, tool), []),
            **current.get((source, tool), NO_ERRORS),
            **changes(
                current.get((source, tool), NO_ERRORS),
                previous.get((source, tool), NO_ERRORS) if previous is not None else None,
            ),
        )
        for source, tool in keys
    ]
    return sorted(groups, key=lambda g: (-g.count, g.source, g.tool_id))


# --- roster --------------------------------------------------------------------------


def _login_counts(connection: Connection, span: Span) -> dict[str, tuple[int, int]]:
    """Per person: logins inside the span, and logins before it started."""
    is_login = events.c.name == "login"
    query = (
        select(
            users.c.id,
            count_if(and_(is_login, in_span(span))),
            count_if(and_(is_login, events.c.ts < span[0])),
        )
        .select_from(users.outerjoin(events, events.c.user_id == users.c.id))
        .group_by(users.c.id)
    )
    return {user_id: (inside, before) for user_id, inside, before in connection.execute(query)}


def _has_history_before(connection: Connection, moment: datetime) -> bool:
    earliest = connection.execute(select(func.min(events.c.ts))).scalar_one()
    return earliest is not None and earliest < moment


def roster(db: Database, window: Window, with_previous: bool = False) -> Roster:
    span = window_span(db.as_of, window)
    previous_span = window_span(db.as_of, window, previous=True)
    with db.connect() as connection:
        counts = _login_counts(connection, span)
        previous_counts = _login_counts(connection, previous_span) if with_previous else None
        # "Went quiet" needs logins before the window. If the data does not reach back
        # past the previous window, its previous value is unknown, not zero.
        previous_quiet_known = _has_history_before(connection, previous_span[0])
        last_seen = last_seen_by_user(connection, db.as_of)
        people = [
            RosterPerson(user_id=uid, name=name, client_name=client, last_seen=last_seen.get(uid))
            for uid, name, client in connection.execute(
                select(users.c.id, users.c.name, clients.c.name)
                .join(clients, clients.c.id == users.c.client_id)
                .order_by(users.c.id)
            )
        ]

    active = [p for p in people if counts[p.user_id][0] > 0]
    went_quiet = [p for p in people if counts[p.user_id][0] == 0 and counts[p.user_id][1] > 0]
    never = [p for p in people if p.last_seen is None]

    extra: dict[str, int] = {}
    if previous_counts is not None:
        before = list(previous_counts.values())
        extra |= changes(
            {"active_count": len(active)},
            {"active_count": sum(1 for inside, _ in before if inside > 0)},
        )
        if previous_quiet_known:
            quiet_before = sum(1 for inside, earlier in before if inside == 0 and earlier > 0)
            extra |= changes(
                {"went_quiet_count": len(went_quiet)}, {"went_quiet_count": quiet_before}
            )
    return Roster(
        invited_count=len(people),
        active_count=len(active),
        never_showed_up_count=len(never),
        went_quiet_count=len(went_quiet),
        active=active,
        never_showed_up=never,
        went_quiet=went_quiet,
        **extra,
    )


# --- cached access -------------------------------------------------------------------


class Lookups:
    """The five lookups bound to one database, with results cached for ten minutes.

    The API and the assistant both go through this, so they can never disagree.
    """

    def __init__(self, db: Database, cache: TTLCache) -> None:
        self._db = db
        self._cache = cache

    @property
    def as_of(self) -> date:
        return self._db.as_of

    def _cached[T](self, name: str, args: tuple[object, ...], compute: Callable[[], T]) -> T:
        return self._cache.get_or_compute((name, *args), compute)

    def usage_by_tool(self, window: Window, with_previous: bool = False) -> list[ToolUsage]:
        return self._cached(
            "usage_by_tool",
            (window, with_previous),
            lambda: usage_by_tool(self._db, window, with_previous),
        )

    def activity_by_person(
        self, window: Window, user_id: str | None = None, with_previous: bool = False
    ) -> list[PersonActivity]:
        return self._cached(
            "activity_by_person",
            (window, user_id, with_previous),
            lambda: activity_by_person(self._db, window, user_id, with_previous),
        )

    def activity_by_client(
        self, window: Window, with_previous: bool = False
    ) -> list[ClientActivity]:
        return self._cached(
            "activity_by_client",
            (window, with_previous),
            lambda: activity_by_client(self._db, window, with_previous),
        )

    def errors_seen(
        self, window: Window, tool_id: ToolId | None = None, with_previous: bool = False
    ) -> list[ErrorGroup]:
        return self._cached(
            "errors_seen",
            (window, tool_id, with_previous),
            lambda: errors_seen(self._db, window, tool_id, with_previous),
        )

    def roster(self, window: Window, with_previous: bool = False) -> Roster:
        return self._cached(
            "roster", (window, with_previous), lambda: roster(self._db, window, with_previous)
        )
