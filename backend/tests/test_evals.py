import json
from collections import Counter
from typing import Any

import pytest

from app.assistant import answer_question
from app.cache import TTLCache
from app.db import Database
from app.llm import FixtureClient, load_fixtures, normalise_question
from app.lookups import Lookups
from evals import build, run
from evals.scoring import passes, says_direction, whole_numbers

QUESTIONS: list[dict[str, Any]] = json.loads((build.EVALS_DIR / "questions.json").read_text())


def test_tracked_eval_files_are_what_the_generator_produces() -> None:
    questions, fixtures = build.build()

    assert (build.EVALS_DIR / "questions.json").read_text() == questions
    assert (build.EVALS_DIR / "fixtures.json").read_text() == fixtures


def test_the_set_has_the_shape_the_spec_asks_for() -> None:
    tiers = Counter(q["tier"] for q in QUESTIONS)

    assert tiers == {"direct": 12, "indirect": 10, "comparison": 8, "refusal": 10}
    assert sum(q["adversarial"] for q in QUESTIONS) == 3
    assert all(q["refuse"] == (q["tier"] == "refusal") for q in QUESTIONS)
    assert len({normalise_question(q["question"]) for q in QUESTIONS}) == 40


def test_every_answerable_question_expects_something_checkable() -> None:
    for question in QUESTIONS:
        if not question["refuse"]:
            expect = question["expect"]
            assert expect["numbers"] or expect["texts"], question["id"]
        if question["tier"] == "comparison":
            assert question["expect"]["direction"] in ("up", "down"), question["id"]


def test_the_suggested_questions_are_in_the_set() -> None:
    asked = {q["question"]: q for q in QUESTIONS}

    assert all(not asked[question]["refuse"] for question in build.SUGGESTED)
    assert asked[build.SUGGESTED_REFUSAL]["refuse"] is True


