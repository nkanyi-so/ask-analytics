from fastapi.testclient import TestClient

from app.main import create_app


def test_health_needs_no_token() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
