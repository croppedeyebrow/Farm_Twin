"""
WebSocket ConnectionManager (5단계 Day 16).

=============================================================================
역할
-----------------------------------------------------------------------------
프로세스 메모리에
  farm_id → {WebSocket, ...}
  farm_id → last_sequence
를 두고, 발행자가 farm 구독자에게 JSON 을 fan-out 한다.

MVP 는 단일 API 프로세스 전제다.
멀티 워커/멀티 인스턴스 가 되면 Redis pub/sub 등으로 교체할 지점이다
(인터페이스: connect / disconnect / next_sequence / broadcast).

=============================================================================
sequence 발급 규칙
-----------------------------------------------------------------------------
- last_sequence == 0  → 아직 본 이벤트 없음
- next_sequence()     → 1, 2, 3, ... (단조 증가)
- connection.ready 는 next_sequence 를 호출하지 않는다
  (연결만으로 번호가 뛰면 다른 구독자의 "누락" 오탐)

실패 정책
---------
한 소켓 send 실패 / CONNECTED 아님
  → 그 연결만 disconnect 하고 나머지는 계속.
broadcast 예외가 HTTP/시뮬 step 을 실패시키면 안 된다
  → publisher 가 try/except 로 감싼다.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    농장 단위 실시간 연결·sequence 저장소 (프로세스 내 메모리).

    스레드/프로세스 간 공유 없음 — uvicorn worker=1 또는 단일 컨테이너 MVP.
    """

    def __init__(self) -> None:
        # farm 구독 소켓. set 이라 동일 WebSocket 중복 등록을 피한다.
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        # 마지막으로 **발급한** sequence (0 이면 아직 없음 → 다음이 1)
        self._last_sequence: dict[uuid.UUID, int] = defaultdict(int)

    def connection_count(self, farm_id: uuid.UUID) -> int:
        """관측/로그용 현재 구독 수."""
        return len(self._connections.get(farm_id, ()))

    def last_sequence(self, farm_id: uuid.UUID) -> int:
        """현재까지 발급된 마지막 sequence (없으면 0)."""
        return self._last_sequence[farm_id]

    def next_sequence(self, farm_id: uuid.UUID) -> int:
        """
        단조 증가 sequence 발급.

        publish_event 경로에서만 호출한다.
        connection.ready 는 last_sequence 만 읽는다.
        """
        self._last_sequence[farm_id] += 1
        return self._last_sequence[farm_id]

    async def connect(self, farm_id: uuid.UUID, websocket: WebSocket) -> None:
        """
        accept(필요 시) 후 구독 등록.

        라우트가 이미 accept 했다면 CONNECTING 이 아니므로 accept 를 건너뛴다.
        """
        if websocket.client_state is WebSocketState.CONNECTING:
            await websocket.accept()
        self._connections[farm_id].add(websocket)
        logger.info(
            "ws connected farm_id=%s connections=%s",
            farm_id,
            self.connection_count(farm_id),
        )

    def disconnect(self, farm_id: uuid.UUID, websocket: WebSocket) -> None:
        """구독 해제. 빈 farm 키는 dict 에서 제거해 메모리 누수를 막는다."""
        sockets = self._connections.get(farm_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[farm_id]
        logger.info(
            "ws disconnected farm_id=%s connections=%s",
            farm_id,
            self.connection_count(farm_id),
        )

    async def broadcast(self, farm_id: uuid.UUID, message: dict) -> int:
        """
        farm 구독자에게 message 전송.

        순회 중 set 이 변할 수 있어 list 로 스냅샷한다.
        dead 소켓은 루프 후 disconnect.

        Returns
        -------
        성공한 전송 수 (구독자 0명이면 0)
        """
        sockets = list(self._connections.get(farm_id, ()))
        if not sockets:
            return 0

        sent = 0
        dead: list[WebSocket] = []
        for websocket in sockets:
            try:
                if websocket.client_state is not WebSocketState.CONNECTED:
                    dead.append(websocket)
                    continue
                await websocket.send_json(message)
                sent += 1
            except Exception:
                logger.exception(
                    "ws send failed farm_id=%s; dropping connection",
                    farm_id,
                )
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(farm_id, websocket)
        return sent


# 프로세스 전역 싱글톤 (FastAPI 앱과 동일 수명)
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """앱·서비스·라우트가 공유하는 ConnectionManager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


def reset_connection_manager() -> ConnectionManager:
    """
    테스트용: 연결·sequence 를 깨끗이 비운다.

    프로덕션 경로에서는 호출하지 않는다.
    """
    global _manager
    _manager = ConnectionManager()
    return _manager
