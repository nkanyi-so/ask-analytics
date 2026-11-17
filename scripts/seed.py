"""Deterministic generator for the synthetic workspace.

Writes `data/events.jsonl` (the workspace and sixty days of events) and
`data/ground_truth.json` (the expected result of every lookup in every window).

Two rules shape this file:

1. Same seed, same bytes. Everything random comes from one `random.Random(seed)`;
   nothing reads the wall clock.
2. Ground truth is worked out here with plain Python loops over the event list. It
   shares no code with `backend/app/lookups.py` and uses no SQL, so the two can check
   each other.

Everything here is invented. No name, term or number comes from a real system.
"""

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

Record = dict[str, Any]

SEED = 20261030
AS_OF = date(2026, 10, 30)  # a Friday, so `today` is a working day
DAYS = 60
FIRST_DAY = AS_OF - timedelta(days=DAYS - 1)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

WINDOW_LENGTHS = {"today": 1, "7d": 7, "30d": 30}

# id, display name, headline event, how often people reach for it
TOOLS: list[tuple[str, str, str, float]] = [
    ("call_agenda", "Call agenda", "agenda_created", 3.0),
    ("contact_enrichment", "Contact enrichment", "contact_enriched", 1.5),
    ("email_drafter", "Email drafter", "email_sent", 5.0),
    ("invoice_generator", "Invoice generator", "invoice_issued", 2.5),
    ("media_plan_builder", "Media plan builder", "plan_exported", 2.0),
    ("meeting_notes", "Meeting notes", "notes_filed", 4.0),
    ("proposal_writer", "Proposal writer", "proposal_sent", 2.0),
    ("report_summariser", "Report summariser", "summary_saved", 3.0),
]
HEADLINE = {tool_id: headline for tool_id, _, headline, _ in TOOLS}

# id, name, headcount, appetite (how keenly this client uses the product)
CLIENTS: list[tuple[str, str, int, float]] = [
    ("c01", "Alder & Finch", 11, 1.0),
    ("c02", "Brightwater", 9, 0.9),
    ("c03", "Cobalt Lane", 7, 0.75),
    ("c04", "Dune Collective", 6, 0.6),
    ("c05", "Ember Works", 4, 0.45),
    ("c06", "Fjord Media", 3, 0.4),
]

FIRST_NAMES = [
    "Ada", "Bram", "Cleo", "Dara", "Elio", "Faye", "Gus", "Hana", "Ivo", "Juno",
    "Kofi", "Lena", "Milo", "Nia", "Otto", "Pia", "Quin", "Rhea", "Sami", "Tess",
    "Umar", "Vera", "Wim", "Xena", "Yara", "Zeno",
]  # fmt: skip
LAST_NAMES = [
    "Abara", "Birch", "Castell", "Dunmore", "Eklund", "Farrow", "Galvez", "Holt",
    "Ivanek", "Jarrah", "Kessler", "Lindqvist", "Marlow", "Nakata", "Okoro", "Penrose",
    "Quill", "Rosales", "Sorrel", "Thackeray",
]  # fmt: skip

# The patterns the demo and the evals depend on (docs/SPEC.md).
UNUSED_TOOL = "contact_enrichment"  # nobody touches it in the last 30 days
SPIKE_TOOL = "invoice_generator"  # errors pile up in the last 7 days...
SPIKE_SOURCE = "pdf_renderer"  # ...all from this one source
QUIET_USER = "u014"  # active on days 1 to 25, nothing after
QUIET_UNTIL_DAY = 25
NEVER_LOGGED_IN = ("u011", "u027", "u037")  # invited, never showed up
OCCASIONAL_USERS = ("u020", "u033")  # log in rarely, so short windows have some drift

BACKGROUND_ERROR_SOURCES = ("upstream_timeout", "input_validation", "rate_limit")
BACKGROUND_ERROR_RATE = 0.015
SPIKE_FAILURE_RATE = 0.75
WEEKEND_FACTOR = 0.12
SPIKE_DAYS = 7
UNUSED_DAYS = 30


# --- generation ----------------------------------------------------------------------


def day_number(day: date) -> int:
    """1 for the first day of the seed, 60 for AS_OF."""
    return (day - FIRST_DAY).days + 1


