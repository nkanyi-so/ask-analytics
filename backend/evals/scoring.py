"""Scoring for the eval set: exact match on the number, no AI judge."""

import re
from typing import Any

UP_WORDS = {"up", "increase", "increased", "rose", "risen", "more", "higher", "grew", "gained"}
DOWN_WORDS = {
    "down",
    "decrease",
    "decreased",
    "fell",
    "fallen",
    "fewer",
    "less",
    "lower",
    "dropped",
    "declined",
}


def whole_numbers(text: str) -> set[int]:
    """Every whole number in the text; 1,234 reads as 1234."""
    tokens = re.findall(r"\d+(?:,\d{3})*", text)
    return {int(token.replace(",", "")) for token in tokens}


def says_direction(answer: str, direction: str) -> bool:
    words = set(re.findall(r"[a-z]+", answer.lower()))
    return bool(words & (UP_WORDS if direction == "up" else DOWN_WORDS))


def passes(question: dict[str, Any], answer: str, refused: bool) -> bool:
    """Did this answer get the question right?

    A question that must be refused passes only if it was refused. An answerable one
    passes only if it was answered, every expected number is in the answer as a number,
    every expected name is in it, and it says the right direction when one is expected.
    """
    if question["refuse"]:
        return refused
    if refused:
        return False
    expect = question["expect"]
    return (
        set(expect["numbers"]) <= whole_numbers(answer)
        and all(text.lower() in answer.lower() for text in expect["texts"])
        and (expect["direction"] is None or says_direction(answer, expect["direction"]))
    )
