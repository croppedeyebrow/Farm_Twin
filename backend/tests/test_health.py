"""
1단계 health / WebSocket 골격 테스트.

실제 PostgreSQL 없이 readiness 성공·실패 경로를 검증하기 위해
engine 을 mock 한다. liveness 와 WS 는 외부 의존성이 없다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Liveness 는 항상 200 + {"status":"ok"}."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_ok() -> None:
    """DB connect/execute 가 성공하면 readiness 200."""
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock()
    mock_connection.__aenter__.return_value = mock_connection
    mock_connection.__aexit__.return_value = None

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connection

    # main 모듈이 import 한 engine 심볼을 패치한다.
    with patch("app.main.engine", mock_engine):
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_ready_unavailable() -> None:
    """DB 연결 실패 시 503 + database unavailable."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("db down")

    with patch("app.main.engine", mock_engine):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


def test_ws_health() -> None:
    """Nginx `/ws/` 검증용 골격이 JSON ok 를 한 번 보내고 닫는지 확인."""
    with client.websocket_connect("/ws/health") as websocket:
        assert websocket.receive_json() == {"status": "ok"}
