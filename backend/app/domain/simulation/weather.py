"""
외기 adapter 계약 (3단계 Day 8).

=============================================================================
역할
-----------------------------------------------------------------------------
실내 상태전이의 경계조건 u_outdoor 를 공급한다.
시뮬레이터 코어는 WeatherAdapter Protocol 만 알고,
구현체(API/REPLAY/SYNTHETIC)는 교체 가능해야 한다 (의존성 역전).

모드
----
- SYNTHETIC: 수식으로 합성. 네트워크 없이 재현 가능. 데모·단위테스트 기본.
- REPLAY: 저장된 (t, T, H) 시계열을 그대로 재생. 회귀·실측 비교.
- API: 외부 기상 API. 장애 시 last_known → fallback (인프라 복구 시나리오).

상태전이와의 관계
----------------
매 스텝:
    outdoor = await weather.read(clock.now_seconds)
    state = step_environment(state, outdoor=outdoor, ...)
외기 T/H/CO₂ 가 leak·vent 항의 목표값(T_out, H_out, C_out)이 된다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.simulation.state import OutdoorCondition


@runtime_checkable
class WeatherAdapter(Protocol):
    """외기 조건을 simulation_time 기준으로 제공한다."""

    @property
    def mode(self) -> str:
        """API | REPLAY | SYNTHETIC"""

    async def read(self, simulation_time: float) -> OutdoorCondition:
        """해당 가상 시각의 외기 조건."""


class SyntheticWeatherAdapter:
    """
    합성 외기.

    ---------------------------------------------------------------------------
    공식
    ---------------------------------------------------------------------------
        θ(t) = 2π · t / period + phase(seed)

        T(t) = T_base + A_T · sin(θ)
        H(t) = H_base + A_H · sin(θ + π/2)   # 온도보다 1/4주기 위상차
               후 [0, 100] clamp

    근거
    ----
    - 일변화(diurnal cycle)를 최소한의 식으로 흉내 낸다. period 기본 86400s=1일.
    - sin 만 쓰면 T·H 가 동시에 같은 위상이 되어 비현실적이므로,
      습도에 π/2 위상차를 둬 "더울 때 상대적으로 다른 RH 패턴"을 표현.
    - seed → phase: 같은 수식이라도 시작 위상을 바꿔 시나리오를 분기.
      난수 스트림이 아니라 **결정적 위상**이라 재현 가능.
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
        # seed 의 0~359 도를 라디안 위상으로 (결정적)
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
    사전 적재 시계열 재생.

    samples: (simulation_time, temperature_c, humidity_pct) 오름차순 정렬.
    조회 시각 t 에 대해 t 이하인 샘플 중 최신 값을 반환 (zero-order hold).
    → 희소 실측 데이터를 스텝 함수로 붙일 때 흔히 쓰는 방식.
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
    외부 기상 API 자리 (계약만).

    운영 시나리오: API 성공 → last_known 갱신.
    실패 시 last_known 유지, 그마저 없으면 fallback(SYNTHETIC).
    "외기 입력 장애여도 시뮬이 멈추지 않고, 복구 후 정상값으로 돌아온다"
    는 인프라 스토리를 나중에 붙이기 위한 훅.
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
    """WeatherMode 문자열로 adapter 인스턴스를 고른다 (팩토리)."""
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
