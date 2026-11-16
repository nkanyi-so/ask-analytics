"""The model behind one interface: the real Anthropic client and a fixture stand-in.

`make check` and CI only ever use the fixture client, so they never spend credits.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import anthropic

MAX_TOKENS = 4096
TIMEOUT_SECONDS = 30.0  # hard limit per request
MAX_RETRIES = 1  # the SDK retries once, with backoff, on timeouts, 429s and 5xx

# USD per million tokens (input, output). A model missing from this table cannot be
# used: the daily budget would have nothing to count.
PRICES_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    text: str
    tool_calls: tuple[ToolCall, ...]
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    # The reply's content exactly as the model sent it. It goes back unchanged as the
    # assistant turn, because thinking blocks must not be edited or dropped.
    content: list[Any] = field(default_factory=list)


class ModelUnavailable(Exception):
    """The model could not be reached or failed; the caller reports it, never guesses."""


class ModelClient(Protocol):
    model: str

    def complete(
        self, system: str, tools: list[ToolSpec], messages: list[Message]
    ) -> ModelReply: ...

    def cannot_answer(self, question: str) -> str | None:
        """A message if this client has no way to answer the question at all."""
        ...


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in PRICES_PER_MILLION_TOKENS:
        return 0.0  # the fixture client; real models are checked at construction
    input_price, output_price = PRICES_PER_MILLION_TOKENS[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


# --- the real client -----------------------------------------------------------------


class AnthropicClient:
    def __init__(self, api_key: str, model: str, messages: Any = None) -> None:
        if model not in PRICES_PER_MILLION_TOKENS:
            known = ", ".join(sorted(PRICES_PER_MILLION_TOKENS))
            raise ValueError(
                f"Model {model!r} has no price in app/llm.py, so the daily budget could not "
                f"count it. Priced models: {known}."
            )
        self.model = model
        # `messages` lets tests pass a stand-in for the SDK's messages resource.
        self._messages: Any = (
            messages
            or anthropic.Anthropic(
                api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES
            ).messages
        )

    def cannot_answer(self, question: str) -> str | None:
        return None

    def complete(self, system: str, tools: list[ToolSpec], messages: list[Message]) -> ModelReply:
        # No temperature and no forced tool choice: current models reject both.
        try:
            response = self._messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "low"},  # routing and wording, not deep reasoning
            )
        except anthropic.APIError as error:
            raise ModelUnavailable(type(error).__name__) from error
        text = "".join(block.text for block in response.content if block.type == "text")
        calls = tuple(
            ToolCall(id=block.id, name=block.name, input=dict(block.input))
            for block in response.content
            if block.type == "tool_use"
        )
        return ModelReply(
            text=text.strip(),
            tool_calls=calls,
            stop_reason=response.stop_reason or "",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            content=response.content,
        )


# --- the fixture client --------------------------------------------------------------

NOT_RECORDED = (
    "Demo mode: the live model is not connected, and this question has no recorded answer. "
    "Try one of the suggested questions."
)


@dataclass(frozen=True)
class Fixture:
    """The model's part for one question: which lookups to call, then how to word it.

    `answer` is a template; `{0}`, `{1}`... are filled from `values`, each of which
    points at a field in a tool result. So the number still comes from the lookup.
    """

    calls: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    values: list[dict[str, Any]] = field(default_factory=list)
    refuse: bool = False


def normalise_question(question: str) -> str:
    return " ".join(question.lower().split())


def resolve(spec: dict[str, Any], results: list[Any]) -> str:
    """Read one value out of the tool results, as described by `spec`.

    Keys: `call` (which result), `list` (a list inside it), `where` (keep rows with
    these values), `top` (keep the row with the largest value of this field), then
    `field` (one value) or `join` (that field of every row left, comma separated).
    `as: "size"` drops the sign; `as: "direction"` turns the sign into a word.
    """
    target: Any = results[spec["call"]]
    if "list" in spec:
        rows = [
            row
            for row in target[spec["list"]]
            if all(row[key] == value for key, value in spec.get("where", {}).items())
        ]
        if "top" in spec:
            rows = [max(rows, key=lambda row: row[spec["top"]])]
        if "join" in spec:
            return ", ".join(str(row[spec["join"]]) for row in rows)
        (target,) = rows
    value = target[spec["field"]]
    match spec.get("as"):
        case "size":
            return str(abs(value))
        case "direction":
            return "up" if value > 0 else "down" if value < 0 else "unchanged"
        case _:
            return str(value)


def load_fixtures(path: Path) -> dict[str, Fixture]:
    raw: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return {question: Fixture(**fixture) for question, fixture in raw.items()}


class FixtureClient:
    """Plays the model from a script. Deterministic, free, and never on the network."""

    model = "fixture"

    def __init__(self, fixtures: dict[str, Fixture]) -> None:
        self._fixtures = fixtures

    def cannot_answer(self, question: str) -> str | None:
        return None if normalise_question(question) in self._fixtures else NOT_RECORDED

    def complete(self, system: str, tools: list[ToolSpec], messages: list[Message]) -> ModelReply:
        fixture = self._fixtures[normalise_question(messages[0]["content"])]
        if fixture.refuse:
            return ModelReply(text="REFUSE", tool_calls=(), stop_reason="end_turn")
        if fixture.calls and len(messages) == 1:
            calls = tuple(
                ToolCall(id=f"fixture_{index}", name=call["name"], input=call["input"])
                for index, call in enumerate(fixture.calls)
            )
            content = [
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
                for call in calls
            ]
            return ModelReply(text="", tool_calls=calls, stop_reason="tool_use", content=content)
        # A failed call leaves a gap, so `call` indexes still line up with the script.
        blocks = messages[-1]["content"] if len(messages) > 1 else []
        results = [
            None if block.get("is_error") else json.loads(block["content"]) for block in blocks
        ]
        values = [resolve(spec, results) for spec in fixture.values]
        return ModelReply(
            text=fixture.answer.format(*values), tool_calls=(), stop_reason="end_turn"
        )
