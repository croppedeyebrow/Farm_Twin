"""
규칙 schema · version (4단계 Day 12).

=============================================================================
역할
-----------------------------------------------------------------------------
DB `control_rules` 행의 도메인 표현.
규칙 변경은 version 을 증가시켜 lineage 를 남긴다
(데이터엔지니어링 설계: rule_set_version).

RULE_SCHEMA_VERSION vs RuleDefinition.version
---------------------------------------------
- RULE_SCHEMA_VERSION ("rules.v1"):
  엔진이 이해하는 **필드 계약** (어떤 키가 무슨 의미인지).
  스키마가 바뀌면 마이그레이션·호환 레이어가 필요하다.
- RuleDefinition.version:
  같은 name 규칙의 **내용 개정** 번호.
  예) cool_on_high_temp v1 → v2 (임계값만 변경).

히스테리시스 (start/stop)
-------------------------
comparator 를 start_threshold 에 적용해 START,
반대 방향으로 stop_threshold 를 보면 STOP.
예) GT + start=28, stop=25
  → 값>28 시작, 값<=25 정지, 그 사이는 상태 유지(채터링 완화 1차).

priority
--------
숫자가 **작을수록** 우선. 동일 actuator 충돌 시 Day 12 evaluate 가
우선순위 높은(숫자 작은) 규칙만 남긴다.

min_on / cooldown (Day 14 gates)
--------------------------------
스키마에 저장만 하고, 실제 차단은 gates.apply_timing_gates 가 수행한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ActuatorMode, ActuatorType, RuleComparator, SensorType

# 엔진이 해석하는 규칙 필드 계약 버전 (lineage 기록용)
RULE_SCHEMA_VERSION = "rules.v1"


@dataclass(frozen=True)
class RuleDefinition:
    """자동 제어 규칙 한 건 (불변 스냅샷)."""

    name: str
    version: int
    enabled: bool
    priority: int
    metric: SensorType
    comparator: RuleComparator
    start_threshold: float
    stop_threshold: float
    target_actuator_type: ActuatorType
    target_mode: ActuatorMode = ActuatorMode.ON
    target_output_ratio: float = 1.0
    # STOP 후 다시 START 하기 전 대기 (초, 가상 시계)
    cooldown_seconds: float = 0.0
    # START 후 STOP 하기 전 최소 가동 (초, 가상 시계)
    min_on_seconds: float = 0.0
    description: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be >= 1")
        if self.priority < 0:
            raise ValueError("priority must be >= 0")
        if not 0.0 <= self.target_output_ratio <= 1.0:
            raise ValueError("target_output_ratio must be in [0, 1]")
        if self.cooldown_seconds < 0 or self.min_on_seconds < 0:
            raise ValueError("cooldown/min_on must be >= 0")


@dataclass(frozen=True)
class RuleSet:
    """
    한 재배실(또는 실험)에 적용할 규칙 묶음.

    schema_version 으로 엔진 계약, rules[].version 으로 개별 개정을 표기한다.
    """

    rules: tuple[RuleDefinition, ...]
    schema_version: str = RULE_SCHEMA_VERSION

    def enabled_by_priority(self) -> list[RuleDefinition]:
        """enabled 만, priority 오름차순 · name 안정 정렬."""
        enabled = [rule for rule in self.rules if rule.enabled]
        return sorted(enabled, key=lambda rule: (rule.priority, rule.name))
