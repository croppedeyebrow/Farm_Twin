"""
시간 컬럼 의미 (2단계 Day 5 확정).

DB·API·시뮬레이터·프론트가 같은 정의를 쓰도록 도메인에 고정한다.
자세한 표는 docs/FarmTwin_실내스마트팜/01_종합_기획_문서/시간_컬럼_의미.md
"""

from __future__ import annotations

TIME_COLUMN_SEMANTICS: dict[str, str] = {
    "simulation_time": (
        "시뮬레이션 가상 시계(초). 상태전이·센서 샘플·제어 판정의 기준 시각. "
        "wall-clock 과 독립이며 time_scale 에 따라 빠르게/느리게 진행할 수 있다."
    ),
    "sampled_at": (
        "소스가 값을 샘플링한 시각(timestamptz). "
        "시뮬레이티드는 보통 simulation_time 을 wall-clock 로 투영한 값, "
        "REPLAY/API 는 원본 관측 시각을 보존한다."
    ),
    "ingested_at": (
        "FarmTwin 이 레코드를 수신·적재한 시각(timestamptz). "
        "파이프라인 지연·stale 판정에 사용한다. 원본 샘플 시각을 덮어쓰지 않는다."
    ),
    "created_at": (
        "행이 처음 INSERT 된 시각. 메타데이터 테이블(Site/Farm/…)의 감사 컬럼."
    ),
    "updated_at": (
        "행이 마지막으로 UPDATE 된 시각. FarmState version 갱신 시각과 함께 본다."
    ),
    "started_at": (
        "SimulationRun 이 RUNNING 으로 전환된 wall-clock 시각."
    ),
    "ended_at": (
        "SimulationRun 이 STOPPED/FAILED 로 종료된 wall-clock 시각."
    ),
    "worker_heartbeat_at": (
        "active simulator worker 가 lease 를 갱신한 시각. "
        "만료 시 다른 worker 가 인계할 수 있다."
    ),
}


def describe_time_column(name: str) -> str:
    """시간 컬럼 이름에 대한 설명을 반환한다. 모르면 KeyError."""
    return TIME_COLUMN_SEMANTICS[name]
