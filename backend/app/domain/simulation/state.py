"""
환경 초기 상태 (3단계 Day 8).

FarmState 참값의 도메인 표현. ORM 에 의존하지 않는다.
시뮬레이터는 이 값으로 시작하고, 커밋 시 farm_states 로 투영한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InitialEnvironmentState:
    """재배실 환경 참값 초기치."""

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


@dataclass(frozen=True)
class OutdoorCondition:
    """외기 한 시점 값 (WeatherAdapter 출력)."""

    temperature_c: float
    humidity_pct: float
    simulation_time: float
    source: str
