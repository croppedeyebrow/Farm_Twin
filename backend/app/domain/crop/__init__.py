"""
작물 구역 도메인 (FarmTwin crop-zone MVP).

=============================================================================
작동 목적
-----------------------------------------------------------------------------
딸기·포도를 **같은 setpoint로 제어하지 않기** 위해, Farm 아래에
재배 구역(Zone)과 작물 프로필을 분리한다.

  Farm
  ├─ strawberry_zone  — 배지 재배 딸기 (근권·양액·과실에 민감)
  └─ grape_zone       — 토양·대형 배지 포도 (수관 미기후·엽면습윤에 민감)

룸 공통 EnvironmentState(공기 T/RH/CO₂/PPFD)는 공유하되,
배지 VWC·EC·엽면습윤·관수 밸브·병해 점수는 **구역 고유**로 둔다.

=============================================================================
만든 이유
-----------------------------------------------------------------------------
기존 모델은 센서 5종·액추에이터 5종·단일 룸 상태만 있어
온·습도·배지수분만으로는 딸기 Botrytis / 포도 흑부·Botrytis 인과를
설명하기 어렵다. 관수 밸브도 구역이 없으면 "딸기만 말랐는데 포도까지
같이 관수" 같은 비현실적 동작이 된다.

=============================================================================
관련 근거 (설계 메모)
-----------------------------------------------------------------------------
- 온도+상대습도 → VPD (증산·결로 지표)
- PPFD 시간적분 → DLI (일일 광량)
- 엽면습윤 지속시간 + 온도 → 곰팡이성 병해 위험
- 폐쇄루프 예시:
  1) 딸기 VWC↓ → 구역밸브 ON → 유량↑ → VWC↑ → OFF
  2) 포도 고습+엽면습윤 → 병해위험↑ → 순환/배기/천창
  3) PPFD 부족 → LED↑ → DLI 누적 → 목표 도달 후 감광

estimated_brix 는 센서 실측이 아니라 추정값이다 (당도계 검증 필요).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from app.domain.enums import CropKind, ZoneId
from app.domain.simulation.state import ActuatorInputs, EnvironmentState


# ---------------------------------------------------------------------------
# 작물 프로필 — 구역별 setpoint (딸기 ≠ 포도)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CropProfile:
    """
    구역 운전 기준.

    목적: 관수 히스테리시스·병해 임계·DLI 목표를 작물마다 다르게 고정.
    이유: 동일 threshold 를 쓰면 한 작물의 최적점이 다른 작물에 해가 됨.
    """

    crop: CropKind
    zone_id: ZoneId
    label: str
    # 관수 히스테리시스 (배지 VWC %) — start에서 ON, stop에서 OFF
    irrigation_start_vwc_pct: float
    irrigation_stop_vwc_pct: float
    # 공기·광 참고 범위 (UI / 생육 점수)
    air_temp_min_c: float
    air_temp_max_c: float
    humidity_min_pct: float
    humidity_max_pct: float
    # 병해: 엽면습윤 누적(분) 위험 임계 — 포도(송이)가 딸기보다 짧게 잡음
    leaf_wetness_risk_minutes: float
    # 병해 완화 히스테리시스 (위험 점수 0~100)
    disease_mitigation_start: float
    disease_mitigation_stop: float
    # DLI 목표 (mol/m²/d)
    target_dli: float
    # 배지 EC / 양액 pH 목표
    target_substrate_ec: float
    target_nutrient_ph: float


# 딸기: 배지 수분에 민감 → 관수 start를 높게(35%). DLI 목표는 상대적 낮음.
STRAWBERRY_PROFILE = CropProfile(
    crop=CropKind.STRAWBERRY,
    zone_id=ZoneId.STRAWBERRY,
    label="딸기 구역",
    irrigation_start_vwc_pct=35.0,
    irrigation_stop_vwc_pct=48.0,
    air_temp_min_c=18.0,
    air_temp_max_c=25.0,
    humidity_min_pct=45.0,
    humidity_max_pct=80.0,
    leaf_wetness_risk_minutes=240.0,
    disease_mitigation_start=45.0,
    disease_mitigation_stop=15.0,
    target_dli=12.0,
    target_substrate_ec=1.4,
    target_nutrient_ph=5.8,
)

# 포도: 뿌리 깊고 건조에 상대적으로 강함 → 관수 start 낮음(28%).
# 송이 구역 습윤에 민감 → 엽면습윤 위험 임계 짧게(180분).
#
# 3D 레퍼런스 (docs/refs/grape_arched_trellis_ref.png)
# ----------------------------------------------------
# 아치 수관 터널 + 송이 흰 봉지 + 흰 통로 반사시트 + 흑멀칭 + 점적관.
# → 수관 상부 미기후 ≠ 송이(봉지) 높이, PPFD는 캐노피 차단·하면 반사,
#   병해는 수관 정체 습윤 + 봉지 국부 습도를 함께 봐야 한다.
GRAPE_PROFILE = CropProfile(
    crop=CropKind.GRAPE,
    zone_id=ZoneId.GRAPE,
    label="포도 구역",
    irrigation_start_vwc_pct=28.0,
    irrigation_stop_vwc_pct=42.0,
    air_temp_min_c=20.0,
    air_temp_max_c=30.0,
    humidity_min_pct=40.0,
    humidity_max_pct=70.0,
    leaf_wetness_risk_minutes=180.0,
    disease_mitigation_start=40.0,
    disease_mitigation_stop=12.0,
    target_dli=20.0,
    target_substrate_ec=1.8,
    target_nutrient_ph=6.2,
)

PROFILES: dict[ZoneId, CropProfile] = {
    ZoneId.STRAWBERRY: STRAWBERRY_PROFILE,
    ZoneId.GRAPE: GRAPE_PROFILE,
}


def profile_for(zone_id: ZoneId) -> CropProfile:
    """ZoneId → 프로필. 잘못된 zone 은 KeyError (의도적)."""
    return PROFILES[zone_id]


# ---------------------------------------------------------------------------
# 파생값 — 센서 원시값이 아니라 제어·경보에 쓰는 계산량
# ---------------------------------------------------------------------------


def vapor_pressure_deficit_kpa(temperature_c: float, humidity_pct: float) -> float:
    """
    VPD [kPa] ≈ es(T) · (1 − RH/100)

    목적: 증산 구동력·결로 여유를 한 숫자로 본다.
    근거: Tetens 포화수증기압 es(T)=0.6108·exp(17.27·T/(T+237.3)) [kPa].
    """
    es = 0.6108 * exp((17.27 * temperature_c) / (temperature_c + 237.3))
    rh = max(0.0, min(100.0, humidity_pct))
    return max(0.0, es * (1.0 - rh / 100.0))


def dli_increment_mol(ppfd_umol: float, dt_seconds: float) -> float:
    """
    PPFD[μmol/m²/s] · Δt → mol/m² 가산분.

    목적: 일일 광량(DLI) 누적 — LED 감광 조건의 입력.
    근거: DLI = ∫ PPFD dt / 1e6  (μmol→mol).
    """
    if dt_seconds <= 0 or ppfd_umol <= 0:
        return 0.0
    return (ppfd_umol * dt_seconds) / 1_000_000.0


def disease_risk_score(
    *,
    temperature_c: float,
    leaf_wetness_minutes: float,
    risk_threshold_minutes: float,
) -> float:
    """
    곰팡이성 병해(Botrytis 등) 위험 점수 0~100.

    목적: 단순 RH 경보 대신 **젖은 시간**을 상태로 넣어 제어 트리거로 쓴다.
    근거: Botrytis 는 잎·과실이 장시간 젖은 환경에서 위험하며,
         15~25℃ 온난에서 가중된다 (딸기·포도 공통 경향).
    """
    wet = max(0.0, leaf_wetness_minutes)
    wet_factor = min(1.0, wet / max(risk_threshold_minutes, 1.0))
    if 15.0 <= temperature_c <= 25.0:
        temp_factor = 1.0
    elif 10.0 <= temperature_c < 15.0 or 25.0 < temperature_c <= 30.0:
        temp_factor = 0.6
    else:
        temp_factor = 0.25
    return round(100.0 * wet_factor * temp_factor, 1)


def water_stress_score(
    *,
    substrate_vwc_pct: float,
    start_vwc: float,
    stop_vwc: float,
) -> float:
    """
    배지 수분 부족 점수 0~100.

    목적: UI·추정 Brix·관수 긴급도에 쓸 연속 지표.
    이유: ON/OFF 밸브 상태만으로는 "얼마나 말랐는지"를 못 보여준다.
    """
    if substrate_vwc_pct >= stop_vwc:
        return 0.0
    if substrate_vwc_pct <= start_vwc - 10.0:
        return 100.0
    span = max(stop_vwc - (start_vwc - 10.0), 1.0)
    return round(100.0 * (stop_vwc - substrate_vwc_pct) / span, 1)


def estimated_brix(
    *,
    crop: CropKind,
    dli_today: float,
    target_dli: float,
    water_stress: float,
    simulation_days: float,
) -> float:
    """
    추정 당도(Brix).

    목적: 대시보드에 성숙 경향을 보여 주되, 실측과 혼동되지 않게 한다.
    이유: 굴절 당도계 없이는 검증 불가 — UI에 '추정' 배지 필수.
    근거: 휴리스틱(기준 + DLI 달성 − 수분 스트레스 + 일수). 학습 모델 아님.
    """
    base = 7.0 if crop is CropKind.STRAWBERRY else 14.0
    dli_term = 2.0 * min(1.2, dli_today / max(target_dli, 0.1))
    stress_pen = 0.03 * water_stress
    age_term = min(4.0, 0.05 * max(0.0, simulation_days))
    return round(max(0.0, base + dli_term - stress_pen + age_term), 1)


# ---------------------------------------------------------------------------
# 구역 상태 벡터
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoneEnvironmentState:
    """
    한 구역의 참값 + 파생 요약.

    공기 T/RH/CO₂/PPFD 는 룸을 미러링(MVP: 다층 미기후는 추후).
    근권·양액·엽면·유량·파생점수는 구역 고유 — 딸기/포도가 갈라지는 지점.
    """

    zone_id: ZoneId
    crop: CropKind
    air_temperature_c: float
    relative_humidity_pct: float
    co2_ppm: float
    ppfd: float
    substrate_vwc_pct: float
    substrate_ec: float
    substrate_temperature_c: float
    nutrient_ph: float
    nutrient_ec: float
    leaf_wetness_minutes: float
    irrigation_flow_lpm: float
    drainage_ratio_pct: float
    dli_today: float
    simulation_time: float
    vpd_kpa: float = 0.0
    water_stress_score: float = 0.0
    disease_risk_score: float = 0.0
    fruit_maturity_score: float = 0.0
    estimated_brix: float = 0.0


def initial_zone_state(
    profile: CropProfile,
    room: EnvironmentState,
    *,
    substrate_vwc_pct: float | None = None,
) -> ZoneEnvironmentState:
    """
    룸 참값에서 구역 초기 상태를 만든다.

    목적: snapshot / 시뮬 시작 시 두 구역을 동시에 세팅.
    이유: DB 마이그레이션 전에도 REST zones 필드를 채울 수 있게.
    """
    vwc = (
        substrate_vwc_pct
        if substrate_vwc_pct is not None
        else room.substrate_moisture_pct
    )
    vpd = vapor_pressure_deficit_kpa(room.temperature_c, room.humidity_pct)
    stress = water_stress_score(
        substrate_vwc_pct=vwc,
        start_vwc=profile.irrigation_start_vwc_pct,
        stop_vwc=profile.irrigation_stop_vwc_pct,
    )
    disease = disease_risk_score(
        temperature_c=room.temperature_c,
        leaf_wetness_minutes=0.0,
        risk_threshold_minutes=profile.leaf_wetness_risk_minutes,
    )
    return ZoneEnvironmentState(
        zone_id=profile.zone_id,
        crop=profile.crop,
        air_temperature_c=room.temperature_c,
        relative_humidity_pct=room.humidity_pct,
        co2_ppm=room.co2_ppm,
        ppfd=room.ppfd_umol,
        substrate_vwc_pct=vwc,
        substrate_ec=profile.target_substrate_ec,
        substrate_temperature_c=max(15.0, room.temperature_c - 2.0),
        nutrient_ph=profile.target_nutrient_ph,
        nutrient_ec=profile.target_substrate_ec,
        leaf_wetness_minutes=0.0,
        irrigation_flow_lpm=0.0,
        drainage_ratio_pct=0.0,
        dli_today=0.0,
        simulation_time=room.simulation_time,
        vpd_kpa=round(vpd, 3),
        water_stress_score=stress,
        disease_risk_score=disease,
        fruit_maturity_score=10.0,
        estimated_brix=estimated_brix(
            crop=profile.crop,
            dli_today=0.0,
            target_dli=profile.target_dli,
            water_stress=stress,
            simulation_days=0.0,
        ),
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def step_zone(
    zone: ZoneEnvironmentState,
    *,
    room: EnvironmentState,
    profile: CropProfile,
    actuators: ActuatorInputs,
    valve_ratio: float,
    dt_seconds: float,
) -> ZoneEnvironmentState:
    """
    구역 환경 한 스텝 (순수 함수).

    목적: 관수 밸브·환기·LED 입력이 구역 VWC·엽면습윤·DLI에 반영되게 한다.
    이유: 폐쇄루프 테스트가 "명령 → 상태 변화"를 재현 가능하게 증명하려면
         I/O 없는 오일러 적분이 필요하다 (EnvironmentState 와 동일 철학).
    """
    if dt_seconds < 0:
        raise ValueError("dt_seconds must be >= 0")

    # 구역 밸브 개도 = 관수 실효. 공유 펌프는 밸브 요구에 따라온다고 가정(MVP).
    # 이유: 펌프로만 묶으면 딸기/포도를 개별 관수할 수 없다.
    effective_irr = max(0.0, min(1.0, valve_ratio))
    flow_lpm = 12.0 * effective_irr  # 데모용 정격 12 L/min
    _ = actuators.irrigation_pump  # 추후 MANUAL OFF 게이트 자리

    # 배지 VWC: 건조 + 관수 회복 + LED 증산. 관수가 건조보다 빨라야 루프가 수렴.
    dry = -0.002 / 60.0
    wet = 0.4 / 60.0 * effective_irr
    transpire = -0.01 / 60.0 * actuators.led
    vwc = _clamp(
        zone.substrate_vwc_pct + dt_seconds * (dry + wet + transpire),
        0.0,
        100.0,
    )

    # 배액률: 공급 대비 배수 경향 (근권 염류 UI용 단순 지표)
    drainage = zone.drainage_ratio_pct
    if effective_irr > 0.05 and vwc > profile.irrigation_stop_vwc_pct:
        drainage = _clamp(drainage + dt_seconds * 0.02, 0.0, 40.0)
    else:
        drainage = _clamp(drainage - dt_seconds * 0.005, 0.0, 40.0)

    # 엽면습윤: 고습·저환기에서 누적 / 제습·배기·순환·천창에서 감소
    # 근거: 병해 완화 폐쇄루프가 실제로 wetness·risk 를 깎는지 보이게 함.
    wetness = zone.leaf_wetness_minutes
    vent = max(
        actuators.ventilation_fan,
        actuators.circulation_fan,
        actuators.vent_motor,
    )
    if room.humidity_pct >= 85.0 and vent < 0.2:
        wetness += dt_seconds / 60.0
    else:
        dry_rate = (
            0.5
            + 2.0 * actuators.dehumidifier
            + 1.5 * actuators.ventilation_fan
            + 1.2 * actuators.circulation_fan
            + 1.0 * actuators.vent_motor
        )
        wetness = max(0.0, wetness - dry_rate * (dt_seconds / 60.0))

    dli = zone.dli_today + dli_increment_mol(room.ppfd_umol, dt_seconds)
    day_index = int(room.simulation_time // 86400.0)
    prev_day = int(zone.simulation_time // 86400.0)
    if day_index > prev_day:
        # 가상 일 경계에서 DLI 리셋 (일일 목표 제어용)
        dli = dli_increment_mol(room.ppfd_umol, dt_seconds)

    vpd = vapor_pressure_deficit_kpa(room.temperature_c, room.humidity_pct)
    stress = water_stress_score(
        substrate_vwc_pct=vwc,
        start_vwc=profile.irrigation_start_vwc_pct,
        stop_vwc=profile.irrigation_stop_vwc_pct,
    )
    disease = disease_risk_score(
        temperature_c=room.temperature_c,
        leaf_wetness_minutes=wetness,
        risk_threshold_minutes=profile.leaf_wetness_risk_minutes,
    )
    sim_days = room.simulation_time / 86400.0
    maturity = _clamp(zone.fruit_maturity_score + dt_seconds * 0.0008, 0.0, 100.0)
    brix = estimated_brix(
        crop=profile.crop,
        dli_today=dli,
        target_dli=profile.target_dli,
        water_stress=stress,
        simulation_days=sim_days,
    )

    # 근권 온도: 공기보다 약간 낮고 1차 지연으로 추적 (급변 필터)
    sub_t = zone.substrate_temperature_c + 0.05 * (
        (room.temperature_c - 2.0) - zone.substrate_temperature_c
    )

    return ZoneEnvironmentState(
        zone_id=zone.zone_id,
        crop=zone.crop,
        air_temperature_c=room.temperature_c,
        relative_humidity_pct=room.humidity_pct,
        co2_ppm=room.co2_ppm,
        ppfd=room.ppfd_umol,
        substrate_vwc_pct=round(vwc, 3),
        substrate_ec=zone.substrate_ec,
        substrate_temperature_c=round(sub_t, 3),
        nutrient_ph=zone.nutrient_ph,
        nutrient_ec=zone.nutrient_ec,
        leaf_wetness_minutes=round(wetness, 3),
        irrigation_flow_lpm=round(flow_lpm, 3),
        drainage_ratio_pct=round(drainage, 3),
        dli_today=round(dli, 5),
        simulation_time=room.simulation_time,
        vpd_kpa=round(vpd, 3),
        water_stress_score=stress,
        disease_risk_score=disease,
        fruit_maturity_score=round(maturity, 2),
        estimated_brix=brix,
    )


# ---------------------------------------------------------------------------
# 폐쇄루프 1: 구역 관수 (딸기·포도 각각 다른 start/stop)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IrrigationDecision:
    """관수 밸브 판정 결과."""

    valve_open: bool
    valve_ratio: float
    reason: str


def decide_zone_irrigation(
    *,
    profile: CropProfile,
    substrate_vwc_pct: float,
    valve_currently_open: bool,
) -> IrrigationDecision:
    """
    배지수분 저하 → 구역 밸브 ON → 목표 도달 → OFF (히스테리시스).

    목적: "딸기만 말라서 딸기 밸브만 연다"를 가능하게 함.
    근거: start/stop 이중 임계로 임계점 채터링을 줄임 (제어 도메인과 동일 패턴).
    """
    start = profile.irrigation_start_vwc_pct
    stop = profile.irrigation_stop_vwc_pct

    if not valve_currently_open:
        if substrate_vwc_pct < start:
            return IrrigationDecision(
                True,
                1.0,
                f"VWC {substrate_vwc_pct:.1f}% < start {start}% → 관수 시작",
            )
        return IrrigationDecision(False, 0.0, "관수 대기")

    if substrate_vwc_pct >= stop:
        return IrrigationDecision(
            False,
            0.0,
            f"VWC {substrate_vwc_pct:.1f}% ≥ stop {stop}% → 관수 정지",
        )
    return IrrigationDecision(True, 1.0, "관수 유지")


# ---------------------------------------------------------------------------
# 폐쇄루프 2: 포도 병해 완화 (고습 + 엽면습윤 → 환기·순환·천창)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiseaseMitigationDecision:
    """
    병해 위험 완화용 설비 요구.

    목적: 위험도↑ → 공기 유동·제습·천창으로 엽면습윤↓ → 위험도↓.
    이유: RH만 보면 송이가 젖어 있는 시간을 놓친다.
    """

    active: bool
    ventilation_fan: float
    circulation_fan: float
    dehumidifier: float
    vent_motor: float
    reason: str


def decide_disease_mitigation(
    *,
    profile: CropProfile,
    humidity_pct: float,
    leaf_wetness_minutes: float,
    disease_score: float,
    currently_active: bool,
) -> DiseaseMitigationDecision:
    """
    포도(및 고위험 딸기) 병해 완화 히스테리시스.

    시작: disease_score ≥ start 또는 (고습 ∧ 습윤이 임계 절반 초과)
    해제: disease_score ≤ stop ∧ 습윤이 충분히 마름
    """
    start = profile.disease_mitigation_start
    stop = profile.disease_mitigation_stop
    wet_half = profile.leaf_wetness_risk_minutes * 0.5

    should_start = disease_score >= start or (
        humidity_pct >= 80.0 and leaf_wetness_minutes >= wet_half
    )
    should_stop = disease_score <= stop and leaf_wetness_minutes < 30.0

    if not currently_active:
        if should_start:
            return DiseaseMitigationDecision(
                True,
                1.0,
                1.0,
                0.7,
                0.8,
                f"병해위험 {disease_score:.0f} / 습윤 {leaf_wetness_minutes:.0f}min → 환기·순환",
            )
        return DiseaseMitigationDecision(
            False, 0.0, 0.0, 0.0, 0.0, "병해 완화 대기"
        )

    if should_stop:
        return DiseaseMitigationDecision(
            False,
            0.0,
            0.0,
            0.0,
            0.0,
            f"병해위험 {disease_score:.0f} · 습윤 감소 → 완화 해제",
        )
    return DiseaseMitigationDecision(
        True,
        1.0,
        1.0,
        0.7,
        0.8,
        "병해 완화 유지",
    )


# ---------------------------------------------------------------------------
# 폐쇄루프 3: LED → PPFD → DLI 누적 → 목표 도달 시 감광
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LedDliDecision:
    """공유 LED 요구 출력 (룸 설비 1대 가정)."""

    output_ratio: float
    reason: str


def decide_led_for_dli(
    *,
    dli_today: float,
    target_dli: float,
) -> LedDliDecision:
    """
    PPFD 부족 / DLI 미달 → LED 출력↑, 일일 목표 도달 → 감광.

    목적: 광 제어가 단순 ON/OFF가 아니라 **일적산**에 묶이게 한다.
    근거: DLI = ∫PPFD; 목표 달성 후 야간 과잉 조명을 줄인다.
    """
    if target_dli <= 0:
        return LedDliDecision(0.0, "DLI 목표 없음")
    if dli_today >= target_dli:
        return LedDliDecision(0.0, f"DLI {dli_today:.2f} ≥ 목표 {target_dli} → 감광")
    deficit = (target_dli - dli_today) / target_dli
    # 부족할수록 밝게: 최소 30% ~ 100%
    ratio = _clamp(0.3 + 0.7 * deficit, 0.0, 1.0)
    return LedDliDecision(
        round(ratio, 3),
        f"DLI {dli_today:.2f}/{target_dli} → LED {ratio * 100:.0f}%",
    )


def merge_actuator_inputs(
    base: ActuatorInputs,
    *,
    disease: DiseaseMitigationDecision,
    led: LedDliDecision,
) -> ActuatorInputs:
    """
    구역 제어 요구를 룸 ActuatorInputs 에 max-merge.

    목적: 기존 수동/규칙 출력과 구역 루프가 충돌하지 않게 **더 강한 쪽**을 택함.
    이유: MANUAL LED를 구역 루프가 강제로 끄면 운영자 의도가 깨진다.
    """
    return ActuatorInputs(
        hvac=base.hvac,
        ventilation_fan=max(base.ventilation_fan, disease.ventilation_fan),
        dehumidifier=max(base.dehumidifier, disease.dehumidifier),
        irrigation_pump=base.irrigation_pump,
        led=max(base.led, led.output_ratio),
        circulation_fan=max(base.circulation_fan, disease.circulation_fan),
        humidifier=base.humidifier,
        zone_valve_strawberry=base.zone_valve_strawberry,
        zone_valve_grape=base.zone_valve_grape,
        dosing_pump=base.dosing_pump,
        shade_curtain=base.shade_curtain,
        vent_motor=max(base.vent_motor, disease.vent_motor),
    )


# ---------------------------------------------------------------------------
# 런타임 · Farm 단위 step
# ---------------------------------------------------------------------------


@dataclass
class ZoneLoopRuntime:
    """
    구역 폐쇄루프 히스테리시스 메모리.

    DB에 넣기 전 MVP는 프로세스 메모리(zone_runtime 캐시)에 둔다.
    """

    strawberry_valve_open: bool = False
    grape_valve_open: bool = False
    grape_disease_mitigation_active: bool = False
    strawberry_disease_mitigation_active: bool = False


@dataclass(frozen=True)
class FarmZonesSnapshot:
    """두 구역 + 밸브/완화/LED 요구 요약 (API·UI 투영용)."""

    strawberry: ZoneEnvironmentState
    grape: ZoneEnvironmentState
    strawberry_valve_open: bool
    grape_valve_open: bool
    disease_mitigation_active: bool
    led_demand_ratio: float
    last_irrigation_reason: str = ""
    last_disease_reason: str = ""
    last_led_reason: str = ""


def bootstrap_zones(room: EnvironmentState) -> FarmZonesSnapshot:
    """
    룸 상태에서 두 구역을 초기화.

    포도는 의도적으로 조금 더 건조하게 시작해 프로필 차이(관수 start)가
    UI/테스트에서 체감되게 한다.
    """
    berry = initial_zone_state(STRAWBERRY_PROFILE, room)
    grape = initial_zone_state(
        GRAPE_PROFILE,
        room,
        substrate_vwc_pct=max(25.0, room.substrate_moisture_pct - 8.0),
    )
    return FarmZonesSnapshot(
        strawberry=berry,
        grape=grape,
        strawberry_valve_open=False,
        grape_valve_open=False,
        disease_mitigation_active=False,
        led_demand_ratio=0.0,
    )


def step_farm_zones(
    zones: FarmZonesSnapshot,
    *,
    room: EnvironmentState,
    actuators: ActuatorInputs,
    runtime: ZoneLoopRuntime,
    dt_seconds: float,
) -> tuple[FarmZonesSnapshot, ZoneLoopRuntime]:
    """
    Farm 단위 구역 step: 관수(구역별) → 병해완화(포도 우선) → LED/DLI → 상태적분.

    목적: 세 폐쇄루프를 한 틱에 순차 적용해 인과를 한 테스트에서 검증 가능하게.
    """
    # 1) 구역별 관수 (프로필 setpoint 분리)
    s_irr = decide_zone_irrigation(
        profile=STRAWBERRY_PROFILE,
        substrate_vwc_pct=zones.strawberry.substrate_vwc_pct,
        valve_currently_open=runtime.strawberry_valve_open,
    )
    g_irr = decide_zone_irrigation(
        profile=GRAPE_PROFILE,
        substrate_vwc_pct=zones.grape.substrate_vwc_pct,
        valve_currently_open=runtime.grape_valve_open,
    )

    # 2) 병해 완화 — 포도를 주 트리거로 (송이 습윤 시나리오). 딸기도 점수만 감시.
    g_dis = decide_disease_mitigation(
        profile=GRAPE_PROFILE,
        humidity_pct=room.humidity_pct,
        leaf_wetness_minutes=zones.grape.leaf_wetness_minutes,
        disease_score=zones.grape.disease_risk_score,
        currently_active=runtime.grape_disease_mitigation_active,
    )
    s_dis = decide_disease_mitigation(
        profile=STRAWBERRY_PROFILE,
        humidity_pct=room.humidity_pct,
        leaf_wetness_minutes=zones.strawberry.leaf_wetness_minutes,
        disease_score=zones.strawberry.disease_risk_score,
        currently_active=runtime.strawberry_disease_mitigation_active,
    )
    # 설비는 공유이므로 둘 중 하나라도 활성이면 merge
    disease_merged = DiseaseMitigationDecision(
        active=g_dis.active or s_dis.active,
        ventilation_fan=max(g_dis.ventilation_fan, s_dis.ventilation_fan),
        circulation_fan=max(g_dis.circulation_fan, s_dis.circulation_fan),
        dehumidifier=max(g_dis.dehumidifier, s_dis.dehumidifier),
        vent_motor=max(g_dis.vent_motor, s_dis.vent_motor),
        reason=g_dis.reason if g_dis.active else s_dis.reason,
    )

    # 3) LED/DLI — 두 구역 중 더 부족한 DLI 기준으로 공유 LED 요구
    #    (포도가 목표 DLI가 더 높아 보통 포도가 지배)
    led_s = decide_led_for_dli(
        dli_today=zones.strawberry.dli_today,
        target_dli=STRAWBERRY_PROFILE.target_dli,
    )
    led_g = decide_led_for_dli(
        dli_today=zones.grape.dli_today,
        target_dli=GRAPE_PROFILE.target_dli,
    )
    led = (
        led_g
        if led_g.output_ratio >= led_s.output_ratio
        else led_s
    )

    merged = merge_actuator_inputs(
        actuators, disease=disease_merged, led=led
    )

    next_runtime = ZoneLoopRuntime(
        strawberry_valve_open=s_irr.valve_open,
        grape_valve_open=g_irr.valve_open,
        grape_disease_mitigation_active=g_dis.active,
        strawberry_disease_mitigation_active=s_dis.active,
    )

    strawberry = step_zone(
        zones.strawberry,
        room=room,
        profile=STRAWBERRY_PROFILE,
        actuators=merged,
        valve_ratio=s_irr.valve_ratio,
        dt_seconds=dt_seconds,
    )
    grape = step_zone(
        zones.grape,
        room=room,
        profile=GRAPE_PROFILE,
        actuators=merged,
        valve_ratio=g_irr.valve_ratio,
        dt_seconds=dt_seconds,
    )

    return (
        FarmZonesSnapshot(
            strawberry=strawberry,
            grape=grape,
            strawberry_valve_open=next_runtime.strawberry_valve_open,
            grape_valve_open=next_runtime.grape_valve_open,
            disease_mitigation_active=disease_merged.active,
            led_demand_ratio=led.output_ratio,
            last_irrigation_reason=s_irr.reason,
            last_disease_reason=disease_merged.reason,
            last_led_reason=led.reason,
        ),
        next_runtime,
    )


def zone_to_dict(zone: ZoneEnvironmentState) -> dict[str, float | str]:
    """API/프론트 JSON 평탄화. Pydantic ZoneStateOut 과 키를 맞춘다."""
    return {
        "zone_id": zone.zone_id.value,
        "crop": zone.crop.value,
        "air_temperature_c": zone.air_temperature_c,
        "relative_humidity_pct": zone.relative_humidity_pct,
        "co2_ppm": zone.co2_ppm,
        "ppfd": zone.ppfd,
        "vpd_kpa": zone.vpd_kpa,
        "dli_today": zone.dli_today,
        "substrate_vwc_pct": zone.substrate_vwc_pct,
        "substrate_ec": zone.substrate_ec,
        "substrate_temperature_c": zone.substrate_temperature_c,
        "nutrient_ph": zone.nutrient_ph,
        "nutrient_ec": zone.nutrient_ec,
        "leaf_wetness_minutes": zone.leaf_wetness_minutes,
        "irrigation_flow_lpm": zone.irrigation_flow_lpm,
        "drainage_ratio_pct": zone.drainage_ratio_pct,
        "water_stress_score": zone.water_stress_score,
        "disease_risk_score": zone.disease_risk_score,
        "fruit_maturity_score": zone.fruit_maturity_score,
        "estimated_brix": zone.estimated_brix,
        "simulation_time": zone.simulation_time,
    }

