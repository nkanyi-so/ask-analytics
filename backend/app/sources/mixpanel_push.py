"""Send the seeded workspace to Mixpanel: `make mixpanel-push`.

This writes to an outside service, so it only runs when asked. It reads the same
`data/events.jsonl` the file source reads, and can be repeated without duplicating.
"""

import json
import sys

from app.config import DATA_DIR, get_settings
from app.sources import mixpanel_config
from app.sources.file import FileEventSource
from app.sources.mixpanel import push_workspace


def seed_days() -> int:
    with (DATA_DIR / "events.jsonl").open(encoding="utf-8") as lines:
        meta = json.loads(next(lines))
    return int(meta["days"])


def main() -> int:
    config = mixpanel_config(get_settings())
    workspace = FileEventSource(DATA_DIR / "events.jsonl").load()
    count = push_workspace(workspace, seed_days(), config)
    print(f"Sent {count} records to Mixpanel project {config.project_id} ({config.region}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
