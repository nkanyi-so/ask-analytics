"""The registry is typed: a tool without a headline event must fail the type check.

These tests run mypy on altered copies of `app/registry.py`, so the proof is the type
checker's own verdict, not a runtime assertion.
"""

import subprocess
import sys
from pathlib import Path

from app import registry
from app.config import DATA_DIR
from app.sources.file import FileEventSource

REGISTRY_SOURCE = Path(registry.__file__).read_text()


def run_mypy(source: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "registry_copy.py"
    path.write_text(source)
    return subprocess.run(  # noqa: S603 - fixed arguments, our own interpreter
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_unaltered_registry_type_checks(tmp_path: Path) -> None:
    # The control: failures below come from the alteration, not from the copy.
    result = run_mypy(REGISTRY_SOURCE, tmp_path)

    assert result.returncode == 0, result.stdout


def test_a_ninth_tool_without_a_headline_event_fails_mypy(tmp_path: Path) -> None:
    marker = '    "report_summariser",\n]'
    assert marker in REGISTRY_SOURCE
    altered = REGISTRY_SOURCE.replace(marker, '    "report_summariser",\n    "ninth_tool",\n]')

    result = run_mypy(altered, tmp_path)

    assert result.returncode != 0
    assert "ninth_tool" in result.stdout
    assert "assert_never" in result.stdout


def test_a_catalog_entry_without_a_headline_event_fails_mypy(tmp_path: Path) -> None:
    complete = 'return CatalogEntry(tool, "Email drafter", "email_sent")'
    assert complete in REGISTRY_SOURCE
    altered = REGISTRY_SOURCE.replace(complete, 'return CatalogEntry(tool, "Email drafter")')

    result = run_mypy(altered, tmp_path)

    assert result.returncode != 0
    assert "headline_event" in result.stdout


def test_a_made_up_headline_event_fails_mypy(tmp_path: Path) -> None:
    complete = 'return CatalogEntry(tool, "Email drafter", "email_sent")'
    altered = REGISTRY_SOURCE.replace(
        complete, 'return CatalogEntry(tool, "Email drafter", "email_opened")'
    )

    result = run_mypy(altered, tmp_path)

    assert result.returncode != 0


def test_catalog_covers_eight_tools_with_distinct_headline_events() -> None:
    assert len(registry.CATALOG) == len(registry.TOOL_IDS) == 8
    assert len({entry.headline_event for entry in registry.CATALOG}) == 8


def test_catalog_matches_the_tools_in_the_data() -> None:
    workspace = FileEventSource(DATA_DIR / "events.jsonl").load()
    in_data = {(tool.id, tool.name, tool.headline_event) for tool in workspace.tools}

    assert in_data == {(e.id, e.name, e.headline_event) for e in registry.CATALOG}
