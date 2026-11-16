import json
from typing import Any

import pytest

from app.config import DATA_DIR, Settings
from app.db import Database, load_database
from app.sources.file import FileEventSource

TEST_TOKEN = "test-token-not-a-secret"


@pytest.fixture(scope="session")
def database() -> Database:
    return load_database(FileEventSource(DATA_DIR / "events.jsonl"))


@pytest.fixture(scope="session")
def truth() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((DATA_DIR / "ground_truth.json").read_text())
    return loaded


@pytest.fixture
def settings() -> Settings:
    # No .env and no key: tests never see real secrets and never reach the live model.
    no_key = ""
    return Settings(_env_file=None, admin_token=TEST_TOKEN, anthropic_api_key=no_key)
