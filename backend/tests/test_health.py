from fastapi.testclient import TestClient

from app.main import create_app


def test_health_needs_no_token() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_loads_the_seeded_data() -> None:
    app = create_app()

    with TestClient(app):
        assert app.state.database.as_of.isoformat() == "2026-10-30"
