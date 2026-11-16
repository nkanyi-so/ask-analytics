"""The Monday summary: last week next to the week before, as one HTML page.

"Last week" is the `7d` window ending on `AS_OF`, the same window the dashboard shows,
so the page and the summary can never disagree. Every number is a field of a lookup
result asked for with `with_previous=True`; nothing is added up or subtracted here.
Sending it by email is not built: the endpoint returns the HTML and stops there.
"""

from html import escape

from app.lookups import Lookups, Window

WINDOW: Window = "7d"


def change(value: int | None) -> str:
    """Word the sign of a difference the lookup already worked out."""
    if value is None:
        return "no earlier data"
    return "no change" if value == 0 else f"{value:+d}"


def cell(value: object) -> str:
    return f"<td>{escape(str(value))}</td>"


def table(headings: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{escape(heading)}</th>" for heading in headings)
    body = "".join(f"<tr>{''.join(cell(value) for value in row)}</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def names(people: list[str]) -> str:
    return escape(", ".join(people)) if people else "nobody"


def render_summary(lookups: Lookups) -> str:
    roster = lookups.roster(WINDOW, with_previous=True)
    tools = lookups.usage_by_tool(WINDOW, with_previous=True)
    clients = lookups.activity_by_client(WINDOW, with_previous=True)
    errors = lookups.errors_seen(WINDOW, with_previous=True)
    as_of = escape(lookups.as_of.isoformat())

    people = table(
        ["", "Last 7 days", "7 days before", "Change"],
        [
            [
                "Active",
                roster.active_count,
                roster.active_count_previous,
                change(roster.active_count_change),
            ],
            [
                "Went quiet",
                roster.went_quiet_count,
                roster.went_quiet_count_previous,
                change(roster.went_quiet_count_change),
            ],
        ],
    )
    tool_rows: list[list[object]] = [
        [
            row.tool_name,
            row.headline_count,
            row.headline_count_previous,
            change(row.headline_count_change),
            row.active_people,
            row.errors,
        ]
        for row in tools
    ]
    client_rows: list[list[object]] = [
        [
            row.client_name,
            row.outputs,
            row.outputs_previous,
            change(row.outputs_change),
            row.active_people,
        ]
        for row in clients
    ]
    error_rows: list[list[object]] = [
        [
            row.source,
            row.tool_name,
            row.count,
            row.count_previous,
            change(row.count_change),
            row.people_affected,
        ]
        for row in errors
    ]
    errors_html = (
        table(
            ["Source", "Tool", "Errors", "7 days before", "Change", "People affected"], error_rows
        )
        if error_rows
        else "<p>No errors in either week.</p>"
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Weekly summary, week ending {as_of}</title></head>
<body>
<h1>Weekly summary</h1>
<p>The last 7 days, ending {as_of}, next to the 7 days before. Seeded demo data.</p>
<h2>People</h2>
{people}
<p>Invited: {roster.invited_count}. Never showed up: {roster.never_showed_up_count} \
({names([person.name for person in roster.never_showed_up])}).</p>
<p>Went quiet: {names([person.name for person in roster.went_quiet])}.</p>
<h2>Headline number per tool</h2>
{table(["Tool", "Last 7 days", "7 days before", "Change", "Active people", "Errors"], tool_rows)}
<h2>Clients</h2>
{table(["Client", "Outputs", "7 days before", "Change", "Active people"], client_rows)}
<h2>Errors</h2>
{errors_html}
</body>
</html>
"""
