import pytest

from app.config import DEFAULT_MODEL, REPO_ROOT, Settings


def test_env_example_names_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "not-a-real-token")
    monkeypatch.setenv("ASK_RATE_PER_MINUTE", "9")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://example.test")

    settings = Settings(_env_file=None)

    assert settings.admin_token == "not-a-real-token"
    assert settings.ask_rate_per_minute == 9
    assert settings.frontend_origin == "http://example.test"


def test_empty_model_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example ships `ANTHROPIC_MODEL=` with nothing after it.
    monkeypatch.setenv("ANTHROPIC_MODEL", "")

    assert Settings(_env_file=None).anthropic_model == DEFAULT_MODEL


def test_demo_mode_follows_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert Settings(_env_file=None).demo_mode is True

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    assert Settings(_env_file=None).demo_mode is False


def test_every_backend_name_in_env_example_is_a_setting() -> None:
    # BACKEND_URL is read by the frontend only.
    frontend_only = {"BACKEND_URL"}
    lines = (REPO_ROOT / ".env.example").read_text().splitlines()
    names = {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}

    assert names - frontend_only == {field.upper() for field in Settings.model_fields}
