from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_ok() -> None:
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock()
    mock_connection.__aenter__.return_value = mock_connection
    mock_connection.__aexit__.return_value = None

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connection

    with patch("app.main.engine", mock_engine):
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_ready_unavailable() -> None:
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("db down")

    with patch("app.main.engine", mock_engine):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


def test_ws_health() -> None:
    with client.websocket_connect("/ws/health") as websocket:
        assert websocket.receive_json() == {"status": "ok"}
