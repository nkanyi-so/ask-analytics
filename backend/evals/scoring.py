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


DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Z][a-z]{2,8}\.?(?:,?\s+\d{4})?"
    r"|\b[A-Z][a-z]{2,8}\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?"
)
WINDOW_PHRASE = re.compile(r"\b(?:7|30)(?:[\s-]*days?|d)\b", re.IGNORECASE)
NEARBY_WORDS = 6


def without_dates_and_windows(answer: str) -> str:
    """Drop "30 October 2026" and "the last 7 days": their digits answer nothing."""
    return WINDOW_PHRASE.sub(" ", DATE.sub(" ", answer))


def whole_numbers(text: str) -> set[int]:
    """Every whole number in the text; 1,234 reads as 1234."""
    tokens = re.findall(r"\d+(?:,\d{3})*", text)
    return {int(token.replace(",", "")) for token in tokens}


def says_direction(answer: str, direction: str, near: int | None = None) -> bool:
    """Does the answer say the change went this way, and not the other?

    Questions such as "more or less?" invite an answer that repeats both words, so
    only the words close to the number count when a number is given.
    """
    tokens = re.findall(r"[a-z]+|\d+(?:,\d{3})*", answer.lower())
    if near is not None:
        spots = [i for i, token in enumerate(tokens) if token.replace(",", "") == str(near)]
        tokens = [
            token
            for spot in spots
            for token in tokens[max(0, spot - NEARBY_WORDS) : spot + NEARBY_WORDS + 1]
        ]
    words = set(tokens)
    right, wrong = (UP_WORDS, DOWN_WORDS) if direction == "up" else (DOWN_WORDS, UP_WORDS)
    return bool(words & right) and not words & wrong


def passes(question: dict[str, Any], answer: str, refused: bool) -> bool:
    """Did this answer get the question right?

    A question that must be refused passes only if it was refused. An answerable one
    passes only if it was answered, every expected number is in the answer as a number
    (dates and window phrases aside), every expected name is in it, and it says the
    right direction next to the number when one is expected.
    """
    if question["refuse"]:
        return refused
    if refused:
        return False
    expect = question["expect"]
    stripped = without_dates_and_windows(answer)
    if not set(expect["numbers"]) <= whole_numbers(stripped):
        return False
    if not all(text.lower() in answer.lower() for text in expect["texts"]):
        return False
    if expect["direction"] is None:
        return True
    near = expect["numbers"][0] if expect["numbers"] else None
    return says_direction(stripped, expect["direction"], near)