def make_users(rng: random.Random) -> list[Record]:
    names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
    rng.shuffle(names)
    users: list[Record] = []
    for client_id, _, headcount, _ in CLIENTS:
        for position in range(headcount):
            role = (
                "admin" if position == 0 else "manager" if position <= headcount // 4 else "member"
            )
            invited = date(2026, 6, 1) + timedelta(days=rng.randrange(80))
            users.append(
                {
                    "kind": "user",
                    "id": f"u{len(users) + 1:03d}",
                    "name": names[len(users)],
                    "client_id": client_id,
                    "role": role,
                    "invited_at": invited.isoformat(),
                }
            )
    return users


def login_chance(user_id: str, appetite: float, rng: random.Random) -> float:
    """Chance that this person logs in on a given weekday."""
    if user_id in OCCASIONAL_USERS:
        return 0.25
    return min(0.96, rng.uniform(0.6, 0.95) * (0.6 + 0.4 * appetite))


def tool_weights(rng: random.Random) -> dict[str, float]:
    """Each person has their own favourites around the overall popularity."""
    return {tool_id: popularity * rng.uniform(0.4, 1.6) for tool_id, _, _, popularity in TOOLS}


def pick_tool(weights: dict[str, float], day: date, rng: random.Random) -> str:
    in_unused_stretch = day > AS_OF - timedelta(days=UNUSED_DAYS)
    options = [t for t in weights if not (in_unused_stretch and t == UNUSED_TOOL)]
    return rng.choices(options, weights=[weights[t] for t in options])[0]


def session_events(tool_id: str, day: date, rng: random.Random) -> list[tuple[str, str | None]]:
    """What happens after someone opens a tool: (event name, error source) pairs."""
    events: list[tuple[str, str | None]] = [("tool_opened", None)]
    spiking = tool_id == SPIKE_TOOL and day > AS_OF - timedelta(days=SPIKE_DAYS)
    if spiking and rng.random() < SPIKE_FAILURE_RATE:
        # The renderer is down: people retry a few times and give up.
        events += [("error", SPIKE_SOURCE)] * rng.randint(1, 3)
    elif rng.random() < BACKGROUND_ERROR_RATE:
        events.append(("error", rng.choice(BACKGROUND_ERROR_SOURCES)))
    elif rng.random() < 0.8:
        events.append((HEADLINE[tool_id], None))
    return events


def user_day(
    user: Record, day: date, sessions_mean: float, weights: dict[str, float], rng: random.Random
) -> list[Record]:
    """One person's events on a day they log in, in time order."""
    moment = datetime(day.year, day.month, day.day, 8) + timedelta(seconds=rng.randrange(3 * 3600))
    events: list[tuple[datetime, str | None, str, str | None]] = [(moment, None, "login", None)]
    for _ in range(max(1, round(rng.gauss(sessions_mean, 1.0)))):
        tool_id = pick_tool(weights, day, rng)
        for name, error_source in session_events(tool_id, day, rng):
            moment += timedelta(seconds=rng.randrange(60, 40 * 60))
            events.append((moment, tool_id, name, error_source))
    return [
        {
            "kind": "event",
            "ts": ts.isoformat(timespec="seconds"),
            "user_id": user["id"],
            "client_id": user["client_id"],
            "tool_id": tool_id,
            "name": name,
            "error_source": error_source,
        }
        for ts, tool_id, name, error_source in events
    ]


def make_events(users: list[Record], rng: random.Random) -> list[Record]:
    appetite = {client_id: value for client_id, _, _, value in CLIENTS}
    events: list[Record] = []
    for user in users:
        # Drawn for everyone, even people who never log in, so adding a pattern
        # to one person does not shift the random stream for the rest.
        chance = login_chance(user["id"], appetite[user["client_id"]], rng)
        weights = tool_weights(rng)
        sessions_mean = 1.0 + 3.5 * appetite[user["client_id"]]
        for offset in range(DAYS):
            day = FIRST_DAY + timedelta(days=offset)
            today_chance = chance * (WEEKEND_FACTOR if day.weekday() >= 5 else 1.0)
            logs_in = rng.random() < today_chance
            if user["id"] in NEVER_LOGGED_IN:
                continue
            if user["id"] == QUIET_USER and day_number(day) > QUIET_UNTIL_DAY:
                continue
            if logs_in:
                events += user_day(user, day, sessions_mean, weights, rng)
    events.sort(key=lambda e: (e["ts"], e["user_id"]))
    for number, event in enumerate(events, start=1):
        event["id"] = number
    return events


