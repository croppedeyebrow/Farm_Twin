"""
WebSocket 라우트 (5단계 Day 16).

=============================================================================
엔드포인트
-----------------------------------------------------------------------------
  WS /ws/farms/{farm_id}

브라우저 → (Vite 또는) Nginx `/ws/` Upgrade → FastAPI 이 핸들러.

연결 수명
---------
1) ConnectionManager.connect (accept + 구독 등록)
2) connection.ready 송신 (last_sequence, sequence 미증가)
3) receive 루프로 연결 유지
   - Day 16: 서버→클라 push 가 본업. 클라 텍스트는 keepalive/무시.
   - Day 17+: snapshot 요청·ack 등 클라→서버 메시지 가능
4) disconnect / 예외 시 finally 에서 구독 해제

인증
----
백엔드 설계의 "WebSocket 인증"은 Day 17+ 범위.
지금은 farm_id UUID 구독만 허용 (로컬·시드 농장 전제).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import get_connection_manager
from app.websocket.publisher import send_connection_ready

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/farms/{farm_id}")
async def farm_realtime(websocket: WebSocket, farm_id: uuid.UUID) -> None:
    """
    농장 단위 실시간 스트림.

    같은 farm_id 로 step/start 등이 commit 되면
    publisher 가 이 연결을 포함한 구독자에게 envelope 를 fan-out 한다.
    """
    manager = get_connection_manager()
    await manager.connect(farm_id, websocket)
    # 기준 sequence 를 알려 준 뒤 push 대기
    await send_connection_ready(farm_id, websocket, manager=manager)

    try:
        # receive 가 끝나야(클라 close) finally 로 간다.
        # 서버가 일방 close 하지 않는 한 구독이 유지된다.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("ws client disconnected farm_id=%s", farm_id)
    except Exception:
        logger.exception("ws farm stream error farm_id=%s", farm_id)
    finally:
        manager.disconnect(farm_id, websocket)
