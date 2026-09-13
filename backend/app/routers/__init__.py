"""API 라우터 패키지 (2단계 Day 7+).

main.py 에서 `include_router` 할 라우터만 여기서 re-export 한다.
경로 예: Nginx `/api/farms` → (strip) → `/farms`
"""

from app.routers.farms import router as farms_router

__all__ = ["farms_router"]
