"""
구역 상태 프로세스 캐시 (DB 마이그레이션 전 MVP).

=============================================================================
작동 목적
-----------------------------------------------------------------------------
시뮬 step 마다 strawberry/grape ZoneEnvironmentState 를 갱신하고,
GET snapshot 이 같은 메모리를 읽어 관제 UI(작물 구역 패널)에 노출한다.

=============================================================================
만든 이유
-----------------------------------------------------------------------------
farm_states 테이블은 아직 룸 5메트릭만 담는다. 구역 컬럼/JSON을 바로
마이그레이션하면 Day17 snapshot·WS 계약을 크게 흔든다.
그래서 ConnectionManager 와 같이 **단일 워커 프로세스 메모리**에
구역 런타임(히스테리시스 포함)을 둔다.

=============================================================================
한계 / 다음 단계
-----------------------------------------------------------------------------
- 멀티 워커·재시작 시 구역 밸브 상태가 리셋된다 → 이후 DB/Redis 영속화.
- WS farm_state.updated 에는 아직 zones 가 없다 → 클라가 snapshot 재조회로
  최신을 맞춘다 (또는 추후 envelope 확장).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.crop import (
    FarmZonesSnapshot,
    ZoneLoopRuntime,
    bootstrap_zones,
    step_farm_zones,
    zone_to_dict,
)
from app.domain.simulation.state import ActuatorInputs, EnvironmentState


@dataclass
class _ZoneEntry:
    """farm_id 당 스냅샷 + 히스테리시스 런타임."""

    snapshot: FarmZonesSnapshot
    runtime: ZoneLoopRuntime


_CACHE: dict[uuid.UUID, _ZoneEntry] = {}


def clear_zone_cache(farm_id: uuid.UUID | None = None) -> None:
    """테스트·run 재시작 시 캐시 비우기."""
    if farm_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(farm_id, None)


def get_or_bootstrap_zones(
    farm_id: uuid.UUID,
    room: EnvironmentState,
) -> FarmZonesSnapshot:
    """없으면 룸 참값으로 bootstrap, 있으면 캐시 반환."""
    entry = _CACHE.get(farm_id)
    if entry is None:
        snap = bootstrap_zones(room)
        _CACHE[farm_id] = _ZoneEntry(snapshot=snap, runtime=ZoneLoopRuntime())
        return snap
    return entry.snapshot


def advance_zones(
    farm_id: uuid.UUID,
    *,
    room: EnvironmentState,
    actuators: ActuatorInputs,
    dt_seconds: float,
) -> FarmZonesSnapshot:
    """
    시뮬 step 직후 호출.

    목적: 룸 EnvironmentState 가 갱신된 뒤 구역 관수·병해·LED 루프를 한 틱 전진.
    """
    entry = _CACHE.get(farm_id)
    if entry is None:
        snap = bootstrap_zones(room)
        entry = _ZoneEntry(snapshot=snap, runtime=ZoneLoopRuntime())
        _CACHE[farm_id] = entry

    next_snap, next_runtime = step_farm_zones(
        entry.snapshot,
        room=room,
        actuators=actuators,
        runtime=entry.runtime,
        dt_seconds=dt_seconds,
    )
    entry.snapshot = next_snap
    entry.runtime = next_runtime
    return next_snap


def zones_payload(farm_id: uuid.UUID, room: EnvironmentState) -> dict:
    """
    FarmZonesOut 직렬화용 dict.

    구역별 센서·파생 + Farm 공유 제어 요구(병해완화/LED)를 함께 실는다.
    """
    snap = get_or_bootstrap_zones(farm_id, room)
    return {
        "strawberry": {
            **zone_to_dict(snap.strawberry),
            "irrigation_valve_open": snap.strawberry_valve_open,
            "label": "딸기 구역",
        },
        "grape": {
            **zone_to_dict(snap.grape),
            "irrigation_valve_open": snap.grape_valve_open,
            "label": "포도 구역",
        },
        "disease_mitigation_active": snap.disease_mitigation_active,
        "led_demand_ratio": snap.led_demand_ratio,
        "last_irrigation_reason": snap.last_irrigation_reason,
        "last_disease_reason": snap.last_disease_reason,
        "last_led_reason": snap.last_led_reason,
    }