def generate(seed: int) -> Record:
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security
    users = make_users(rng)
    return {
        "meta": {"kind": "meta", "as_of": AS_OF.isoformat(), "seed": seed, "days": DAYS},
        "clients": [{"kind": "client", "id": cid, "name": name} for cid, name, _, _ in CLIENTS],
        "tools": [
            {"kind": "tool", "id": tid, "name": name, "headline_event": headline}
            for tid, name, headline, _ in TOOLS
        ],
        "users": users,
        "events": make_events(users, rng),
    }


# --- ground truth: plain Python over the event list, no SQL, no app code -----------


def window_days(window: str, previous: bool = False) -> tuple[date, date]:
    """First and last day of a window, or of the equally long stretch just before it."""
    length = WINDOW_LENGTHS[window]
    end = AS_OF - timedelta(days=length) if previous else AS_OF
    return end - timedelta(days=length - 1), end


def event_day(event: Record) -> date:
    return date.fromisoformat(event["ts"][:10])


def in_days(events: list[Record], span: tuple[date, date]) -> list[Record]:
    return [e for e in events if span[0] <= event_day(e) <= span[1]]


def with_change(row: Record, current: Record, previous: Record) -> Record:
    """Add each measure, its previous-window value and the difference to a row."""
    for measure, value in current.items():
        row[measure] = value
        row[f"{measure}_previous"] = previous[measure]
        row[f"{measure}_change"] = value - previous[measure]
    return row


def last_seen_by_user(events: list[Record]) -> dict[str, str]:
    seen: dict[str, str] = {}
    for event in events:
        if event["name"] == "login":
            day = event["ts"][:10]
            seen[event["user_id"]] = max(seen.get(event["user_id"], day), day)
    return seen


def tool_measures(events: list[Record], tool: Record) -> Record:
    on_tool = [e for e in events if e["tool_id"] == tool["id"]]
    return {
        "headline_count": sum(1 for e in on_tool if e["name"] == tool["headline_event"]),
        "active_people": len({e["user_id"] for e in on_tool}),
        "errors": sum(1 for e in on_tool if e["name"] == "error"),
    }


def truth_usage_by_tool(data: Record, window: str) -> list[Record]:
    current = in_days(data["events"], window_days(window))
    previous = in_days(data["events"], window_days(window, previous=True))
    return [
        with_change(
            {"tool_id": t["id"], "tool_name": t["name"], "headline_event": t["headline_event"]},
            tool_measures(current, t),
            tool_measures(previous, t),
        )
        for t in sorted(data["tools"], key=lambda t: t["id"])
    ]


def person_measures(events: list[Record], user_id: str, headlines: set[str]) -> Record:
    theirs = [e for e in events if e["user_id"] == user_id]
    return {
        "logins": sum(1 for e in theirs if e["name"] == "login"),
        "outputs": sum(1 for e in theirs if e["name"] in headlines),
    }


def truth_activity_by_person(data: Record, window: str) -> list[Record]:
    current = in_days(data["events"], window_days(window))
    previous = in_days(data["events"], window_days(window, previous=True))
    headlines = {t["headline_event"] for t in data["tools"]}
    client_name = {c["id"]: c["name"] for c in data["clients"]}
    last_seen = last_seen_by_user(data["events"])
    rows = []
    for user in sorted(data["users"], key=lambda u: u["id"]):
        row = {
            "user_id": user["id"],
            "name": user["name"],
            "client_id": user["client_id"],
            "client_name": client_name[user["client_id"]],
            "role": user["role"],
            "last_seen": last_seen.get(user["id"]),
        }
        rows.append(
            with_change(
                row,
                person_measures(current, user["id"], headlines),
                person_measures(previous, user["id"], headlines),
            )
        )
    return rows