@pytest.mark.parametrize("question", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_fixture_eval(question: dict[str, Any], database: Database) -> None:
    """Each question, end to end through the real loop and lookups, scored as in a live run."""
    client = FixtureClient(load_fixtures(build.EVALS_DIR / "fixtures.json"))

    result = answer_question(question["question"], client, Lookups(database, TTLCache()))

    assert passes(question, result.answer, result.refused), result.answer
    assert result.refused == question["refuse"]


def test_fixture_run_reports_every_tier_at_full_marks(database: Database) -> None:
    client = FixtureClient(load_fixtures(build.EVALS_DIR / "fixtures.json"))

    outcomes = run.run(client, Lookups(database, TTLCache()), runs=1)
    report = run.table(outcomes, runs=1)

    assert "| direct | 12 | 12 | 100% |" in report
    assert "| indirect | 10 | 10 | 100% |" in report
    assert "| comparison | 8 | 8 | 100% |" in report
    assert "| refusal | 10 | 10 | 100% |" in report
    assert "| all | 40 | 40 | 100% |" in report


# --- the scorer must be able to fail ---------------------------------------------------

NUMBER_Q = {"refuse": False, "expect": {"numbers": [41], "texts": [], "direction": "down"}}
NAME_Q = {"refuse": False, "expect": {"numbers": [], "texts": ["Xena Jarrah"], "direction": None}}
REFUSAL_Q = {"refuse": True, "expect": None}
WEEK_Q = {"refuse": False, "expect": {"numbers": [7], "texts": [], "direction": "up"}}


@pytest.mark.parametrize(
    ("question", "answer", "refused", "expected"),
    [
        (NUMBER_Q, "Invoices are down by 41 this week.", False, True),
        (NUMBER_Q, "Invoices fell by 41.", False, True),
        (NUMBER_Q, "Invoices are down by 42 this week.", False, False),
        (NUMBER_Q, "Invoices are down by 410 this week.", False, False),
        (NUMBER_Q, "Invoices are up by 41 this week.", False, False),
        (NUMBER_Q, "More or less? Invoices went up by 41.", False, False),
        (NUMBER_Q, "You asked whether it went up or down: invoices are down by 41.", False, True),
        (
            NUMBER_Q,
            "More or less than before? Clearly less: this week it is down by 41.",
            False,
            True,
        ),
        (WEEK_Q, "Errors rose in the last 7 days.", False, False),
        (WEEK_Q, "Errors rose by 7 in the last 7 days.", False, True),
        (WEEK_Q, "Errors rose, as of 7 October 2026.", False, False),
        (WEEK_Q, "Errors rose, as of 2026-10-07.", False, False),
        (NUMBER_Q, "I can't answer that.", True, False),
        (NAME_Q, "xena jarrah has gone quiet.", False, True),
        (NAME_Q, "Yara Quill has gone quiet.", False, False),
        (REFUSAL_Q, "I can't answer that.", True, True),
        (REFUSAL_Q, "Revenue was 41.", False, False),
    ],
)
def test_scoring(question: dict[str, Any], answer: str, refused: bool, expected: bool) -> None:
    assert passes(question, answer, refused) is expected


def test_numbers_are_matched_whole_not_as_substrings() -> None:
    assert whole_numbers("1,234 events on 2026-10-30, up 41") == {1234, 2026, 10, 30, 41}
    assert 41 not in whole_numbers("410 and 141")


def test_direction_words() -> None:
    assert says_direction("It rose by 5.", "up")
    assert says_direction("5 fewer than before.", "down")
    assert not says_direction("It is 5.", "up")
    assert not says_direction("It went up, or maybe down, by 5.", "up", near=5)
    assert says_direction(
        "Up or down? Whatever you expected, the answer is: it fell by 5.", "down", near=5
    )


def test_no_expected_number_is_a_window_length() -> None:
    # "the last 7 days" is stripped before scoring, but an expected 7 or 30 would still
    # be the easiest number for an answer to contain by accident.
    for question in QUESTIONS:
        if not question["refuse"]:
            assert not {7, 30} & set(question["expect"]["numbers"]), question["id"]


def test_one_outage_does_not_abort_a_run(database: Database) -> None:
    from app.llm import ModelUnavailable

    class DownClient:
        model = "claude-haiku-5-5"

        def cannot_answer(self, question: str) -> str | None:
            return None

        def complete(self, system: str, tools: list[Any], messages: list[Any]) -> Any:
            raise ModelUnavailable("APITimeoutError")

    outcomes = run.run(DownClient(), Lookups(database, TTLCache()), runs=2)

    assert len(outcomes) == 40
    assert not any(any(o.passed) for o in outcomes)
    assert outcomes[0].answers == ("<model unavailable: APITimeoutError>",) * 2


def test_live_table_counts_a_question_only_if_every_run_passed() -> None:
    question = {"id": "d01", "tier": "direct", "refuse": False, "question": "q", "expect": {}}
    flaky = run.Outcome(question, ("a", "b", "c"), (True, False, True), 0.0)

    assert "| direct | 1 | 0 | 0% | 2 of 3 |" in run.table([flaky], runs=3)
    assert "run 2 FAILED: b" in run.failures([flaky])


def test_a_live_run_without_a_key_stops_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.config import Settings

    def no_client(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a model client was built without a key")

    monkeypatch.setattr(run, "get_settings", lambda: Settings(_env_file=None, anthropic_api_key=""))
    monkeypatch.setattr(run, "AnthropicClient", no_client)
    monkeypatch.setattr("sys.argv", ["evals.run", "--live"])

    assert run.main() == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err


def test_fixture_mode_ignores_a_local_env_that_points_at_mixpanel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `make check` must never send a request to Mixpanel, whatever .env says.
    monkeypatch.setenv("EVENT_SOURCE", "mixpanel")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")

    settings = run.fixture_settings()

    assert settings.event_source == "file"
    assert settings.demo_mode
