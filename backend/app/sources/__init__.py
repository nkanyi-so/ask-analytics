"""Event sources. `build_source` is the only place that knows which one is in use."""

from app.config import DATA_DIR, Settings
from app.sources.base import EventSource
from app.sources.file import FileEventSource
from app.sources.mixpanel import MixpanelConfig, MixpanelEventSource


def mixpanel_config(settings: Settings) -> MixpanelConfig:
    """The Mixpanel settings, or an error naming the ones that are missing."""
    needed = {
        "MIXPANEL_PROJECT_ID": settings.mixpanel_project_id,
        "MIXPANEL_SERVICE_ACCOUNT_USERNAME": settings.mixpanel_service_account_username,
        "MIXPANEL_SERVICE_ACCOUNT_SECRET": settings.mixpanel_service_account_secret,
        "MIXPANEL_AS_OF": settings.mixpanel_as_of,
    }
    missing = [name for name, value in needed.items() if not value]
    if missing or settings.mixpanel_as_of is None:
        raise ValueError(f"The Mixpanel source needs: {', '.join(missing)}.")
    return MixpanelConfig(
        project_id=settings.mixpanel_project_id,
        username=settings.mixpanel_service_account_username,
        secret=settings.mixpanel_service_account_secret,
        as_of=settings.mixpanel_as_of,
        region=settings.mixpanel_region,
    )


def build_source(settings: Settings) -> EventSource:
    match settings.event_source:
        case "file":
            return FileEventSource(DATA_DIR / "events.jsonl")
        case "mixpanel":
            return MixpanelEventSource(mixpanel_config(settings))
