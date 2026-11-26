"""The assistant loop, driven by the fixture client. No test here can reach a live model."""

import json
import logging
from datetime import date
from typing import Any

import pytest

from app.assistant import (
    MAX_TOOL_CALLS,
    REFUSAL_TEXT,
    TOOL_SPECS,
    answer_question,
    digits_for_words,
    run_lookup,
    system_prompt,
    unsupported_numbers,
)
from app.cache import TTLCache
from app.db import Database
from app.llm import Fixture, FixtureClient, ModelReply, ToolCall
from app.lookups import Lookups
from app.registry import CATALOG

INVOICES_7D = {
    "call": 0,
    "list": "rows",
    "where": {"tool_id": "invoice_generator"},
    "field": "headline_count",
}
USAGE_7D = {"name": "usage_by_tool", "input": {"window": "7d", "with_previous": False}}


@pytest.fixture
def lookups(database: Database) -> Lookups:
    return Lookups(database, TTLCache())


def client_for(question: str, fixture: Fixture) -> FixtureClient:
    return FixtureClient({question.lower(): fixture})


def test_a_correct_answer_carries_the_number_from_the_lookup(
    lookups: Lookups, truth: dict[str, Any]
) -> None:
    question = "How many invoices were issued in the last 7 days?"
    fixture = Fixture(
        calls=[USAGE_7D],
        answer="{0} invoices were issued in the last 7 days.",
        values=[INVOICES_7D],
    )
    expected = next(
        row["headline_count"]
        for row in truth["lookups"]["usage_by_tool"]["7d"]
        if row["tool_id"] == "invoice_generator"
    )

    result = answer_question(question, client_for(question, fixture), lookups)

    assert result.refused is False
    assert result.answer == f"{expected} invoices were issued in the last 7 days."
    assert result.window == "7d"
    assert [(call.name, call.window) for call in result.lookups_called] == [("usage_by_tool", "7d")]
    assert result.cost_usd == 0.0
    assert result.latency_ms >= 0


def test_a_question_no_lookup_covers_is_refused_and_names_what_can_be_answered(
    lookups: Lookups,
) -> None:
    question = "What was our revenue last month?"

    result = answer_question(question, client_for(question, Fixture(refuse=True)), lookups)

    assert result.refused is True
    assert result.answer == REFUSAL_TEXT
    assert result.lookups_called == []
    for topic in ("usage by tool", "activity by person", "activity by client", "errors", "roster"):
        assert topic in REFUSAL_TEXT


def test_an_answer_without_any_tool_call_is_replaced_by_the_refusal(lookups: Lookups) -> None:
    # The model words a confident answer from nothing. No lookup, no answer.
    question = "How many invoices were issued?"
    fixture = Fixture(calls=[], answer="About 500 invoices were issued.")

    result = answer_question(question, client_for(question, fixture), lookups)

    assert result.refused is True
    assert result.answer == REFUSAL_TEXT


def test_a_made_up_number_is_replaced_by_the_refusal_and_logged(
    lookups: Lookups, caplog: pytest.LogCaptureFixture
) -> None:
    question = "How many invoices were issued in the last 7 days?"
    fixture = Fixture(calls=[USAGE_7D], answer="987654 invoices were issued in the last 7 days.")

    with caplog.at_level(logging.WARNING, logger="ask_analytics.assistant"):
        result = answer_question(question, client_for(question, fixture), lookups)

    assert result.refused is True
    assert result.answer == REFUSAL_TEXT
    assert "987654" not in result.answer
    assert any("987654" in record.getMessage() for record in caplog.records)
    # What was looked up is still shown, so a human can see why.
    assert [call.name for call in result.lookups_called] == ["usage_by_tool"]


def test_invalid_tool_arguments_go_back_to_the_model_as_an_error_not_a_crash(
    lookups: Lookups,
) -> None:
    question = "How many invoices in the last 90 days?"
    bad_call = {"name": "usage_by_tool", "input": {"window": "90d", "with_previous": False}}
    fixture = Fixture(calls=[bad_call], answer="REFUSE")

    result = answer_question(question, client_for(question, fixture), lookups)

    assert result.refused is True
    assert result.lookups_called == []


