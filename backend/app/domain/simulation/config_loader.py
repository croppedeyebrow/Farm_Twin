"""
환경 모델 계수 설정 파일 로더 (3단계 Day 10).

TOML 파일에서 EnvironmentModelParams 를 읽는다.
표준 라이브러리 tomllib 만 사용 (추가 의존성 없음).

기본 경로
---------
repo 루트 기준 `simulator/config/environment_model.toml`
"""

from __future__ import annotations

import tomllib
from dataclasses import fields
from pathlib import Path

from app.domain.simulation.params import DEFAULT_ENV_PARAMS, EnvironmentModelParams

# repo/backend/app/domain/simulation → repo/simulator/config
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "simulator" / "config" / "environment_model.toml"

_VALID_FIELD_NAMES = {field.name for field in fields(EnvironmentModelParams)}


def load_environment_params(
    path: Path | str | None = None,
) -> EnvironmentModelParams:
    """
    TOML 설정에서 EnvironmentModelParams 를 생성한다.

    - path 가 None 이면 DEFAULT_CONFIG_PATH
    - [environment_model] 섹션만 읽는다 (없으면 루트 키 사용)
    - 알 수 없는 키는 무시
    - 파일이 없으면 DEFAULT_ENV_PARAMS 반환
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        return DEFAULT_ENV_PARAMS

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    section = raw.get("environment_model", raw)
    if not isinstance(section, dict):
        raise TypeError("environment_model section must be a table")

    kwargs = {
        key: value
        for key, value in section.items()
        if key in _VALID_FIELD_NAMES and isinstance(value, (int, float))
    }
    return EnvironmentModelParams(**kwargs)
