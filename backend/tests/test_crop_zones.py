"""
작물 구역 · 파생값 · 관수/병해/LED 폐쇄루프 단위 테스트.

검증 의도
---------
- 딸기≠포도 프로필 setpoint
- VPD/DLI 파생
- 딸기 관수 히스테리시스 수렴
- 포도 병해완화 → 엽면습윤·위험 감소
- DLI 목표 도달 시 LED 감광
"""

from dataclasses import replace

from app.domain.crop import (
    GRAPE_PROFILE,
    STRAWBERRY_PROFILE,
    ZoneLoopRuntime,
    bootstrap_zones,
    decide_disease_mitigation,
    decide_led_for_dli,
    decide_zone_irrigation,
    dli_increment_mol,
    step_farm_zones,
    vapor_pressure_deficit_kpa,
)
from app.domain.enums import CropKind, ZoneId
from app.domain.simulation.state import ActuatorInputs, EnvironmentState


def _room(
    *,
    moisture: float = 45.0,
    t: float = 24.0,
    rh: float = 60.0,
    ppfd: float = 200.0,
    sim_t: float = 0.0,
) -> EnvironmentState:
    return EnvironmentState(
        temperature_c=t,
        humidity_pct=rh,
        co2_ppm=800.0,
        substrate_moisture_pct=moisture,
        ppfd_umol=ppfd,
        simulation_time=sim_t,
    )


def test_profiles_are_separated() -> None:
    assert STRAWBERRY_PROFILE.zone_id is ZoneId.STRAWBERRY
    assert GRAPE_PROFILE.zone_id is ZoneId.GRAPE
    assert STRAWBERRY_PROFILE.irrigation_start_vwc_pct != (
        GRAPE_PROFILE.irrigation_start_vwc_pct
    )
    assert STRAWBERRY_PROFILE.crop is CropKind.STRAWBERRY


def test_vpd_increases_when_humidity_drops() -> None:
    high = vapor_pressure_deficit_kpa(25.0, 80.0)
    low = vapor_pressure_deficit_kpa(25.0, 40.0)
    assert low > high
    assert high > 0.0


def test_dli_integrates_ppfd() -> None:
    assert abs(dli_increment_mol(500.0, 3600.0) - 1.8) < 1e-9


def test_strawberry_irrigation_hysteresis() -> None:
    start = decide_zone_irrigation(
        profile=STRAWBERRY_PROFILE,
        substrate_vwc_pct=30.0,
        valve_currently_open=False,
    )
    assert start.valve_open is True

    hold = decide_zone_irrigation(
        profile=STRAWBERRY_PROFILE,
        substrate_vwc_pct=40.0,
        valve_currently_open=True,
    )
    assert hold.valve_open is True

    stop = decide_zone_irrigation(
        profile=STRAWBERRY_PROFILE,
        substrate_vwc_pct=50.0,
        valve_currently_open=True,
    )
    assert stop.valve_open is False


def test_grape_uses_different_start_threshold() -> None:
    vwc = 32.0
    berry = decide_zone_irrigation(
        profile=STRAWBERRY_PROFILE,
        substrate_vwc_pct=vwc,
        valve_currently_open=False,
    )
    grape = decide_zone_irrigation(
        profile=GRAPE_PROFILE,
        substrate_vwc_pct=vwc,
        valve_currently_open=False,
    )
    assert berry.valve_open is True
    assert grape.valve_open is False


def test_closed_loop_strawberry_irrigation_raises_then_stops() -> None:
    room = _room(moisture=45.0)
    zones = bootstrap_zones(room)
    zones = replace(
        zones,
        strawberry=replace(zones.strawberry, substrate_vwc_pct=30.0),
    )
    runtime = ZoneLoopRuntime()
    actuators = ActuatorInputs()

    saw_open = False
    saw_flow = False
    final_open = True

    for _ in range(120):
        room = replace(room, simulation_time=room.simulation_time + 60.0)
        zones, runtime = step_farm_zones(
            zones,
            room=room,
            actuators=actuators,
            runtime=runtime,
            dt_seconds=60.0,
        )
        if runtime.strawberry_valve_open:
            saw_open = True
        if zones.strawberry.irrigation_flow_lpm > 0:
            saw_flow = True
        if (
            saw_open
            and not runtime.strawberry_valve_open
            and zones.strawberry.substrate_vwc_pct
            >= STRAWBERRY_PROFILE.irrigation_stop_vwc_pct - 0.5
        ):
            final_open = runtime.strawberry_valve_open
            break
        final_open = runtime.strawberry_valve_open

    assert saw_open
    assert saw_flow
    assert (
        zones.strawberry.substrate_vwc_pct
        >= STRAWBERRY_PROFILE.irrigation_stop_vwc_pct - 1.0
    )
    assert final_open is False


def test_grape_disease_mitigation_reduces_wetness() -> None:
    """고습+긴 엽면습윤 → 완화 ON → 습윤·위험 감소."""
    # 위험 점수 높게: wetness >= threshold, temp in 15~25
    start = decide_disease_mitigation(
        profile=GRAPE_PROFILE,
        humidity_pct=90.0,
        leaf_wetness_minutes=200.0,
        disease_score=80.0,
        currently_active=False,
    )
    assert start.active is True

    room = _room(rh=90.0, t=22.0, ppfd=100.0)
    zones = bootstrap_zones(room)
    zones = replace(
        zones,
        grape=replace(
            zones.grape,
            leaf_wetness_minutes=200.0,
            disease_risk_score=80.0,
        ),
    )
    runtime = ZoneLoopRuntime()
    wet0 = zones.grape.leaf_wetness_minutes

    for _ in range(30):
        room = replace(room, simulation_time=room.simulation_time + 60.0)
        zones, runtime = step_farm_zones(
            zones,
            room=room,
            actuators=ActuatorInputs(),
            runtime=runtime,
            dt_seconds=60.0,
        )

    assert runtime.grape_disease_mitigation_active or zones.disease_mitigation_active
    assert zones.grape.leaf_wetness_minutes < wet0
    assert zones.grape.disease_risk_score < 80.0


def test_led_dims_when_dli_target_met() -> None:
    low = decide_led_for_dli(dli_today=2.0, target_dli=12.0)
    assert low.output_ratio > 0.3

    done = decide_led_for_dli(dli_today=12.0, target_dli=12.0)
    assert done.output_ratio == 0.0


def test_led_dli_loop_accumulates_then_demands_less() -> None:
    """PPFD 존재 시 DLI 누적 → 목표 근접 시 LED 요구가 감소."""
    room = _room(ppfd=800.0)
    zones = bootstrap_zones(room)
    runtime = ZoneLoopRuntime()
    # 딸기 목표 12, 고PPFD로 빠르게 채움
    ratios: list[float] = []
    for _ in range(40):
        room = replace(
            room,
            simulation_time=room.simulation_time + 600.0,
            ppfd_umol=800.0,
        )
        zones, runtime = step_farm_zones(
            zones,
            room=room,
            actuators=ActuatorInputs(),
            runtime=runtime,
            dt_seconds=600.0,
        )
        ratios.append(zones.led_demand_ratio)

    assert zones.strawberry.dli_today > 0.5
    # 후반에 목표 근접/도달하면 요구가 초반보다 작거나 0
    assert ratios[-1] <= ratios[0]