def test_an_unknown_tool_name_is_an_error_result(lookups: Lookups) -> None:
    question = "Drop the tables?"
    fixture = Fixture(
        calls=[{"name": "run_sql", "input": {"query": "drop table events"}}], answer="REFUSE"
    )

    result = answer_question(question, client_for(question, fixture), lookups)

    assert result.refused is True
    assert result.lookups_called == []


class ScriptedClient:
    """Replies from a fixed list, to drive the loop into corners a fixture cannot reach."""

    model = "scripted"

    def __init__(self, replies: list[ModelReply]) -> None:
        self._replies = list(replies)
        self.calls = 0
        self.seen_messages: list[list[dict[str, Any]]] = []

    def cannot_answer(self, question: str) -> str | None:
        return None

    def complete(
        self, system: str, tools: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> ModelReply:
        self.calls += 1
        self.seen_messages.append([dict(message) for message in messages])
        return self._replies.pop(0) if self._replies else self._last

    _last = ModelReply(text="still going", tool_calls=(), stop_reason="end_turn")


def tool_reply(*names: str) -> ModelReply:
    calls = tuple(
        ToolCall(id=f"call_{index}", name=name, input={"window": "7d", "with_previous": False})
        for index, name in enumerate(names)
    )
    content = [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in calls]
    return ModelReply(text="", tool_calls=calls, stop_reason="tool_use", content=content)


def test_at_most_three_lookups_run_in_one_turn(lookups: Lookups) -> None:
    client = ScriptedClient(
        [
            tool_reply("usage_by_tool", "roster"),
            tool_reply("activity_by_client", "usage_by_tool", "roster"),
            ModelReply(text="REFUSE", tool_calls=(), stop_reason="end_turn"),
        ]
    )

    result = answer_question("anything", client, lookups)

    assert result.refused is True
    assert len(result.lookups_called) == 3
    last_results = client.seen_messages[-1][-1]["content"]
    flags = [bool(block.get("is_error")) for block in last_results]
    assert flags == [False, True, True], "only the third call runs; the rest are told to stop"
    assert MAX_TOOL_CALLS == 3


def test_a_model_that_never_stops_calling_tools_ends_in_a_refusal(lookups: Lookups) -> None:
    client = ScriptedClient([tool_reply("roster") for _ in range(20)])

    result = answer_question("anything", client, lookups)

    assert result.refused is True
    assert client.calls <= MAX_TOOL_CALLS + 2


def test_a_refusal_stop_reason_is_a_refusal(lookups: Lookups) -> None:
    client = ScriptedClient([ModelReply(text="", tool_calls=(), stop_reason="refusal")])

    result = answer_question("anything", client, lookups)

    assert result.refused is True
    assert result.answer == REFUSAL_TEXT


def test_a_truncated_reply_is_a_refusal(lookups: Lookups) -> None:
    client = ScriptedClient(
        [
            tool_reply("roster"),
            ModelReply(text="There were 3", tool_calls=(), stop_reason="max_tokens"),
        ]
    )

    assert answer_question("anything", client, lookups).refused is True


def test_tool_results_go_back_in_one_message_and_the_assistant_turn_is_unchanged(
    lookups: Lookups,
) -> None:
    first = tool_reply("usage_by_tool", "roster")
    client = ScriptedClient(
        [first, ModelReply(text="REFUSE", tool_calls=(), stop_reason="end_turn")]
    )

    answer_question("anything", client, lookups)

    messages = client.seen_messages[-1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[1]["content"] is first.content
    assert [block["tool_use_id"] for block in messages[2]["content"]] == ["call_0", "call_1"]


def question_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    """Every log record of the assistant, each of which must be one JSON object."""
    return [
        json.loads(r.getMessage()) for r in caplog.records if r.name == "ask_analytics.assistant"
    ]


def test_an_answered_question_logs_one_json_line_with_its_request_id(
    lookups: Lookups, caplog: pytest.LogCaptureFixture
) -> None:
    question = "How many invoices were issued in the last 7 days?"
    fixture = Fixture(calls=[USAGE_7D], answer="{0} invoices.", values=[INVOICES_7D])

    with caplog.at_level(logging.INFO, logger="ask_analytics.assistant"):
        result = answer_question(question, client_for(question, fixture), lookups)

    (line,) = question_lines(caplog)
    assert line["event"] == "question"
    assert line["outcome"] == "answered"
    assert line["question"] == question
    assert line["lookups"] == [{"name": "usage_by_tool", "window": "7d"}]
    assert line["model_calls"] == 2
    assert line["request_id"] == result.request_id
    assert len(result.request_id) == 12
    assert line["latency_ms"] == result.latency_ms
    for field in ("time", "model", "input_tokens", "output_tokens", "cost_usd"):
        assert field in line


def test_the_log_line_adds_up_tokens_and_cost_across_model_calls(
    lookups: Lookups, caplog: pytest.LogCaptureFixture
) -> None:
    class Priced(ScriptedClient):
        model = "claude-haiku-5-5"

    client = Priced(
        [
            ModelReply(
                text="",
                tool_calls=(ToolCall(id="c0", name="roster", input=dict(USAGE_7D["input"])),),
                stop_reason="tool_use",
                input_tokens=1000,
                output_tokens=100,
            ),
            ModelReply(
                text="REFUSE",
                tool_calls=(),
                stop_reason="end_turn",
                input_tokens=2000,
                output_tokens=50,
            ),
        ]
    )

    with caplog.at_level(logging.INFO, logger="ask_analytics.assistant"):
        result = answer_question("anything", client, lookups)

    (line,) = question_lines(caplog)
    assert (line["input_tokens"], line["output_tokens"]) == (3000, 150)
    assert line["cost_usd"] == pytest.approx(result.cost_usd)
    assert result.cost_usd > 0
    assert line["outcome"] == "refused_by_model"
    assert line["reply"] == "REFUSE"


def test_a_number_check_refusal_logs_the_unsupported_numbers_as_a_warning(
    lookups: Lookups, caplog: pytest.LogCaptureFixture
) -> None:
    question = "How many invoices were issued in the last 7 days?"
    fixture = Fixture(calls=[USAGE_7D], answer="987654 invoices were issued in the last 7 days.")

    with caplog.at_level(logging.WARNING, logger="ask_analytics.assistant"):
        result = answer_question(question, client_for(question, fixture), lookups)

    (line,) = question_lines(caplog)
    assert line["outcome"] == "refused_by_number_check"
    assert line["unsupported_numbers"] == ["987654"]
    assert "987654" in line["rejected_answer"]
    assert line["request_id"] == result.request_id
    assert result.refused is True


def test_other_refusals_and_a_model_outage_each_log_one_line_with_a_reason(
    lookups: Lookups, caplog: pytest.LogCaptureFixture
) -> None:
    from app.llm import ModelUnavailable

    class Down(ScriptedClient):
        def complete(self, system: str, tools: list[Any], messages: list[Any]) -> ModelReply:
            raise ModelUnavailable("APITimeoutError")

    with caplog.at_level(logging.INFO, logger="ask_analytics.assistant"):
        answer_question("Never recorded?", FixtureClient({}), lookups)
        with pytest.raises(ModelUnavailable):
            answer_question("anything", Down([]), lookups)

    unrecorded, outage = question_lines(caplog)
    assert (unrecorded["outcome"], unrecorded["reason"]) == ("refused_other", "no_recorded_answer")
    assert (outage["outcome"], outage["reason"]) == ("model_unavailable", "APITimeoutError")
    assert unrecorded["request_id"] != outage["request_id"]


def test_a_question_the_fixture_client_has_no_recording_for_says_so(lookups: Lookups) -> None:
    result = answer_question("Never recorded?", FixtureClient({}), lookups)

    assert result.refused is True
    assert "live model is not connected" in result.answer
    assert result.answer != REFUSAL_TEXT


def test_refuse_anywhere_in_the_reply_is_a_refusal(lookups: Lookups) -> None:
    client = ScriptedClient(
        [
            tool_reply("roster"),
            ModelReply(
                text="After checking, I must REFUSE this.", tool_calls=(), stop_reason="end_turn"
            ),
        ]
    )

    assert answer_question("anything", client, lookups).answer == REFUSAL_TEXT


def test_cost_is_reported_per_model_call(lookups: Lookups) -> None:
    question = "How many invoices were issued in the last 7 days?"
    fixture = Fixture(calls=[USAGE_7D], answer="{0} invoices.", values=[INVOICES_7D])
    costs: list[float] = []

    answer_question(question, client_for(question, fixture), lookups, on_cost=costs.append)

    assert costs == [0.0, 0.0]


# --- the number check ----------------------------------------------------------------

RESULTS = [
    '{"as_of": "2026-10-30", "rows": [{"user_id": "u014", "count": 86, "change": -41, '
    '"last_seen": "2026-09-25", "ok": true}]}'
]
ROSTER_LIKE = [
    '{"as_of": "2026-10-30", "active_count": 35, "active": [{"user_id": "u012", "name": "A"}, '
    '{"user_id": "u031", "name": "B"}]}'
]


@pytest.mark.parametrize(
    "answer",
    [
        "There were 86 errors.",
        "Down by 41 in the last 7 days.",
        "It changed by -41.",
        "86 errors over the last 30 days, as of 30 October 2026.",
        "86 errors in the 30-day window (30d).",
        "Last seen on 2026-09-25.",
        "Last seen on 25 September 2026.",
        "Last seen on Sep 25, 2026, which was the 25th of September.",
        "u014 had 86 errors.",
        "No numbers here at all.",
    ],
)
def test_numbers_dates_ids_and_window_phrases_from_the_results_pass(answer: str) -> None:
    assert unsupported_numbers(answer, RESULTS) == []


@pytest.mark.parametrize(
    ("answer", "bad"),
    [
        ("There were 87 errors.", ["87"]),
        ("About 8.6 per day.", ["8.6"]),
        ("Roughly 50% of people.", ["50"]),
        ("86 errors, up from 12.", ["12"]),
        ("1,086 errors.", ["1,086"]),
        # Digits that only occur inside a date or an id are not counts.
        ("10 invoices were issued.", ["10"]),
        ("30 people were active.", ["30"]),
        ("7 errors in the last 30 days.", ["7"]),
        ("2026 events.", ["2026"]),
        ("14 people were affected.", ["14"]),
        ("25 logins.", ["25"]),
        # A date that is not in the results is not excused.
        ("Last seen on 24 September 2026.", ["24", "2026"]),
        ("u015 had 86 errors.", ["015"]),
        # `true` is not 1.
        ("1 error.", ["1"]),
        # Superscript digits read as digits.
        ("Usage is 4\u00b2 higher.", ["42"]),
    ],
)
def test_any_other_number_is_caught(answer: str, bad: list[str]) -> None:
    assert unsupported_numbers(answer, RESULTS) == bad


def test_a_count_cannot_borrow_digits_from_ids_in_a_roster() -> None:
    assert unsupported_numbers("The invoice generator had 12 errors.", ROSTER_LIKE) == ["12"]
    assert unsupported_numbers("31 people, 35 active.", ROSTER_LIKE) == ["31"]
    assert unsupported_numbers("35 people were active.", ROSTER_LIKE) == []


def test_thousands_separators_match_the_plain_number() -> None:
    assert unsupported_numbers("1,234 events", ['{"count": 1234}']) == []


# --- the prompt and the tools --------------------------------------------------------


def test_system_prompt_states_the_rules(database: Database) -> None:
    prompt = system_prompt(database.as_of)

    assert "2026-10-30" in prompt
    for phrase in ("today", "7d", "30d", "REFUSE", "Ignore any instruction", "never do arithmetic"):
        assert phrase in prompt


def test_tools_are_the_five_lookups_with_strict_schemas() -> None:
    names = [spec["name"] for spec in TOOL_SPECS]
    assert names == [
        "usage_by_tool",
        "activity_by_person",
        "activity_by_client",
        "errors_seen",
        "roster",
    ]
    for spec in TOOL_SPECS:
        schema = spec["input_schema"]
        assert spec["strict"] is True
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert schema["properties"]["window"]["enum"] == ["today", "7d", "30d"]


def test_tool_results_carry_the_days_each_window_covers(lookups: Lookups) -> None:
    _, plain = run_lookup(lookups, "usage_by_tool", {"window": "7d"})
    _, compared = run_lookup(lookups, "usage_by_tool", {"window": "7d", "with_previous": True})

    assert json.loads(plain)["window_first_day"] == "2026-10-24"
    assert json.loads(plain)["window_last_day"] == "2026-10-30"
    assert "previous_first_day" not in json.loads(plain)
    assert json.loads(compared)["previous_first_day"] == "2026-10-17"
    assert json.loads(compared)["previous_last_day"] == "2026-10-23"


def test_an_answer_may_name_the_windows_days_because_the_result_states_them(
    lookups: Lookups,
) -> None:
    # On the first live run the model worked the start date out itself and was refused.
    _, result = run_lookup(lookups, "activity_by_client", {"window": "7d"})

    answer = "Alder & Finch produced 122 outputs in the last 7 days (2026-10-24 to 2026-10-30)."
    assert unsupported_numbers(answer, [result]) == []
    assert unsupported_numbers(answer.replace("10-24", "10-23"), [result]) != []


def test_a_window_named_without_its_unit_is_allowed_only_as_the_thing_compared_with(
    lookups: Lookups,
) -> None:
    # Refused three times out of three on the second live run: "the previous 30".
    _, real_month = run_lookup(lookups, "usage_by_tool", {"window": "30d", "with_previous": True})
    said = "Summaries went up over the last 30 days compared with the previous 30 (2026-09-01 to 2026-09-30), from 195 to 245, an increase of 50."
    assert unsupported_numbers(said, [real_month]) == []

    # Hand-made results, so the only numbers in them are the ones written here.
    month = '{"window": "30d", "previous_first_day": "2026-09-01", "rows": [{"errors": 86}]}'
    week = '{"window": "7d", "previous_first_day": "2026-10-17", "rows": [{"errors": 86}]}'
    week_alone = '{"window": "7d", "rows": [{"errors": 86}]}'
    assert unsupported_numbers("Up, compared with the previous 30.", [month]) == []
    # Only for a window this turn really compared.
    assert unsupported_numbers("Up, compared with the previous 30.", [week]) == ["30"]
    assert unsupported_numbers("Up, compared with the previous 7.", [week_alone]) == ["7"]
    # And never where a previous value would sit.
    assert unsupported_numbers("86 errors, up from the prior 7.", [week]) == ["7"]
    assert unsupported_numbers("Errors: 86, up from the previous 7.", [week]) == ["7"]
    assert unsupported_numbers("86 errors compared with the previous 7 errors.", [week]) == ["7"]
    assert unsupported_numbers("The last 30 invoices failed.", [month]) == ["30"]


def test_the_prompt_names_every_tool_and_what_it_counts() -> None:
    # Without this the live model refused "how many emails were sent" as unanswerable.
    prompt = system_prompt(date(2026, 10, 30))

    for entry in CATALOG:
        assert f"{entry.name} (id {entry.id}): counts {entry.headline_event}" in prompt


def test_a_number_written_as_a_word_is_held_to_the_same_rule() -> None:
    # The live model writes "Three people" whatever the prompt says about digits.
    roster_result = '{"never_showed_up_count": 3, "active_count": 35, "x": 20, "y": 2}'

    assert unsupported_numbers("Three people never showed up.", [roster_result]) == []
    assert unsupported_numbers("Twelve people never showed up.", [roster_result]) == ["Twelve"]
    assert unsupported_numbers("No one else, and not one error.", [roster_result]) == []
    # "twenty-two" is 22, not a 20 and a 2 that happen to be in the result.
    assert unsupported_numbers("Twenty-two errors.", [roster_result]) == ["Twenty-two"]
    assert unsupported_numbers("Thirty-five people are active.", [roster_result]) == []
    assert unsupported_numbers("Forty people, hundreds of events.", [roster_result]) == ["Forty"]
    assert unsupported_numbers("About a hundred errors.", [roster_result]) == ["hundred"]
    # A window's length in words is a window, as it is in digits.
    assert unsupported_numbers("In the last seven days, 35 were active.", [roster_result]) == []
    assert unsupported_numbers("Over thirty days, 35 were active.", [roster_result]) == []


def test_number_words_map_to_the_right_numbers() -> None:
    spelled = (
        "two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen twenty"
    )
    assert digits_for_words(spelled) == " ".join(str(n) for n in range(2, 21))
    assert digits_for_words("twenty-one, forty two and ninety-nine") == "21, 42 and 99"
    assert digits_for_words("thirty, fifty, sixty, seventy, eighty") == "30, 50, 60, 70, 80"
    assert digits_for_words("No one came; one of them left.") == "No one came; one of them left."


def test_a_checked_number_word_reaches_the_reader_as_digits(lookups: Lookups) -> None:
    client = FixtureClient(
        {
            "who never showed up?": Fixture(
                calls=[{"name": "roster", "input": {"window": "7d"}}],
                answer="Three people were invited but never logged in.",
            )
        }
    )

    result = answer_question("Who never showed up?", client, lookups)

    assert result.answer == "3 people were invited but never logged in."
    assert not result.refused


def test_a_span_of_days_is_a_date_only_when_both_ends_are_in_the_results() -> None:
    # Refused on the sixth live run: "(17 to 23 October 2026)" left a bare 17.
    # A hand-made result, so the only numbers in it are the ones written here.
    result = (
        '{"window_first_day": "2026-10-24", "window_last_day": "2026-10-30", '
        '"previous_first_day": "2026-10-17", "previous_last_day": "2026-10-23", '
        '"rows": [{"headline_count": 10, "headline_count_previous": 51}]}'
    )
    said = "10 invoices in the last 7 days (24 to 30 October 2026), against 51 in the previous 7 days (17 to 23 October)."

    assert unsupported_numbers(said, [result]) == []
    assert unsupported_numbers("51 before (October 17 to 23, 2026).", [result]) == []
    assert unsupported_numbers("51 before (17\u201323 Oct).", [result]) == []
    # One end that is not a date in the results is a number like any other.
    assert unsupported_numbers("51 before (18 to 23 October).", [result]) == ["18"]
    assert unsupported_numbers("51 before (17 to 22 October).", [result]) == ["17", "22"]
    # And a span is not a way to smuggle a count in front of a real date.
    assert unsupported_numbers("17 errors to 23 October.", [result]) == ["17"]
    assert unsupported_numbers("17 and 23 October.", [result]) == ["17"]


def test_a_span_is_only_ever_a_windows_own_two_ends() -> None:
    # Found in review: any two dates in a result used to make a span, so in a list of
    # people an invented count could sit in front of a real last-seen date and pass.
    people = (
        '{"window_first_day": "2026-10-01", "window_last_day": "2026-10-30", "rows": ['
        '{"name": "A", "logins": 5, "last_seen": "2026-10-28"}, '
        '{"name": "B", "logins": 7, "last_seen": "2026-10-30"}]}'
    )

    assert unsupported_numbers("- A: 28 \u2013 30 October", [people]) == ["28"]
    assert unsupported_numbers("- A: 28 - 30 Oct", [people]) == ["28"]
    assert unsupported_numbers("Logins rose from 28 to 30 October.", [people]) == ["28"]
    # The window's own span is still a date.
    assert (
        unsupported_numbers(
            "In the last 30 days (1 to 30 October 2026), A logged in 5 times.", [people]
        )
        == []
    )


def test_the_prompt_gives_the_model_no_count_of_its_own_to_repeat() -> None:
    # On the sixth live run the model wrote "all eight tools", a number from its
    # instructions and not from a lookup, and the check rightly refused the answer.
    prompt = system_prompt(date(2026, 10, 30)).lower()

    assert "eight" not in prompt
    assert "forty" not in prompt
