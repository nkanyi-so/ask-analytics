from types import SimpleNamespace
from typing import Any

import pytest

from app.llm import (
    PRICES_PER_MILLION_TOKENS,
    AnthropicClient,
    Fixture,
    FixtureClient,
    ModelUnavailable,
    cost_usd,
    normalise_question,
    resolve,
)


def test_cost_uses_the_price_table() -> None:
    assert cost_usd("claude-haiku-5-5", input_tokens=1_000_000, output_tokens=1_000_000) == (
        pytest.approx(0.60)
    )
    assert cost_usd("claude-opus-5-5", input_tokens=2_000, output_tokens=500) == (
        pytest.approx(2_000 * 4 / 1e6 + 500 * 20 / 1e6)
    )
    assert set(PRICES_PER_MILLION_TOKENS) == {"claude-haiku-5-5", "claude-opus-5-5"}


def test_an_unpriced_model_is_refused_at_construction() -> None:
    # A budget cap over a model with no price is no cap at all.
    with pytest.raises(ValueError, match="no price"):
        AnthropicClient(api_key="not-a-real-key", model="claude-made-up-9")


class StubMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def sdk_response(content: list[Any], stop_reason: str = "end_turn") -> Any:
    usage = SimpleNamespace(input_tokens=1200, output_tokens=80)
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


def test_anthropic_client_turns_an_sdk_reply_into_a_model_reply() -> None:
    content = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="Let me look. "),
        SimpleNamespace(type="tool_use", id="call_1", name="roster", input={"window": "7d"}),
    ]
    stub = StubMessages(sdk_response(content, stop_reason="tool_use"))
    client = AnthropicClient(api_key="not-a-real-key", model="claude-haiku-5-5", messages=stub)

    reply = client.complete("system text", [{"name": "roster"}], [{"role": "user", "content": "q"}])

    assert reply.text == "Let me look."
    assert [(c.id, c.name, c.input) for c in reply.tool_calls] == [
        ("call_1", "roster", {"window": "7d"})
    ]
    assert reply.stop_reason == "tool_use"
    assert (reply.input_tokens, reply.output_tokens) == (1200, 80)
    # The whole content goes back unchanged on the next turn, thinking blocks included.
    assert reply.content is content
    request = stub.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["system"] == "system text"
    assert "temperature" not in request
    assert "tool_choice" not in request


def test_sdk_errors_become_model_unavailable() -> None:
    import anthropic

    error = anthropic.APIConnectionError(request=SimpleNamespace())  # type: ignore[arg-type]
    client = AnthropicClient(
        api_key="not-a-real-key", model="claude-haiku-5-5", messages=StubMessages(error=error)
    )

    with pytest.raises(ModelUnavailable):
        client.complete("s", [], [{"role": "user", "content": "q"}])


def test_question_matching_ignores_case_and_spacing() -> None:
    assert normalise_question("  How MANY   invoices?\n") == "how many invoices?"


ROWS = {
    "rows": [
        {"tool_id": "a", "tool_name": "Alpha", "count": 4, "change": -3},
        {"tool_id": "b", "tool_name": "Beta", "count": 0, "change": 2},
        {"tool_id": "c", "tool_name": "Gamma", "count": 9, "change": 0},
    ],
    "total": 13,
    "people": [{"name": "Ada"}, {"name": "Bram"}],
}


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ({"call": 0, "field": "total"}, "13"),
        ({"call": 0, "list": "rows", "where": {"tool_id": "a"}, "field": "count"}, "4"),
        ({"call": 0, "list": "rows", "where": {"count": 0}, "join": "tool_name"}, "Beta"),
        ({"call": 0, "list": "people", "join": "name"}, "Ada, Bram"),
        ({"call": 0, "list": "rows", "top": "count", "field": "tool_name"}, "Gamma"),
        (
            {"call": 0, "list": "rows", "where": {"tool_id": "a"}, "field": "change", "as": "size"},
            "3",
        ),
        (
            {
                "call": 0,
                "list": "rows",
                "where": {"tool_id": "a"},
                "field": "change",
                "as": "direction",
            },
            "down",
        ),
        (
            {
                "call": 0,
                "list": "rows",
                "where": {"tool_id": "b"},
                "field": "change",
                "as": "direction",
            },
            "up",
        ),
        (
            {
                "call": 0,
                "list": "rows",
                "where": {"tool_id": "c"},
                "field": "change",
                "as": "direction",
            },
            "unchanged",
        ),
    ],
)
def test_resolve_reads_a_value_out_of_tool_results(spec: dict[str, Any], expected: str) -> None:
    assert resolve(spec, [ROWS]) == expected


def test_fixture_client_calls_the_tools_then_words_the_answer_from_their_results() -> None:
    fixture = Fixture(
        calls=[{"name": "usage_by_tool", "input": {"window": "7d", "with_previous": False}}],
        answer="Alpha made {0}.",
        values=[{"call": 0, "list": "rows", "where": {"tool_id": "a"}, "field": "count"}],
    )
    client = FixtureClient({"how many did alpha make?": fixture})
    question = {"role": "user", "content": "How many did Alpha make?"}

    first = client.complete("s", [], [question])
    assert first.stop_reason == "tool_use"
    assert [c.name for c in first.tool_calls] == ["usage_by_tool"]

    import json

    results = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": first.tool_calls[0].id,
                "content": json.dumps(ROWS),
            }
        ],
    }
    second = client.complete(
        "s", [], [question, {"role": "assistant", "content": first.content}, results]
    )
    assert second.stop_reason == "end_turn"
    assert second.text == "Alpha made 4."
    assert second.tool_calls == ()


def test_fixture_client_knows_which_questions_it_has() -> None:
    client = FixtureClient({"known question?": Fixture(refuse=True)})

    assert client.cannot_answer("Known   QUESTION?") is None
    assert "live model is not connected" in (client.cannot_answer("Something else?") or "")


def test_fixture_refusal_is_the_refuse_word() -> None:
    client = FixtureClient({"known question?": Fixture(refuse=True)})

    reply = client.complete("s", [], [{"role": "user", "content": "Known question?"}])

    assert (reply.text, reply.tool_calls) == ("REFUSE", ())
