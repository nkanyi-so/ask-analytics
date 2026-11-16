"""Shape checks on the ground-truth file. Its numbers are checked in Phase 2, where the
SQL lookups must reproduce every one of them."""

import json
from typing import Any

import pytest

from app.config import DATA_DIR

LOOKUPS = {"usage_by_tool", "activity_by_person", "activity_by_client", "errors_seen", "roster"}
WINDOWS = {"today", "7d", "30d"}


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((DATA_DIR / "ground_truth.json").read_text())
    return loaded


def test_every_lookup_has_every_window(truth: dict[str, Any]) -> None:
    assert set(truth["lookups"]) == LOOKUPS
    for by_window in truth["lookups"].values():
        assert set(by_window) == WINDOWS


def test_rows_are_complete_even_at_zero(truth: dict[str, Any]) -> None:
    for window in WINDOWS:
        assert len(truth["lookups"]["usage_by_tool"][window]) == 8
        assert len(truth["lookups"]["activity_by_person"][window]) == 40
        assert len(truth["lookups"]["activity_by_client"][window]) == 6


def test_change_is_current_minus_previous(truth: dict[str, Any]) -> None:
    for row in truth["lookups"]["usage_by_tool"]["7d"]:
        assert (
            row["headline_count_change"] == row["headline_count"] - row["headline_count_previous"]
        )


def test_roster_counts_match_its_lists_and_add_up(truth: dict[str, Any]) -> None:
    for window in WINDOWS:
        roster = truth["lookups"]["roster"][window]
        assert roster["active_count"] == len(roster["active"])
        assert roster["went_quiet_count"] == len(roster["went_quiet"])
        assert roster["never_showed_up_count"] == len(roster["never_showed_up"]) == 3
        # Everyone invited is in exactly one group.
        total = (
            roster["active_count"] + roster["went_quiet_count"] + roster["never_showed_up_count"]
        )
        assert total == roster["invited_count"] == 40


def test_patterns_show_up_in_the_expected_answers(truth: dict[str, Any]) -> None:
    patterns = truth["patterns"]
    month = truth["lookups"]

    unused = [r for r in month["usage_by_tool"]["30d"] if r["headline_count"] == 0]
    assert [r["tool_id"] for r in unused] == [patterns["unused_tool"]]

    assert [p["user_id"] for p in month["roster"]["30d"]["went_quiet"]] == [patterns["quiet_user"]]

    top_error = month["errors_seen"]["7d"][0]
    assert (top_error["tool_id"], top_error["source"]) == (
        patterns["error_tool"],
        patterns["error_source"],
    )
