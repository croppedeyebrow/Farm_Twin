"""
외기 adapter 계약 (3단계 Day 8).

모드
----
- SYNTHETIC: 수식/시나리오로 합성
- REPLAY: 저장된 시계열 재생
- API: 외부 기상 API (장애 시 마지막 정상값 — 인프라 복구 시나리오)

시뮬레이터는 Protocol 만 의존하고, 구현체는 교체 가능하다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.simulation.state import OutdoorCondition


@runtime_checkable
class WeatherAdapter(Protocol):
    """외기 온·습도를 simulation_time 기준으로 제공한다."""

    @property
    def mode(self) -> str:
        """API | REPLAY | SYNTHETIC"""

    async def read(self, simulation_time: float) -> OutdoorCondition:
        """해당 가상 시각의 외기 조건을 반환한다."""


class SyntheticWeatherAdapter:
    """
    합성 외기.

    base + amplitude * sin(2π * t / period) 형태의 완만한 일변화.
    seed 는 위상 오프셋에만 사용해 재현 가능하게 한다.
    """

    def __init__(
        self,
        *,
        seed: int = 0,
        base_temperature_c: float = 22.0,
        temperature_amplitude_c: float = 4.0,
        base_humidity_pct: float = 55.0,
        humidity_amplitude_pct: float = 10.0,
        period_seconds: float = 86400.0,
    ) -> None:
        if period_seconds <= 0:
            raise ValueError("period_seconds must be > 0")
        self._seed = seed
        self._base_t = base_temperature_c
        self._amp_t = temperature_amplitude_c
        self._base_h = base_humidity_pct
        self._amp_h = humidity_amplitude_pct
        self._period = period_seconds
        # seed 로 위상 결정 (0~2π)
        self._phase = (seed % 360) * (3.141592653589793 / 180.0)

    @property
    def mode(self) -> str:
        return "SYNTHETIC"

    async def read(self, simulation_time: float) -> OutdoorCondition:
        import math

        angle = (2.0 * math.pi * simulation_time / self._period) + self._phase
        temperature = self._base_t + self._amp_t * math.sin(angle)
        humidity = self._base_h + self._amp_h * math.sin(angle + math.pi / 2)
        humidity = min(100.0, max(0.0, humidity))
        return OutdoorCondition(
            temperature_c=temperature,
            humidity_pct=humidity,
            simulation_time=simulation_time,
            source=self.mode,
        )


class ReplayWeatherAdapter:
    """
    사전 적재된 (simulation_time, temp, humidity) 시계열을 재생한다.

    요청 시각 이하 중 가장 최근 샘플을 반환한다 (step hold).
    """

    def __init__(
        self,
        samples: list[tuple[float, float, float]],
    ) -> None:
        if not samples:
            raise ValueError("samples must not be empty")
        self._samples = sorted(samples, key=lambda row: row[0])

    @property
    def mode(self) -> str:
        return "REPLAY"

    async def read(self, simulation_time: float) -> OutdoorCondition:
        chosen = self._samples[0]
        for sample in self._samples:
            if sample[0] <= simulation_time:
                chosen = sample
            else:
                break
        return OutdoorCondition(
            temperature_c=chosen[1],
            humidity_pct=chosen[2],
            simulation_time=simulation_time,
            source=self.mode,
        )


class ApiWeatherAdapter:
    """
    외부 API 자리 (Day 8 계약만).

    실제 HTTP 호출은 이후 단계에서 붙인다.
    지금은 last_known 또는 fallback 합성값을 반환한다.
    """

    def __init__(
        self,
        *,
        fallback: WeatherAdapter | None = None,
        last_known: OutdoorCondition | None = None,
    ) -> None:
        self._fallback = fallback or SyntheticWeatherAdapter(seed=0)
        self._last_known = last_known

    @property
    def mode(self) -> str:
        return "API"

    async def read(self, simulation_time: float) -> OutdoorCondition:
        # TODO(day8+): 실제 기상 API 연동. 실패 시 last_known → fallback.
        if self._last_known is not None:
            return OutdoorCondition(
                temperature_c=self._last_known.temperature_c,
                humidity_pct=self._last_known.humidity_pct,
                simulation_time=simulation_time,
                source=self.mode,
            )
        outdoor = await self._fallback.read(simulation_time)
        return OutdoorCondition(
            temperature_c=outdoor.temperature_c,
            humidity_pct=outdoor.humidity_pct,
            simulation_time=simulation_time,
            source=self.mode,
        )


def create_weather_adapter(
    mode: str,
    *,
    seed: int = 0,
    replay_samples: list[tuple[float, float, float]] | None = None,
) -> WeatherAdapter:
    """WeatherMode 문자열로 adapter 를 생성한다."""
    normalized = mode.upper()
    if normalized == "SYNTHETIC":
        return SyntheticWeatherAdapter(seed=seed)
    if normalized == "REPLAY":
        if not replay_samples:
            raise ValueError("REPLAY mode requires replay_samples")
        return ReplayWeatherAdapter(replay_samples)
    if normalized == "API":
        return ApiWeatherAdapter(fallback=SyntheticWeatherAdapter(seed=seed))
    raise ValueError(f"unknown weather mode: {mode}")
