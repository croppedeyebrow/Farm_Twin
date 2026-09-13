# FarmTwin API 이미지 (1단계 Day 3).
# Python 3.12 + uv 공식 이미지를 사용해 로컬과 동일한 패키지 매니저를 유지한다.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# UV_COMPILE_BYTECODE: import 속도 개선
# UV_LINK_MODE=copy: 볼륨/레이어에서 hardlink 이슈 회피
# PYTHONUNBUFFERED: 컨테이너 로그를 즉시 flush
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 의존성 레이어를 코드와 분리해 캐시 효율을 높인다.
COPY pyproject.toml uv.lock ./
# 프로덕션 이미지에는 ruff/pytest 등 dev 그룹을 넣지 않는다.
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh
# Windows 체크아웃의 CRLF 를 제거해 shebang 실행 오류를 막는다.
RUN sed -i 's/\r$//' ./docker-entrypoint.sh && chmod +x ./docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
