"""
가상 센서 고장 적용 (6단계 Day 22).

=============================================================================
원칙
-----------------------------------------------------------------------------
고장은 **측정 생성 경로**에서만 적용한다.

  참값(FarmState)      : 고장과 무관하게 환경 모델이 계속 갱신
  측정(SensorSample)   : offset+noise 뒤 raw 에 고장을 덧씌움
  이력(fault_injections): 시작·해제 시각만 남김 (reading 을 사후 수정하지 않음)

품질 판정은 고장 여부를 모른 채 Day 21 검사로 이상을 잡아야 한다.
그래서 샘플에 "고장 주입됨" 표시를 붙이지 않는다.

=============================================================================
유형별 동작과 기대 검출
-----------------------------------------------------------------------------
| 유형    | 측정 변화                              | 기대 품질                      |
|---------|----------------------------------------|--------------------------------|
| spike   | 기대 주기 홀수 번째마다 raw + magnitude | suspect (rate_of_change)       |
| stuck   | raw = stuck_value 고정                  | bad (flatline_detected)        |
| dropout | 샘플을 보내지 않음 (sequence 는 진행)   | 조회 시 stale → 복구 시 missing |

spike 를 매 샘플에 더하면 단순 offset 이 되어 변화율 검사에 걸리지 않는다.
주입 시각 기준 기대 주기 번호로 튐/복귀를 번갈아 결정적으로 만든다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import FaultType, SensorType

# spike 기본 크기 — Day 21 변화율 허용치(deadband + per_second·60s)를 넘도록 잡는다.
DEFAULT_SPIKE_MAGNITUDE: dict[SensorType, float] = {
    SensorType.TEMPERATURE: 8.0,
    SensorType.HUMIDITY: 25.0,
    SensorType.CO2: 800.0,
    SensorType.SUBSTRATE_MOISTURE: 30.0,
    SensorType.PPFD: 3000.0,
}

SPIKE_PERIOD_S = 60.0


@dataclass(frozen=True)
class ActiveFault:
    """step 이 측정에 적용할 진행 중 고장 하나."""

    sensor_type: SensorType
    fault_type: FaultType
    start_simulation_time: float
    magnitude: float | None = None
    stuck_value: float | None = None


def spike_magnitude(fault: ActiveFault) -> float:
    if fault.magnitude is not None:
        return fault.magnitude
    return DEFAULT_SPIKE_MAGNITUDE.get(fault.sensor_type, 0.0)


def spike_active_at(fault: ActiveFault, simulation_time: float) -> bool:
    """주입 뒤 기대 주기 번호가 홀수면 튄다 — 첫 샘플부터 바로 보인다."""
    index = round((simulation_time - fault.start_simulation_time) / SPIKE_PERIOD_S)
    return index % 2 == 1


def apply_fault(
    raw_value: float,
    fault: ActiveFault | None,
    *,
    simulation_time: float,
) -> float | None:
    """
    고장 적용 후 raw 값. None 이면 이번 샘플은 전송되지 않는다(dropout).

    주입 시각 이전 샘플에는 적용하지 않는다.
    """
    if fault is None or simulation_time < fault.start_simulation_time:
        return raw_value
    if fault.fault_type is FaultType.DROPOUT:
        return None
    if fault.fault_type is FaultType.STUCK:
        return fault.stuck_value if fault.stuck_value is not None else raw_value
    if spike_active_at(fault, simulation_time):
        return raw_value + spike_magnitude(fault)
    return raw_value
