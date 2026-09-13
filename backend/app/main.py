"""FarmTwin API entrypoint."""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.session import engine

app = FastAPI(
    title="FarmTwin API",
    version="0.1.0",
)

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


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "FarmTwin API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
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
    await websocket.accept()
    await websocket.send_json({"status": "ok"})
    await websocket.close()
