"""
애플리케이션 설정 (1단계 Day 2).

환경변수 / `.env` 에서 값을 읽고, 모듈 import 시점에 한 번 캐시한다.
필수 값인 DATABASE_URL 이 없으면 기동 시 ValidationError 로 즉시 실패한다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    런타임 설정.

    database_url 예시
    - Compose 내부: postgresql+asyncpg://farmtwin:farmtwin@db:5432/farmtwin
    - 호스트 개발 : postgresql+asyncpg://farmtwin:farmtwin@127.0.0.1:15432/farmtwin
      (compose.yaml 이 DB를 15432로 publish)
    """

    database_url: str

    model_config = SettingsConfigDict(
        # backend/ 작업 디렉터리 기준 `.env` 를 읽는다.
        env_file=".env",
        env_file_encoding="utf-8",
        # 알 수 없는 환경변수가 있어도 무시 (Compose에 다른 키가 섞여도 안전).
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 프로세스당 1회만 생성."""
    return Settings()


# 기존 코드 호환을 위한 모듈 수준 싱글톤.
settings = get_settings()