def client_measures(events: list[Record], client_id: str, headlines: set[str]) -> Record:
    theirs = [e for e in events if e["client_id"] == client_id]
    return {
        "active_people": len({e["user_id"] for e in theirs if e["name"] == "login"}),
        "outputs": sum(1 for e in theirs if e["name"] in headlines),
    }


def truth_activity_by_client(data: Record, window: str) -> list[Record]:
    current = in_days(data["events"], window_days(window))
    previous = in_days(data["events"], window_days(window, previous=True))
    headlines = {t["headline_event"] for t in data["tools"]}
    return [
        with_change(
            {"client_id": c["id"], "client_name": c["name"]},
            client_measures(current, c["id"], headlines),
            client_measures(previous, c["id"], headlines),
        )
        for c in sorted(data["clients"], key=lambda c: c["id"])
    ]


def error_groups(events: list[Record]) -> dict[tuple[str, str], list[Record]]:
    groups: dict[tuple[str, str], list[Record]] = {}
    for event in events:
        if event["name"] == "error":
            groups.setdefault((event["error_source"], event["tool_id"]), []).append(event)
    return groups


def truth_errors_seen(data: Record, window: str) -> list[Record]:
    current = error_groups(in_days(data["events"], window_days(window)))
    previous = error_groups(in_days(data["events"], window_days(window, previous=True)))
    tool_name = {t["id"]: t["name"] for t in data["tools"]}
    user_name = {u["id"]: u["name"] for u in data["users"]}
    rows = []
    for source, tool_id in set(current) | set(previous):
        now = current.get((source, tool_id), [])
        before = previous.get((source, tool_id), [])
        people = {e["user_id"] for e in now}
        row = with_change(
            {"source": source, "tool_id": tool_id, "tool_name": tool_name[tool_id]},
            {"count": len(now), "people_affected": len(people)},
            {"count": len(before), "people_affected": len({e["user_id"] for e in before})},
        )
        row["affected"] = sorted(user_name[user_id] for user_id in people)
        rows.append(row)
    return sorted(rows, key=lambda r: (-r["count"], r["source"], r["tool_id"]))


def roster_groups(data: Record, span: tuple[date, date]) -> dict[str, set[str]]:
    logins = [e for e in data["events"] if e["name"] == "login"]
    inside = {e["user_id"] for e in logins if span[0] <= event_day(e) <= span[1]}
    before = {e["user_id"] for e in logins if event_day(e) < span[0]}
    ever = {e["user_id"] for e in logins}
    everyone = {u["id"] for u in data["users"]}
    return {"active": inside, "never_showed_up": everyone - ever, "went_quiet": before - inside}


def truth_roster(data: Record, window: str) -> Record:
    current = roster_groups(data, window_days(window))
    previous = roster_groups(data, window_days(window, previous=True))
    client_name = {c["id"]: c["name"] for c in data["clients"]}
    last_seen = last_seen_by_user(data["events"])

    def people(ids: set[str]) -> list[Record]:
        return [
            {
                "user_id": u["id"],
                "name": u["name"],
                "client_name": client_name[u["client_id"]],
                "last_seen": last_seen.get(u["id"]),
            }
            for u in sorted(data["users"], key=lambda u: u["id"])
            if u["id"] in ids
        ]

    roster: Record = {
        "invited_count": len(data["users"]),
        "never_showed_up_count": len(current["never_showed_up"]),
    }
    with_change(
        roster,
        {"active_count": len(current["active"]), "went_quiet_count": len(current["went_quiet"])},
        {"active_count": len(previous["active"]), "went_quiet_count": len(previous["went_quiet"])},
    )
    if window_days(window, previous=True)[0] <= FIRST_DAY:
        # Going quiet needs history before the window. Nothing precedes the previous
        # 30 days, so "nobody had gone quiet then" would be an artefact, not a fact.
        roster["went_quiet_count_previous"] = None
        roster["went_quiet_count_change"] = None
    for group, ids in current.items():
        roster[group] = people(ids)
    return roster


