"""
가상 센서 측정 모델 (3단계 Day 11).

=============================================================================
왜 참값과 측정을 가르나
-----------------------------------------------------------------------------
관제·규칙은 "센서가 본 값"으로 움직이지만, 시뮬레이터의 물리 모델은
"실제로 방이 어떤 상태인가"로 움직여야 한다.

  FarmState / EnvironmentState  = 참값 (환경 모델 출력, noise 없음)
  SensorReading / SensorSample  = 측정값 (offset + noise + delay)

"센서 noise 가 FarmState 를 바꾸지 않는다" 는 3단계 완료 기준이자
데이터 모델 불변조건이다. 이 모듈의 measure() 는 state 를 절대 수정하지 않는다.

=============================================================================
측정 공식
-----------------------------------------------------------------------------
스텝 k 에서 채널 c 의 측정값:

    true_now      = EnvironmentState 의 해당 필드
    true_delayed  = true[k − delay_steps]     # delay_steps=0 → true_now
    y_k           = true_delayed + offset + ε
    ε ~ N(0, σ²)                               # σ = noise_std, 결정적 시드

그 후 units.SENSOR_VALUE_RANGE 로 clamp.
clamp 가 일어나면 quality = SUSPECT, 아니면 GOOD.

근거
----
- offset: 교정 오차·설치 편향 (고정 바이어스)
- noise : 전자/양자화 잡음의 1차 근사 (가우시안)
- delay : 통신·필터·샘플링 지연을 스텝 단위로 근사 (zero-order hold 버퍼)

=============================================================================
재현성 (결정적 RNG)
-----------------------------------------------------------------------------
HTTP 로 step 을 여러 번 나눠 호출해도 같은 가상 시각이면 같은 노이즈가
나오도록, 매 샘플마다

    Random(f"{seed}:{sensor_type}:{simulation_time:.6f}")

로 스트림을 다시 연다. (인스턴스 전역 RNG 누적 상태와 무관)
동일 seed + 동일 참값 시계열 → 동일 측정값.
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
    """
    센서 타입 하나당 측정 파라미터.

    - offset: 참값에 더하는 고정 편향 (단위는 sensor_type 의 기본 단위)
    - noise_std: 가우시안 σ. 0 이면 노이즈 항 없음
    - delay_steps: 몇 스텝 전 참값을 내보낼지 (0 = 즉시)
    """

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
    """
    DB 적재 전 도메인 측정 샘플.

    SensorReading ORM 행으로 투영된다.
    true_value 는 테스트·디버그용이며 farm_states 에 쓰지 않는다.
    """

    sensor_type: SensorType
    value: float  # 측정값 (offset+noise+delay+clamp 후)
    unit: Unit
    quality: ReadingQuality
    source: ReadingSource
    simulation_time: float
    true_value: float  # delay 적용 후·noise 적용 전 참값 스칼라


def true_value_for(state: EnvironmentState, sensor_type: SensorType) -> float:
    """
    환경 참값 벡터 → 센서 타입 스칼라.

    SensorType 과 EnvironmentState 필드가 1:1 대응한다.
    """
    mapping = {
        SensorType.TEMPERATURE: state.temperature_c,
        SensorType.HUMIDITY: state.humidity_pct,
        SensorType.CO2: state.co2_ppm,
        SensorType.SUBSTRATE_MOISTURE: state.substrate_moisture_pct,
        SensorType.PPFD: state.ppfd_umol,
    }
    return mapping[sensor_type]


# MVP 기본 채널. 숫자는 교육·데모용 스케일 (실측 calibration 아님).
# delay_steps 기본 0 — HTTP step 배치를 나눠도 delay 버퍼 단절 이슈를 피한다.
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
    여러 채널의 delay 링버퍼 + 결정적 노이즈 생성기.

    mutable: 같은 run 안에서 step 루프가 버퍼를 누적한다.
    measure(state) 는 state 를 변경하지 않고 SensorSample 목록만 반환한다.
    """

    seed: int  # SimulationRun.random_seed 와 맞추면 재현성 연결
    channels: tuple[SensorChannelConfig, ...] = DEFAULT_SENSOR_CHANNELS
    _buffers: dict[SensorType, deque[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # maxlen = delay_steps + 1 → 현재값 + 과거 delay 개 보관
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
        현재 참값 state 로부터 전 채널 측정 샘플을 만든다.

        처리 순서 (채널마다)
        --------------------
        1. true_now 를 버퍼에 append
        2. delay_steps 만큼 과거 참값 선택 (버퍼가 짧으면 가장 오래된 값)
        3. offset + 결정적 가우시안 noise
        4. 물리 범위 clamp → quality
        """
        samples: list[SensorSample] = []
        for channel in self.channels:
            true_now = true_value_for(state, channel.sensor_type)
            buffer = self._buffers[channel.sensor_type]
            buffer.append(true_now)

            # delay: 버퍼 워밍업 중에는 가능한 가장 오래된 참값을 유지
            if channel.delay_steps == 0:
                delayed_true = true_now
            elif len(buffer) > channel.delay_steps:
                delayed_true = buffer[-1 - channel.delay_steps]
            else:
                delayed_true = buffer[0]

            if channel.noise_std > 0:
                # 결정적: 동일 seed·타입·가상시각 → 동일 ε
                # (step API 를 여러 HTTP 요청으로 나눠도 시각만 같으면 동일)
                step_rng = random.Random(
                    f"{self.seed}:{channel.sensor_type.value}:{state.simulation_time:.6f}"
                )
                noise = step_rng.gauss(0.0, channel.noise_std)
            else:
                noise = 0.0

            raw = delayed_true + channel.offset + noise
            low, high = value_range_for(channel.sensor_type)
            clamped = min(high, max(low, raw))
            # clamp 발생 = 물리적으로 수상한 관측 → SUSPECT (삭제가 아니라 태그)
            quality = (
                ReadingQuality.SUSPECT if clamped != raw else ReadingQuality.GOOD
            )

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
    측정 후 참값 state 가 그대로인지 확인하기 쉬운 헬퍼.

    반환 (samples, 원본 state 참조).
    테스트에서 before/after 튜플 비교와 함께 쓴다.
    """
    bank = VirtualSensorBank(
        seed=seed,
        channels=channels or DEFAULT_SENSOR_CHANNELS,
    )
    samples = bank.measure(state)
    return samples, state
