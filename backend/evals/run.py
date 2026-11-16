"""Run the eval set.

    python -m evals.run                    fixture mode: free, deterministic, part of `make check`
    python -m evals.run --live             live model (spends API credits; ask first)
    python -m evals.run --live --model claude-opus-5-5

Fixture mode proves the lookups, the assistant loop, the number check and the scorer
end to end. It cannot tell whether a model picks the right lookup; only a live run can.
A live run asks every question three times and writes its table to docs/eval-results.md,
one section per model, so two models can sit side by side.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.assistant import answer_question
from app.cache import TTLCache
from app.config import REPO_ROOT, Settings, get_settings
from app.db import load_database
from app.llm import (
    AnthropicClient,
    FixtureClient,
    ModelClient,
    ModelUnavailable,
    load_fixtures,
)
from app.lookups import Lookups
from app.sources import build_source
from evals.scoring import passes

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_FILE = REPO_ROOT / "docs" / "eval-results.md"
TIERS = ("direct", "indirect", "comparison", "refusal")
LIVE_RUNS = 3


@dataclass(frozen=True)
class Outcome:
    question: dict[str, Any]
    answers: tuple[str, ...]
    passed: tuple[bool, ...]
    cost_usd: float

    @property
    def stable_pass(self) -> bool:
        """Right every time it was asked."""
        return all(self.passed)


def load_questions() -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = json.loads((EVALS_DIR / "questions.json").read_text())
    return questions


def run(client: ModelClient, lookups: Lookups, runs: int) -> list[Outcome]:
    outcomes = []
    for question in load_questions():
        answers, passed, cost = [], [], 0.0
        for _ in range(runs):
            try:
                result = answer_question(question["question"], client, lookups)
            except ModelUnavailable as error:
                # One outage must not throw away a paid run: count it and carry on.
                answers.append(f"<model unavailable: {error}>")
                passed.append(False)
                continue
            answers.append(result.answer)
            passed.append(passes(question, result.answer, result.refused))
            cost += result.cost_usd
        outcomes.append(Outcome(question, tuple(answers), tuple(passed), cost))
    return outcomes


def table(outcomes: list[Outcome], runs: int) -> str:
    """Results per tier. With several runs, a question passes only if every run did."""
    header = "| Tier | Questions | Passed | Rate |"
    rule = "|---|---|---|---|"
    if runs > 1:
        header = f"| Tier | Questions | Passed all {runs} runs | Rate | Single runs passed |"
        rule = "|---|---|---|---|---|"
    lines = [header, rule]
    for tier in (*TIERS, "all"):
        rows = [o for o in outcomes if tier in ("all", o.question["tier"])]
        if not rows:
            continue
        passed = sum(o.stable_pass for o in rows)
        line = f"| {tier} | {len(rows)} | {passed} | {passed / len(rows):.0%} |"
        if runs > 1:
            line += f" {sum(sum(o.passed) for o in rows)} of {len(rows) * runs} |"
        lines.append(line)
    return "\n".join(lines)


def failures(outcomes: list[Outcome]) -> str:
    lines = []
    for outcome in outcomes:
        if outcome.stable_pass:
            continue
        q = outcome.question
        expected = "a refusal" if q["refuse"] else json.dumps(q["expect"])
        lines.append(f"- **{q['id']}** ({q['tier']}): {q['question']}")
        lines.append(f"  - expected: {expected}")
        for index, (answer, ok) in enumerate(zip(outcome.answers, outcome.passed, strict=True), 1):
            lines.append(f"  - run {index} {'passed' if ok else 'FAILED'}: {answer}")
    return "\n".join(lines) or "None."


def write_live_section(model: str, outcomes: list[Outcome], runs: int) -> None:
    """Replace this model's section in docs/eval-results.md, or add it."""
    begin, end = f"<!-- begin:{model} -->", f"<!-- end:{model} -->"
    when = datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")
    cost = sum(o.cost_usd for o in outcomes)
    section = (
        f"{begin}\n### `{model}`\n\nRun on {when}. {len(outcomes)} questions, {runs} runs each. "
        f"Cost: ${cost:.4f}.\n\n{table(outcomes, runs)}\n\n"
        f"Failures (any run):\n\n{failures(outcomes)}\n{end}"
    )
    current = RESULTS_FILE.read_text(encoding="utf-8")
    if begin in current:
        start, stop = current.index(begin), current.index(end) + len(end)
        current = current[:start] + section + current[stop:]
    else:
        current = current.replace("None yet.\n", "").rstrip() + "\n\n" + section + "\n"
    RESULTS_FILE.write_text(current, encoding="utf-8")


def build_lookups(settings: Settings) -> Lookups:
    return Lookups(load_database(build_source(settings)), TTLCache())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="call the live model (spends credits)")
    parser.add_argument("--model", help="model id for a live run (default: ANTHROPIC_MODEL)")
    arguments = parser.parse_args()
    settings = get_settings()
    lookups = build_lookups(settings)

    if not arguments.live:
        client: ModelClient = FixtureClient(load_fixtures(EVALS_DIR / "fixtures.json"))
        outcomes = run(client, lookups, runs=1)
        print("Evals, fixture mode (no model was called):\n")
        print(table(outcomes, runs=1))
        if not all(o.stable_pass for o in outcomes):
            print("\nFailures:\n" + failures(outcomes))
            return 1
        return 0

    if not settings.anthropic_api_key:
        print("evals: ANTHROPIC_API_KEY is not set, so there is no live run.", file=sys.stderr)
        return 2
    model = arguments.model or settings.anthropic_model
    client = AnthropicClient(settings.anthropic_api_key, model)
    outcomes = run(client, lookups, runs=LIVE_RUNS)
    write_live_section(model, outcomes, LIVE_RUNS)
    print(f"Evals, live, {model}:\n")
    print(table(outcomes, LIVE_RUNS))
    print("\nFailures (any run):\n" + failures(outcomes))
    print(f"\nWritten to {RESULTS_FILE.relative_to(REPO_ROOT)}. A failing question is a finding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
