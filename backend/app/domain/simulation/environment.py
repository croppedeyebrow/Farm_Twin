"""
실내 환경 상태전이 (3단계 Day 9).

=============================================================================
왜 이 모델인가
-----------------------------------------------------------------------------
FarmTwin 목표는 "난수 생성기"가 아니라 **인과관계가 설명 가능한** 가상 환경이다.
관제 UI·규칙 엔진·교육 시나리오에서
  "외기가 올랐으니 실내도 올랐다"
  "제습기를 켰으니 습도가 떨어졌다"
처럼 원인→결과를 그래프로 말할 수 있어야 한다.

물리 정밀 CFD/Psychrometrics 전모델은 MVP 범위를 넘는다.
대신 온실·실내 농업 시뮬에서 흔히 쓰는 **1차(선형) 혼합 + 설비 강제항**
형태를 오일러 적분으로 풀어, 방향성(sign)과 재현성을 먼저 확보한다.

=============================================================================
수학적 골격 (공통)
-----------------------------------------------------------------------------
연속 시간에서 상태 x 에 대해

    dx/dt = f(x, u_outdoor, u_actuators; θ)

를 시간 간격 Δt (= dt_seconds) 로 전방 오일러(explicit Euler) 근사:

    x(t+Δt) = x(t) + Δt · f(...)

- θ 는 EnvironmentModelParams (계수)
- 난수 항 없음 → 동일 입력이면 비트 단위로 같은 결과
- Δt=0 이면 상태 불변 (pause/idle 안전)

clamp: 적분 후 물리 범위로 잘라 발산을 막는다.
(정밀 포화·상대습도 곡선은 Day 10+ 에서 보강 가능)

Day 9 갱신: temperature / humidity / co2
Day 10 예정: substrate_moisture / ppfd (지금은 입력 그대로 통과)
"""

from __future__ import annotations

from app.domain.simulation.params import DEFAULT_ENV_PARAMS, EnvironmentModelParams
from app.domain.simulation.state import (
    ActuatorInputs,
    EnvironmentState,
    OutdoorCondition,
)


def _clamp(value: float, low: float, high: float) -> float:
    """값을 [low, high] 안으로 제한한다. 모델 발산·비물리 값 방지."""
    return min(high, max(low, value))


def step_temperature(
    temperature_c: float,
    *,
    outdoor_temperature_c: float,
    actuators: ActuatorInputs,
    dt_seconds: float,
    params: EnvironmentModelParams = DEFAULT_ENV_PARAMS,
) -> float:
    """
    실내 온도 T [°C] 한 스텝.

    ---------------------------------------------------------------------------
    연속 시간 식 (개념)
    ---------------------------------------------------------------------------
        dT/dt = k_leak · (T_out − T)          # 벽·틈새 수동 열교환
              + k_vent · u_fan · (T_out − T)  # 환기로 외기 혼합 가속
              − k_cool · u_hvac               # HVAC 냉방 (강제 하강항)
              + k_led  · u_led                # LED 발열 (강제 상승항)

    근거
    ----
    - (T_out − T) 항: 뉴턴 냉각/가열에 해당하는 **1차 혼합**.
      외기와 실내 차이가 클수록 변화율이 커지고, 같아지면 0.
      k_leak ≈ 1/τ 이고 τ=1800s 이면 "시정수 약 30분" 느낌의 느린 추적.
    - 환기: 같은 형태의 차를 fan 출력으로 스케일. 팬을 켤수록 외기에 빨리 수렴.
    - HVAC: MVP 는 **냉방 시나리오** 중심이라 목표온도 추적 대신
      출력에 비례한 음의 상수항으로 단순화 (고온→규칙→냉방 데모에 충분).
    - LED: 광원의 상당 에너지가 열로 전환된다는 관찰을 양의 상수항으로 반영.
      (PPFD 자체는 Day 10. 여기서는 열 부작용만.)

    이산
    ----
        T' = T + Δt · (leak + vent + cool + heat)
    """
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be >= 0")
    if dt_seconds == 0:
        return temperature_c

    # 수동 누설: 외기 쪽으로 지수적으로 끌려가는 힘
    leak = params.temp_outdoor_leak_per_s * (outdoor_temperature_c - temperature_c)
    # 환기 ON 시 같은 방향의 혼합을 가속 (u_fan ∈ [0,1])
    vent = (
        params.temp_vent_mix_per_s
        * actuators.ventilation_fan
        * (outdoor_temperature_c - temperature_c)
    )
    # 냉방: 외기 차와 무관하게 실내를 내리는다 (MVP 단순화)
    cool = -params.temp_hvac_cool_per_s * actuators.hvac
    # LED 발열
    heat = params.temp_led_heat_per_s * actuators.led

    next_t = temperature_c + dt_seconds * (leak + vent + cool + heat)
    return _clamp(next_t, params.temperature_min_c, params.temperature_max_c)


