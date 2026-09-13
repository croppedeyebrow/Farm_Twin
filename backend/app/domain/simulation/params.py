"""
환경 모델 계수 θ (3단계 Day 9~10).

=============================================================================
역할
-----------------------------------------------------------------------------
상태전이식 dx/dt = f(..., θ) 의 θ 를 한곳에 모은다.
Day 10 부터 `simulator/config/environment_model.toml` 로 외부화 가능
(load_environment_params).

=============================================================================
단위·해석
-----------------------------------------------------------------------------
이름에 `_per_s` 가 붙은 항:
  - 혼합 계수 k  : [1/초]  ≈ 1/시정수(τ)
  - 강제항 계수  : [물리단위/초]

Day 10 추가
-----------
- substrate_* : 배지수분 [%/s]
- ppfd_*      : LED→PPFD 목표·추적
- *_min/max   : step 후 clamp 범위 (units.SENSOR_VALUE_RANGE 와 정합)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentModelParams:
    """오일러 상태전이 계수 묶음 (불변)."""

    # --- 온도 [°C] ---------------------------------------------------------
    temp_outdoor_leak_per_s: float = 1.0 / 1800.0
    temp_hvac_cool_per_s: float = 0.004
    temp_led_heat_per_s: float = 0.0015
    temp_vent_mix_per_s: float = 1.0 / 600.0

    # --- 습度 [%RH] --------------------------------------------------------
    humidity_outdoor_leak_per_s: float = 1.0 / 1800.0
    humidity_dehumidifier_per_s: float = 0.01
    humidity_vent_mix_per_s: float = 1.0 / 600.0
    humidity_irrigation_per_s: float = 0.002

    # --- CO₂ [ppm] ---------------------------------------------------------
    co2_plant_uptake_per_s: float = 0.05
    co2_vent_mix_per_s: float = 1.0 / 900.0
    co2_base_generation_per_s: float = 0.005

    # --- 배지수분 [%] (Day 10) ---------------------------------------------
    # 자연 건조(증발·식물 흡수 근사). 관수 없으면 monotonic 감소 방향.
    substrate_drydown_per_s: float = 0.00008
    # 관수 펌프 출력에 비례한 습윤.
    substrate_irrigation_per_s: float = 0.015
    # LED ON 시 광합성 증발 추가 (배지 건조 가속).
    substrate_transpiration_per_s: float = 0.00004

    # --- PPFD [µmol/m²/s] (Day 10) -------------------------------------------
    # LED output_ratio=1 일 때 수렴 목표 PPFD.
    ppfd_led_max_umol: float = 800.0
    # 목표 PPFD 로 1차 추적: dP/dt = k_track · (P_target − P)
    ppfd_track_per_s: float = 0.5

    # --- 적분 후 clamp -------------------------------------------------------
    temperature_min_c: float = -10.0
    temperature_max_c: float = 50.0
    humidity_min_pct: float = 0.0
    humidity_max_pct: float = 100.0
    co2_min_ppm: float = 300.0
    co2_max_ppm: float = 5000.0
    substrate_moisture_min_pct: float = 0.0
    substrate_moisture_max_pct: float = 100.0
    ppfd_min_umol: float = 0.0
    ppfd_max_umol: float = 2000.0


# 코드 내장 기본 θ (TOML 없을 때·단위 테스트용).
DEFAULT_ENV_PARAMS = EnvironmentModelParams()
