"""
환경 상태·입력 DTO (3단계 Day 8~9).

=============================================================================
계층에서의 위치
-----------------------------------------------------------------------------
이 모듈은 ORM/FastAPI 에 의존하지 않는 **순수 도메인 값**이다.

  WeatherAdapter → OutdoorCondition ─┐
  Actuator(운전) → ActuatorInputs  ─┼→ step_environment → EnvironmentState
  이전 EnvironmentState ────────────┘

DB 의 farm_states 는 EnvironmentState 의 영속 투영이고,
sensor_readings 는 이 참값에 noise/fault 를 얹은 **측정값**(Day 11)이다.
참값과 측정값을 섞지 않는 것이 데이터 모델 불변조건이다.

frozen dataclass: 한 시점 스냅샷을 불변으로 다루어
"이전 상태를 제자리 수정"하지 않고 항상 새 상태를 만든다 (상태전이 명확).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ActuatorMode, ActuatorType


@dataclass(frozen=True)
class EnvironmentState:
    """
    재배실 환경 **참값** 한 시점.

    simulation_time: 이 상태가 유효한 가상 시계(초).
    step_environment 가 반환할 때마다 dt 만큼 증가한다.
    """

    temperature_c: float
    humidity_pct: float
    co2_ppm: float
    substrate_moisture_pct: float  # Day 10 전이식 대상 (지금은 유지)
    ppfd_umol: float  # Day 10 LED 관계 대상 (지금은 유지)
    simulation_time: float = 0.0


@dataclass(frozen=True)
class InitialEnvironmentState:
    """
    런/시드 시작 시 쓰는 기본 참값.

    EnvironmentState 와 필드는 같되 simulation_time 은 변환 시 주입한다.
    __post_init__ 범위 검사는 units / params clamp 와 같은 MVP 물리 구간.
    """

    temperature_c: float = 24.0
    humidity_pct: float = 60.0
    co2_ppm: float = 800.0
    substrate_moisture_pct: float = 45.0
    ppfd_umol: float = 0.0

    def __post_init__(self) -> None:
        if not -10.0 <= self.temperature_c <= 50.0:
            raise ValueError("temperature_c out of physical range")
        if not 0.0 <= self.humidity_pct <= 100.0:
            raise ValueError("humidity_pct out of range")
        if not 300.0 <= self.co2_ppm <= 5000.0:
            raise ValueError("co2_ppm out of range")
        if not 0.0 <= self.substrate_moisture_pct <= 100.0:
            raise ValueError("substrate_moisture_pct out of range")
        if not 0.0 <= self.ppfd_umol <= 2000.0:
            raise ValueError("ppfd_umol out of range")

    def to_environment_state(self, *, simulation_time: float = 0.0) -> EnvironmentState:
        """시드/설정 초기치를 상태전이 입력 형태로 변환한다."""
        return EnvironmentState(
            temperature_c=self.temperature_c,
            humidity_pct=self.humidity_pct,
            co2_ppm=self.co2_ppm,
            substrate_moisture_pct=self.substrate_moisture_pct,
            ppfd_umol=self.ppfd_umol,
            simulation_time=simulation_time,
        )


@dataclass(frozen=True)
class OutdoorCondition:
    """
    외기 경계조건 한 시점 (WeatherAdapter 출력).

    실내 상태전이의 u_outdoor.
    co2_ppm 기본 420: 도시 대기 근사. SYNTHETIC/REPLAY 가 안 주면 이 값 사용.
    source: API | REPLAY | SYNTHETIC — lineage / 장애 시나리오 표시용.
    """

    temperature_c: float
    humidity_pct: float
    simulation_time: float
    source: str
    co2_ppm: float = 420.0


@dataclass(frozen=True)
class ActuatorCommandState:
    """
    설비 하나의 운전 스냅샷 → 상태전이 입력으로 쓰기 전 단계.

    mode=OFF 이면 물리적으로 출력이 나와도 무시한다 (effective_ratio=0).
    실제 ORM Actuator.mode / output_ratio 와 같은 의미를 도메인에 복제.
    """

    actuator_type: ActuatorType
    mode: ActuatorMode
    output_ratio: float  # 0~1 duty / 개도

    def __post_init__(self) -> None:
        if not 0.0 <= self.output_ratio <= 1.0:
            raise ValueError("output_ratio must be in [0, 1]")

    @property
    def effective_ratio(self) -> float:
        """상태전이 f(...) 에 넣을 실효 출력. OFF → 0."""
        if self.mode is ActuatorMode.OFF:
            return 0.0
        return self.output_ratio


@dataclass(frozen=True)
class ActuatorInputs:
    """
    상태전이식이 받는 설비 입력 벡터 u_actuators.

    각 필드는 [0,1]. 타입별로 이미 집계된 값이다.
    (룸에 HVAC 가 여러 대면 from_commands 가 max 로 합친다 — MVP)

    step_* 함수는 ActuatorType 을 직접 보지 않고 이 벡터만 본다.
    → 설비 목록 변경과 수식을 느슨하게 결합.
    """

    hvac: float = 0.0
    ventilation_fan: float = 0.0
    dehumidifier: float = 0.0
    irrigation_pump: float = 0.0
    led: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "hvac",
            "ventilation_fan",
            "dehumidifier",
            "irrigation_pump",
            "led",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")

    @classmethod
    def from_commands(cls, commands: list[ActuatorCommandState]) -> ActuatorInputs:
        """
        개별 설비 스냅샷 → 타입별 실효 출력.

        동일 타입 여러 대: max (가장 강하게 켜진 것). 
        합산(sum) 하면 1을 넘기기 쉬워 MVP 에선 max 가 안전하다.
        """
        ratios: dict[ActuatorType, float] = {item: 0.0 for item in ActuatorType}
        for command in commands:
            current = ratios[command.actuator_type]
            ratios[command.actuator_type] = max(current, command.effective_ratio)
        return cls(
            hvac=ratios[ActuatorType.HVAC],
            ventilation_fan=ratios[ActuatorType.VENTILATION_FAN],
            dehumidifier=ratios[ActuatorType.DEHUMIDIFIER],
            irrigation_pump=ratios[ActuatorType.IRRIGATION_PUMP],
            led=ratios[ActuatorType.LED],
        )
