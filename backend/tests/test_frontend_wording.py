"""Two things the Ask panel can only tell from the backend's wording.

The API gives the panel no field for these, and the design pass was not allowed to add
one. So the panel reads the words, and these tests fail if the words change without it.
"""

import inspect

from app import main
from app.config import REPO_ROOT
from app.llm import NOT_RECORDED
from evals import build

PANEL = (REPO_ROOT / "frontend" / "src" / "components" / "AskPanel.tsx").read_text()


def test_the_two_limits_can_be_told_apart_by_the_word_the_panel_looks_for() -> None:
    source = inspect.getsource(main)
    rate = "Too many questions. Wait a minute and try again."
    budget = "The demo has used its budget for today. Ask again tomorrow."

    assert rate in source
    assert budget in source
    assert "budget" in budget.lower()
    assert "budget" not in rate.lower()
    assert 'message.toLowerCase().includes("budget")' in PANEL


def test_a_question_with_no_recording_starts_with_the_words_the_panel_looks_for() -> None:
    assert NOT_RECORDED.startswith("Demo mode")
    assert 'body.answer.startsWith("Demo mode")' in PANEL


def test_the_question_offered_as_one_to_refuse_is_one_the_eval_set_expects_refused() -> None:
    suggested = (REPO_ROOT / "frontend" / "src" / "lib" / "suggested.ts").read_text()

    assert f'export const REFUSED_QUESTION = "{build.SUGGESTED_REFUSAL}";' in suggested
