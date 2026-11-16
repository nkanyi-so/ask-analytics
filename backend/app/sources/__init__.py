"""Event sources. `build_source` is the only place that knows which one is in use."""

from app.config import DATA_DIR, Settings
from app.sources.base import EventSource
from app.sources.file import FileEventSource


def build_source(settings: Settings) -> EventSource:
    match settings.event_source:
        case "file":
            return FileEventSource(DATA_DIR / "events.jsonl")
        case "mixpanel":
            raise NotImplementedError("The Mixpanel source arrives in Phase 5.")
