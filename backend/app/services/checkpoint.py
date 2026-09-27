"""
run 체크포인트 — 재생이 원본과 같은 출발점에서 시작하게 한다 (6단계 Day 23).

=============================================================================
캡처 (모든 run, 첫 step_run 직전 1회)
-----------------------------------------------------------------------------
참값 FarmState 는 룸당 최신 1행이라 과거 시점을 다시 읽을 수 없다.
그래서 run 이 처음 스텝을 밟기 직전 상태를 simulation_runs.initial_state 에 남긴다.

  farm_state : 참값 5종 + 시각
  actuators  : 설비 코드별 mode / output_ratio
  streams    : 센서 코드별 수신측 판정 상태 + 송신 커서 (중간 시각 출발 대비)
  control    : 게이트 시각 + 진행 중 품질 차단

run 이 t=0 부터가 아니라 이미 진행된 상태에서 첫 캡처되면 그 시각이 재생 출발점이다.

=============================================================================
복원 (재생 run, 첫 스텝 1회)
-----------------------------------------------------------------------------
재생 run 은 원본과 같은 룸을 쓴다. 첫 스텝에서 룸 참값·설비를 체크포인트로
되돌리고, 송신 커서·품질 차단 메모리를 이어 받은 뒤 replay_input.restored 를 켠다.
판정 상태·게이트는 이 run 의 이력이 생기기 전까지 매 호출 시드로 쓴다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Actuator, FarmState, Sensor, SimulationRun
from app.domain.enums import ActuatorMode
from app.domain.telemetry import StreamState
from app.services.room_control import control_checkpoint, seed_blocked
from app.services.sender import SENDER_SEQUENCES
from app.services.telemetry import load_stream_states

CHECKPOINT_VERSION = 1


async def capture_initial_state(
    session: AsyncSession,
    run: SimulationRun,
    farm_state: FarmState,
    sensors: Iterable[Sensor],
    actuators: Iterable[Actuator],
) -> dict[str, Any]:
    states = await load_stream_states(session, run.id)
    streams: dict[str, dict[str, Any]] = {}
    for sensor in sensors:
        state = states.get(sensor.id)
        if state is None:
            continue
        streams[sensor.code] = {
            "last_sequence": state.last_sequence,
            "issued": SENDER_SEQUENCES.last_issued(run.id, sensor.id, state.last_sequence),
            "last_value": state.last_value,
            "last_simulation_time": state.last_simulation_time,
            "last_raw": state.last_raw,
            "flat_run": state.flat_run,
        }
    return {
        "version": CHECKPOINT_VERSION,
        "simulation_time": run.simulation_time_seconds,
        "farm_state": {
            "temperature_c": farm_state.temperature_c,
            "humidity_pct": farm_state.humidity_pct,
            "co2_ppm": farm_state.co2_ppm,
            "substrate_moisture_pct": farm_state.substrate_moisture_pct,
            "ppfd_umol": farm_state.ppfd_umol,
        },
        "actuators": [
            {
                "code": actuator.code,
                "actuator_type": actuator.actuator_type.value,
                "mode": actuator.mode.value,
                "output_ratio": actuator.output_ratio,
            }
            for actuator in sorted(actuators, key=lambda item: item.code)
        ],
        "streams": streams,
        "control": await control_checkpoint(session, run.id),
    }


def seed_stream_states(
    initial_state: Mapping[str, Any],
    sensors: Iterable[Sensor],
) -> dict[uuid.UUID, StreamState]:
    streams = initial_state.get("streams") or {}
    seeded: dict[uuid.UUID, StreamState] = {}
    for sensor in sensors:
        item = streams.get(sensor.code)
        if item is None:
            continue
        seeded[sensor.id] = StreamState(
            last_sequence=item.get("last_sequence"),
            last_value=item.get("last_value"),
            last_simulation_time=item.get("last_simulation_time"),
            last_raw=item.get("last_raw"),
            flat_run=int(item.get("flat_run") or 0),
        )
    return seeded


def seed_gates(initial_state: Mapping[str, Any]) -> dict[str, Any]:
    return dict((initial_state.get("control") or {}).get("gates") or {})


def restore_replay_start(
    run: SimulationRun,
    farm_state: FarmState,
    sensors: Iterable[Sensor],
    actuators: Iterable[Actuator],
) -> None:
    """재생 run 첫 스텝 — 룸을 원본 체크포인트로 되돌린다 (commit 은 호출자)."""
    initial = run.initial_state or {}
    state = initial.get("farm_state") or {}
    farm_state.temperature_c = state["temperature_c"]
    farm_state.humidity_pct = state["humidity_pct"]
    farm_state.co2_ppm = state["co2_ppm"]
    farm_state.substrate_moisture_pct = state["substrate_moisture_pct"]
    farm_state.ppfd_umol = state["ppfd_umol"]
    farm_state.simulation_time = run.simulation_time_seconds
    farm_state.simulation_run_id = run.id

    saved = {item["code"]: item for item in initial.get("actuators") or []}
    for actuator in actuators:
        item = saved.get(actuator.code)
        if item is None:
            actuator.mode = ActuatorMode.OFF
            actuator.output_ratio = 0.0
            continue
        actuator.mode = ActuatorMode(item["mode"])
        actuator.output_ratio = float(item["output_ratio"])

    streams = initial.get("streams") or {}
    for sensor in sensors:
        item = streams.get(sensor.code)
        if item is None or item.get("issued") is None:
            continue
        SENDER_SEQUENCES.seed(
            run.id,
            sensor.id,
            issued=int(item["issued"]),
            received=item.get("last_sequence"),
        )
    seed_blocked(run.id, (initial.get("control") or {}).get("blocked") or {})

    run.replay_input = {**(run.replay_input or {}), "restored": True}


def scheduled_manual_actions(
    run: SimulationRun,
    *,
    step_start: float,
    dt_seconds: float,
) -> list[dict[str, Any]]:
    """
    이번 스텝 시작 시각에 적용할 원본 수동 변경.

    원본은 스텝 사이(run 시계 = t)에 설비를 바꿨고 그 다음 스텝이 새 출력으로 돌았다.
    그래서 (step_start - dt, step_start] 구간에 기록된 변경을 이 스텝 전에 적용한다.
    """
    actions = (run.replay_input or {}).get("manual_actions") or []
    return [
        action
        for action in actions
        if step_start - dt_seconds < float(action["simulation_time"]) <= step_start
    ]
