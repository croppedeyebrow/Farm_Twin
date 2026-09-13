"""
FarmTwin API 엔트리포인트 (1단계 Day 2~3, 2단계 Day 7 라우터 연결).

역할
----
- FastAPI 앱 생성과 CORS 설정
- liveness(`/health`) / readiness(`/health/ready`) 분리
- WebSocket 라우팅 검증용 `/ws/health` 골격
- Day 7: farms snapshot/state/sensors/actuators/readings 라우터 등록

설계 배경
--------
인프라 문서의 health 기준을 따른다.
- live  : 프로세스만 살아 있으면 OK (DB 불필요)
- ready : DB 등 필수 의존성이 준비되어야 OK

브라우저 → Nginx(`/api`, `/ws`) → 이 앱 으로 들어온다.
로컬 Vite 개발 시에는 `/api` 가 Vite proxy 로 여기로 전달된다.
"""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.session import engine
from app.routers import farms_router

app = FastAPI(
    title="FarmTwin API",
    version="0.1.0",
)

# 개발용 CORS.
# - 5173: Vite dev server
# - 8080: Compose Nginx 진입점
# 이후 단계에서는 공개 도메인만 최소 허용하도록 좁힌다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Day 7: 농장 CRUD / snapshot (Nginx `/api` strip 후 경로)
app.include_router(farms_router)


@app.get("/")
async def root() -> dict[str, str]:
    """루트 핑. 로드밸런서/수동 확인용 간단한 응답."""
    return {"message": "FarmTwin API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Liveness 프로브.

    컨테이너/프로세스가 살아 있는지만 본다.
    DB 장애가 있어도 200을 반환해야 재시작 루프에 빠지지 않는다.
    Nginx 경유 시: GET /api/health → 여기로 rewrite.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """
    Readiness 프로브.

    PostgreSQL에 `SELECT 1` 이 성공해야 트래픽을 받을 준비가 된 것으로 본다.
    실패 시 503을 내려 Compose/오케스트레이터가 의존 대기를 할 수 있게 한다.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="database unavailable",
        ) from exc

    return {"status": "ok", "database": "connected"}


@app.websocket("/ws/health")
async def ws_health(websocket: WebSocket) -> None:
    """
    WebSocket 라우팅 골격 검증용 엔드포인트 (1단계 Day 3).

    실제 농장 스트림(`/ws/farms/{id}`)은 이후 단계에서 구현한다.
    지금은 Nginx `/ws/` Upgrade 헤더 전달이 동작하는지 확인하는 용도.
    """
    await websocket.accept()
    await websocket.send_json({"status": "ok"})
    await websocket.close()
