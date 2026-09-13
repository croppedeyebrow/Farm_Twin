"""
환경 모델 계수 θ (3단계 Day 9).

=============================================================================
역할
-----------------------------------------------------------------------------
상태전이식 dx/dt = f(..., θ) 의 θ 를 한곳에 모은다.
코드를 바꾸지 않고 시나리오(빠른 반응 / 둔한 온실)를 바꾸려면
이 값(또는 Day 10 의 파일)만 조정하면 된다.

=============================================================================
단위·해석
-----------------------------------------------------------------------------
이름에 `_per_s` 가 붙은 항:
  - 혼합 계수 k  : [1/초]  ≈ 1/시정수(τ)
      예) 1/1800 → τ≈30분. "외기 차의 e-folding 시간" 감각.
  - 강제항 계수  : [물리단위/초]  (예: °C/s, %RH/s, ppm/s)
      출력 u=1 일 때 초당 변화량. Δt 를 곱하면 한 스텝 변화.

시정수 직관
------------
1차 시스템 x' = −(1/τ)(x − x_target) 에서
약 1τ 지나면 차이의 ~63% 가 줄어든다.
누설·환기 계수를 1/τ 형태로 두면 "몇 분 만에 외기에 얼마나 따라가나"
를 튜닝하기 쉽다.

주의
----
숫자는 **교육·데모용 MVP 스케일**이다. 특정 실측 온실 calibration 이 아니다.
Day 10 에서 YAML 등으로 외부화하고, 실험으로 맞출 수 있게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentModelParams:
    """
    오일러 상태전이 계수 묶음.

    frozen: 런타임에 실수로 바꿔 재현성을 깨지 않도록 불변.
    시나리오별 변형은 새 인스턴스(또는 설정 로드)로 만든다.
    """

    # --- 온도 [°C] ---------------------------------------------------------
    # 벽체·침기 등에 의한 수동 열교환. τ≈1800s (30분).
    temp_outdoor_leak_per_s: float = 1.0 / 1800.0
    # HVAC 풀출력 냉방 시 초당 하강량 [°C/s].
    # 0.004 * 300s ≈ 1.2°C → 5분 풀냉방에 체감 가능한 하락.
    temp_hvac_cool_per_s: float = 0.004
    # LED 풀출력 발열 [°C/s]. 광 열부하 데모용 (PPFD와 별개).
    temp_led_heat_per_s: float = 0.0015
    # 환기 팬 풀출력 시 외기 혼합 가속. τ≈600s (10분) 급.
    temp_vent_mix_per_s: float = 1.0 / 600.0

    # --- 습도 [%RH] --------------------------------------------------------
    # 온도 누설과 같은 시정수로 "외기 RH 추적" 속도 맞춤.
    humidity_outdoor_leak_per_s: float = 1.0 / 1800.0
    # 제습 풀출력 [%RH/s]. 0.01*300s = 3%p / 5분.
    humidity_dehumidifier_per_s: float = 0.01
    humidity_vent_mix_per_s: float = 1.0 / 600.0
    # 관수 시 공기 가습 약식 [%RH/s]. Day 10 배지 모델 전 임시.
    humidity_irrigation_per_s: float = 0.002

    # --- CO₂ [ppm] ---------------------------------------------------------
    # LED 풀출력 시 광합성 흡수 [ppm/s].
    # 0.05*600s = 30ppm / 10분 → 광 ON 시 눈에 띄는 감소.
    co2_plant_uptake_per_s: float = 0.05
    # 환기 혼합. τ≈900s (15분).
    co2_vent_mix_per_s: float = 1.0 / 900.0
    # 밀폐·암기 시 약한 발생 [ppm/s] (호흡·미생물 근사).
    co2_base_generation_per_s: float = 0.005

    # --- 적분 후 clamp (units.SENSOR_VALUE_RANGE 와 동일 계열) -------------
    # 비물리 발산을 막고, 센서/API 허용 범위와 맞춘다.
    temperature_min_c: float = -10.0
    temperature_max_c: float = 50.0
    humidity_min_pct: float = 0.0
    humidity_max_pct: float = 100.0
    co2_min_ppm: float = 300.0
    co2_max_ppm: float = 5000.0


# 모듈 전역 기본 θ. 테스트·데모가 공유한다.
DEFAULT_ENV_PARAMS = EnvironmentModelParams()