def step_humidity(
    humidity_pct: float,
    *,
    outdoor_humidity_pct: float,
    actuators: ActuatorInputs,
    dt_seconds: float,
    params: EnvironmentModelParams = DEFAULT_ENV_PARAMS,
) -> float:
    """
    실내 상대습도 H [%RH] 한 스텝.

    ---------------------------------------------------------------------------
    연속 시간 식 (개념)
    ---------------------------------------------------------------------------
        dH/dt = k_leak · (H_out − H)
              + k_vent · u_fan · (H_out − H)
              − k_dehum · u_dehumidifier      # 제습
              + k_irr   · u_irrigation        # 관수로 인한 약가습

    근거
    ----
    - 절대습도·노점·잠열을 풀지 않고 **상대습도 스칼라**만 다룬다.
      (교육·관제 데모용. 정밀 HVAC psychrometric 은 후속.)
    - 외기 혼합은 온도와 같은 1차 형태 → "환기하면 외기 RH 쪽으로 간다".
    - 제습기: 출력에 비례해 RH 를 낮추는 강제항 (실기기 제습량 근사).
    - 관수: Day 10 배지 수분과 본격 연계 전, 공기 중 수분 증가를 약하게 표현.

    이산
    ----
        H' = H + Δt · (leak + vent + dry + wet)
    """
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be >= 0")
    if dt_seconds == 0:
        return humidity_pct

    leak = params.humidity_outdoor_leak_per_s * (
        outdoor_humidity_pct - humidity_pct
    )
    vent = (
        params.humidity_vent_mix_per_s
        * actuators.ventilation_fan
        * (outdoor_humidity_pct - humidity_pct)
    )
    # 제습: RH 감소 방향
    dry = -params.humidity_dehumidifier_per_s * actuators.dehumidifier
    # 관수: RH 소폭 증가 (배지 증발의 약식)
    wet = params.humidity_irrigation_per_s * actuators.irrigation_pump

    next_h = humidity_pct + dt_seconds * (leak + vent + dry + wet)
    return _clamp(next_h, params.humidity_min_pct, params.humidity_max_pct)


def step_co2(
    co2_ppm: float,
    *,
    outdoor_co2_ppm: float,
    actuators: ActuatorInputs,
    dt_seconds: float,
    params: EnvironmentModelParams = DEFAULT_ENV_PARAMS,
) -> float:
    """
    실내 CO₂ 농도 C [ppm] 한 스텝.

    ---------------------------------------------------------------------------
    연속 시간 식 (개념)
    ---------------------------------------------------------------------------
        dC/dt = g_base                         # 밀폐 시 약한 발생(호흡·토양)
              − k_uptake · u_led               # 광합성 흡수 (광 ON 가정)
              + k_vent · u_fan · (C_out − C)   # 환기로 외기(~420ppm)와 혼합

    근거
    ----
    - 식물 군락의 순광합성은 광량에 크게 의존한다.
      MVP 는 PPFD 방정식을 Day 10 에 두므로, 여기서는 **LED 출력 ≈ 광 공급**
      대리변수로 흡수를 켠다. (암기에는 흡수 ≈ 0)
    - 환기는 온·습도와 동일하게 (C_out − C) 1차 혼합.
      실내가 높고 외기가 낮으면 환기 시 농도가 떨어진다 (환기 시나리오).
    - g_base: 완전 밀폐·암기에서도 천천히 쌓이는 약한 발생을 넣어
      "가만히 두면 조금 오른다"는 인과를 유지한다.

    이산
    ----
        C' = C + Δt · (generation + uptake + vent)
    """
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be >= 0")
    if dt_seconds == 0:
        return co2_ppm

    # 상시 약한 발생 (설비와 무관)
    generation = params.co2_base_generation_per_s
    # LED ON 비율만큼 광합성 흡수 (음수 기여)
    uptake = -params.co2_plant_uptake_per_s * actuators.led
    # 환기 혼합: C_out 쪽으로
    vent = (
        params.co2_vent_mix_per_s
        * actuators.ventilation_fan
        * (outdoor_co2_ppm - co2_ppm)
    )

    next_c = co2_ppm + dt_seconds * (generation + uptake + vent)
    return _clamp(next_c, params.co2_min_ppm, params.co2_max_ppm)


def step_environment(
    state: EnvironmentState,
    *,
    outdoor: OutdoorCondition,
    actuators: ActuatorInputs,
    dt_seconds: float,
    params: EnvironmentModelParams = DEFAULT_ENV_PARAMS,
) -> EnvironmentState:
    """
    환경 참값 벡터 한 스텝 (폐쇄 루프의 "다음 FarmState 계산" 핵심).

    입력
    ----
    - state: 이전 참값 (센서 noise 없음)
    - outdoor: WeatherAdapter 가 준 외기
    - actuators: 설비 effective 출력 0~1
    - dt_seconds: 가상 시계 진행량 (보통 clock.advance 전후 차)

    출력
    ----
    새 EnvironmentState. simulation_time 은 state + dt 로 전진.
    substrate_moisture / ppfd 는 Day 10 까지 복사만 한다.

    불변
    ----
    이 함수는 순수하다 (I/O·난수·전역 상태 없음).
    동일 인자 → 동일 반환 → 회귀·재현성 테스트의 기반.
    """
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be >= 0")

    temperature = step_temperature(
        state.temperature_c,
        outdoor_temperature_c=outdoor.temperature_c,
        actuators=actuators,
        dt_seconds=dt_seconds,
        params=params,
    )
    humidity = step_humidity(
        state.humidity_pct,
        outdoor_humidity_pct=outdoor.humidity_pct,
        actuators=actuators,
        dt_seconds=dt_seconds,
        params=params,
    )
    co2 = step_co2(
        state.co2_ppm,
        outdoor_co2_ppm=outdoor.co2_ppm,
        actuators=actuators,
        dt_seconds=dt_seconds,
        params=params,
    )
    return EnvironmentState(
        temperature_c=temperature,
        humidity_pct=humidity,
        co2_ppm=co2,
        # Day 10: 배지 수분·PPFD 방정식이 여기로 들어온다
        substrate_moisture_pct=state.substrate_moisture_pct,
        ppfd_umol=state.ppfd_umol,
        simulation_time=state.simulation_time + dt_seconds,
    )
