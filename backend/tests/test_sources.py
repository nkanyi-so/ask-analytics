from datetime import date, datetime
from pathlib import Path

import pytest

from app.config import DATA_DIR, Settings
from app.sources import build_source
from app.sources.base import EventSource, Workspace
from app.sources.file import FileEventSource


def load_through_the_interface(source: EventSource) -> Workspace:
    return source.load()


def test_file_source_loads_the_whole_workspace() -> None:
    workspace = load_through_the_interface(FileEventSource(DATA_DIR / "events.jsonl"))

    assert workspace.as_of == date(2026, 10, 30)
    assert len(workspace.clients) == 6
    assert len(workspace.tools) == 8
    assert len(workspace.users) == 40
    assert len(workspace.events) > 5000
    first = workspace.events[0]
    assert isinstance(first.ts, datetime)
    assert first.name == "login"
    assert first.tool_id is None
    assert first.error_source is None


def test_people_without_events_are_still_in_the_roster() -> None:
    workspace = FileEventSource(DATA_DIR / "events.jsonl").load()
    with_events = {event.user_id for event in workspace.events}

    assert len({user.id for user in workspace.users} - with_events) == 3


def test_file_without_a_meta_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"kind":"client","id":"c01","name":"Somewhere"}\n')

    with pytest.raises(ValueError, match="meta"):
        FileEventSource(path).load()


def test_unknown_record_kind_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"kind":"meta","as_of":"2026-10-30","seed":1,"days":60}\n{"kind":"mystery"}\n')

    with pytest.raises(ValueError, match="mystery"):
        FileEventSource(path).load()


def test_settings_choose_the_source() -> None:
    assert isinstance(build_source(Settings(_env_file=None, event_source="file")), FileEventSource)

    with pytest.raises(NotImplementedError, match="Phase 5"):
        build_source(Settings(_env_file=None, event_source="mixpanel"))
