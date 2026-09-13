"""
가상 센서 측정 모델 (3단계 Day 11).

=============================================================================
불변조건
-----------------------------------------------------------------------------
- FarmState / EnvironmentState 는 **참값**이다. 이 모듈은 절대 수정하지 않는다.
- SensorReading 만 offset + noise + delay 가 적용된 **측정값**이다.
- 동일 seed + 동일 참값 시계열 → 동일 측정값 (결정적 RNG).

=============================================================================
모델
-----------------------------------------------------------------------------
측정값 y_k:

    true_delayed = true[k − delay_steps]   # delay_steps=0 이면 현재 참값
    y_k = true_delayed + offset + N(0, σ²)

- offset: 고정 바이어스 (°C, % 등 단위는 센서 타입 따름)
- σ (noise_std): 가우시안 표준편차. 0 이면 노이즈 없음
- delay_steps: 샘플 스텝 단위 지연 (통신/필터 지연 근사)

RNG 는 random.Random(seed ⊕ sensor_key) 로 센서별 스트림을 분리한다.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from app.domain.enums import ReadingQuality, ReadingSource, SensorType, Unit
from app.domain.simulation.state import EnvironmentState
from app.domain.units import default_unit_for, value_range_for


@dataclass(frozen=True)
class SensorChannelConfig:
    """센서 타입 하나당 offset / noise / delay."""

    sensor_type: SensorType
    offset: float = 0.0
    noise_std: float = 0.0
    delay_steps: int = 0

    def __post_init__(self) -> None:
        if self.noise_std < 0:
            raise ValueError("noise_std must be >= 0")
        if self.delay_steps < 0:
            raise ValueError("delay_steps must be >= 0")


@dataclass(frozen=True)
class SensorSample:
    """DB 적재 전 도메인 측정 샘플 (SensorReading 투영용)."""

    sensor_type: SensorType
    value: float
    unit: Unit
    quality: ReadingQuality
    source: ReadingSource
    simulation_time: float
    true_value: float  # 참값(지연 적용 전·후 비교/테스트용). FarmState 에 쓰지 않음.


def true_value_for(state: EnvironmentState, sensor_type: SensorType) -> float:
    """EnvironmentState 참값에서 센서 타입에 해당하는 스칼라를 고른다."""
    mapping = {
        SensorType.TEMPERATURE: state.temperature_c,
        SensorType.HUMIDITY: state.humidity_pct,
        SensorType.CO2: state.co2_ppm,
        SensorType.SUBSTRATE_MOISTURE: state.substrate_moisture_pct,
        SensorType.PPFD: state.ppfd_umol,
    }
    return mapping[sensor_type]


DEFAULT_SENSOR_CHANNELS: tuple[SensorChannelConfig, ...] = (
    SensorChannelConfig(SensorType.TEMPERATURE, offset=0.1, noise_std=0.05),
    SensorChannelConfig(SensorType.HUMIDITY, offset=-0.5, noise_std=0.3),
    SensorChannelConfig(SensorType.CO2, offset=5.0, noise_std=2.0),
    SensorChannelConfig(SensorType.SUBSTRATE_MOISTURE, offset=0.0, noise_std=0.4),
    SensorChannelConfig(SensorType.PPFD, offset=0.0, noise_std=5.0),
)


@dataclass
class VirtualSensorBank:
    """
    여러 채널의 delay 버퍼 + 결정적 노이즈.

    measure(state) 는 state 를 변경하지 않고 SensorSample 목록만 반환한다.
    """

    seed: int
    channels: tuple[SensorChannelConfig, ...] = DEFAULT_SENSOR_CHANNELS
    _buffers: dict[SensorType, deque[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # 인스턴스 전역 RNG 는 delay 버퍼와 함께 쓰되,
        # noise 자체는 (seed, type, simulation_time) 으로 다시 뽑아
        # HTTP step 배치가 갈라져도 같은 시각이면 같은 노이즈가 나오게 한다.
        self._buffers = {
            channel.sensor_type: deque(maxlen=max(channel.delay_steps, 0) + 1)
            for channel in self.channels
        }

    def measure(
        self,
        state: EnvironmentState,
        *,
        source: ReadingSource = ReadingSource.SIMULATED,
    ) -> list[SensorSample]:
        """
        현재 참값 state 로부터 측정 샘플을 만든다.

        순서: 버퍼에 현재 참값 push → delay 만큼 과거 참값 선택
             → offset + noise → 물리 범위 clamp → quality.
        """
        samples: list[SensorSample] = []
        for channel in self.channels:
            true_now = true_value_for(state, channel.sensor_type)
            buffer = self._buffers[channel.sensor_type]
            buffer.append(true_now)

            # delay: 버퍼가 짧으면 가장 오래된 값(아직 채워지는 중)
            if channel.delay_steps == 0:
                delayed_true = true_now
            elif len(buffer) > channel.delay_steps:
                delayed_true = buffer[-1 - channel.delay_steps]
            else:
                delayed_true = buffer[0]

            if channel.noise_std > 0:
                # 결정적: 동일 seed·타입·가상시각 → 동일 노이즈
                step_rng = random.Random(
                    f"{self.seed}:{channel.sensor_type.value}:{state.simulation_time:.6f}"
                )
                noise = step_rng.gauss(0.0, channel.noise_std)
            else:
                noise = 0.0
            raw = delayed_true + channel.offset + noise
            low, high = value_range_for(channel.sensor_type)
            clamped = min(high, max(low, raw))
            quality = ReadingQuality.GOOD
            if clamped != raw:
                quality = ReadingQuality.SUSPECT

            samples.append(
                SensorSample(
                    sensor_type=channel.sensor_type,
                    value=clamped,
                    unit=default_unit_for(channel.sensor_type),
                    quality=quality,
                    source=source,
                    simulation_time=state.simulation_time,
                    true_value=delayed_true,
                )
            )
        return samples


def measure_without_side_effects(
    state: EnvironmentState,
    *,
    seed: int,
    channels: tuple[SensorChannelConfig, ...] | None = None,
) -> tuple[list[SensorSample], EnvironmentState]:
    """
    측정 후 state 가 그대로인지 검증하기 쉬운 헬퍼.

    반환: (samples, 동일 state 참조/동등성 확인용 복사 전 원본)
    """
    bank = VirtualSensorBank(
        seed=seed,
        channels=channels or DEFAULT_SENSOR_CHANNELS,
    )
    samples = bank.measure(state)
    return samples, state