def truth_activity_over_time(data: Record, window: str) -> Record:
    """Activity bucket by bucket, for the dashboard's charts: by hour for today, else by day."""
    first, last = window_days(window)
    events = in_days(data["events"], (first, last))
    previous = in_days(data["events"], window_days(window, previous=True))
    tool_ids = sorted(tool["id"] for tool in data["tools"])

    def is_output(event: Record) -> bool:
        return event["tool_id"] is not None and event["name"] == HEADLINE[event["tool_id"]]

    if window == "today":
        unit, labels = "hour", [f"{hour:02d}:00" for hour in range(24)]

        def bucket_of(event: Record) -> str:
            return str(event["ts"])[11:13] + ":00"
    else:
        unit = "day"
        labels = [(first + timedelta(days=n)).isoformat() for n in range((last - first).days + 1)]

        def bucket_of(event: Record) -> str:
            return str(event["ts"])[:10]

    buckets = []
    for label in labels:
        inside = [e for e in events if bucket_of(e) == label]
        buckets.append(
            {
                "label": label,
                "active_people": len({e["user_id"] for e in inside if e["name"] == "login"}),
                "outputs": sum(1 for e in inside if is_output(e)),
                "errors": sum(1 for e in inside if e["name"] == "error"),
                "outputs_by_tool": {
                    tool_id: sum(1 for e in inside if is_output(e) and e["tool_id"] == tool_id)
                    for tool_id in tool_ids
                },
            }
        )
    outputs = sum(1 for e in events if is_output(e))
    outputs_previous = sum(1 for e in previous if is_output(e))
    errors = sum(1 for e in events if e["name"] == "error")
    errors_previous = sum(1 for e in previous if e["name"] == "error")
    return {
        "unit": unit,
        "buckets": buckets,
        "outputs": outputs,
        "outputs_previous": outputs_previous,
        "outputs_change": outputs - outputs_previous,
        "errors": errors,
        "errors_previous": errors_previous,
        "errors_change": errors - errors_previous,
    }


def ground_truth(data: Record) -> Record:
    lookups = {
        "usage_by_tool": truth_usage_by_tool,
        "activity_by_person": truth_activity_by_person,
        "activity_by_client": truth_activity_by_client,
        "errors_seen": truth_errors_seen,
        "roster": truth_roster,
    }
    return {
        "as_of": data["meta"]["as_of"],
        "seed": data["meta"]["seed"],
        "days": DAYS,
        "patterns": {
            "unused_tool": UNUSED_TOOL,
            "quiet_user": QUIET_USER,
            "never_logged_in": list(NEVER_LOGGED_IN),
            "error_tool": SPIKE_TOOL,
            "error_source": SPIKE_SOURCE,
        },
        # Every row carries the previous-window values and the change. A lookup called
        # without `with_previous` returns the same rows minus those fields, with one
        # difference: `errors_seen` then leaves out groups whose current count is zero
        # (they are only listed here because they had errors in the previous window).
        "lookups": {
            name: {window: compute(data, window) for window in WINDOW_LENGTHS}
            for name, compute in lookups.items()
        },
        # The dashboard's charts. Not one of the assistant's five lookups, so it is kept
        # apart from them: it takes no `with_previous` and always carries its totals.
        "series": {
            "activity_over_time": {
                window: truth_activity_over_time(data, window) for window in WINDOW_LENGTHS
            }
        },
    }


# --- output --------------------------------------------------------------------------


def to_line(record: Record) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def render_events(data: Record) -> bytes:
    records = [data["meta"], *data["clients"], *data["tools"], *data["users"], *data["events"]]
    return "".join(to_line(record) + "\n" for record in records).encode()


def render_ground_truth(truth: Record) -> bytes:
    return (json.dumps(truth, sort_keys=True, indent=1, ensure_ascii=True) + "\n").encode()


def build(seed: int) -> tuple[bytes, bytes]:
    """The exact bytes of events.jsonl and ground_truth.json for a seed."""
    data = generate(seed)
    return render_events(data), render_ground_truth(ground_truth(data))


def main() -> None:
    events, truth = build(SEED)
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "events.jsonl").write_bytes(events)
    (DATA_DIR / "ground_truth.json").write_bytes(truth)
    print(f"seed {SEED}: {events.count(b'\n')} lines, as of {AS_OF.isoformat()}")


if __name__ == "__main__":
    main()
