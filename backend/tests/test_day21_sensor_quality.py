"""
6단계 Day 21 — sequence 중복·누락 검출, 품질 5단계, 품질 사유.

검증 의도
---------
- sequence: 중복·역순은 거부, 누락은 missing 마커 (상한 포함)
- 저장 품질: 시간 역전 BAD, 변화율·적재 지연 SUSPECT, 사유 누적
- 조회 품질: no_readings / 누락 마커 / 가상시각 stale / 적재 끊김 stale
- 시뮬 step 이 센서별 source_sequence 를 0 부터 이어 발급
- ingest API 가 중복을 거부하고 누락을 마커로 저장
- health API 가 최신 품질·분포를 돌려줌
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Sensor, SensorReading
from app.db.seed import FARM_ID, RUN_ID, seed_mvp
from app.db.session import SessionLocal
from app.domain.enums import ReadingQuality, SensorType
from app.domain.telemetry import (
    LatestReadingView,
    QualityConfig,
    QualityReason,
    StreamQualityAssessor,
    StreamState,
    assess_sensor_health,
    check_sequence,
)
from app.domain.telemetry.quality import (
    SequenceStatus,
    classify_stream_reading,
    join_reasons,
)
from app.main import app

T0 = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# sequence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("last", "incoming", "status", "missing"),
    [
        (None, 0, SequenceStatus.FIRST, 0),
        (None, 5, SequenceStatus.FIRST, 0),
        (4, 5, SequenceStatus.OK, 0),
        (4, 7, SequenceStatus.GAP, 2),
        (4, 4, SequenceStatus.DUPLICATE, 0),
        (4, 2, SequenceStatus.OUT_OF_ORDER, 0),
    ],
)
def test_check_sequence(
    last: int | None,
    incoming: int,
    status: SequenceStatus,
    missing: int,
) -> None:
    result = check_sequence(last, incoming)
    assert result.status is status
    assert result.missing_count == missing


def test_check_sequence_rejects_negative() -> None:
    with pytest.raises(ValueError):
        check_sequence(None, -1)


def _assess(
    assessor: StreamQualityAssessor,
    seq: int,
    value: float,
    t: float,
    **kwargs: object,
):
    return assessor.assess(
        "temp",
        sensor_type=SensorType.TEMPERATURE,
        source_sequence=seq,
        value=value,
        simulation_time=t,
        **kwargs,
    )


def test_duplicate_and_out_of_order_rejected_without_state_change() -> None:
    assessor = StreamQualityAssessor()
    assert _assess(assessor, 0, 24.0, 0.0).accepted
    assert _assess(assessor, 1, 24.1, 60.0).accepted
    before = assessor.state_for("temp")

    dup = _assess(assessor, 1, 99.0, 120.0)
    assert not dup.accepted
    assert dup.reject_reason == QualityReason.SEQUENCE_DUPLICATE.value

    late = _assess(assessor, 0, 24.0, 0.0)
    assert not late.accepted
    assert late.reject_reason == QualityReason.SEQUENCE_OUT_OF_ORDER.value

    assert assessor.state_for("temp") == before


def test_gap_creates_interpolated_missing_markers() -> None:
    assessor = StreamQualityAssessor()
    _assess(assessor, 0, 24.0, 0.0)
    result = _assess(assessor, 4, 24.2, 240.0)

    assert result.accepted
    assert result.sequence.status is SequenceStatus.GAP
    assert [m.source_sequence for m in result.missing_markers] == [1, 2, 3]
    assert [m.simulation_time for m in result.missing_markers] == [60.0, 120.0, 180.0]
    assert all(m.reason == QualityReason.SEQUENCE_GAP.value for m in result.missing_markers)
    assert result.verdict is not None
    assert QualityReason.SEQUENCE_GAP.value in result.verdict.reasons
    assert assessor.next_sequence("temp") == 5


def test_gap_markers_capped() -> None:
    assessor = StreamQualityAssessor(config=QualityConfig(max_missing_markers=3))
    _assess(assessor, 0, 24.0, 0.0)
    result = _assess(assessor, 11, 24.0, 660.0)
    assert len(result.missing_markers) == 3
    assert result.missing_truncated == 7


# ---------------------------------------------------------------------------
# 저장 품질
# ---------------------------------------------------------------------------


def _classify(value: float, t: float, state: StreamState, **kwargs: object):
    return classify_stream_reading(
        sensor_type=SensorType.TEMPERATURE,
        value=value,
        simulation_time=t,
        base_quality=kwargs.pop("base_quality", ReadingQuality.GOOD),
        base_reason=kwargs.pop("base_reason", None),
        state=state,
        **kwargs,
    )


def test_rate_of_change_flags_jump_but_not_normal_drift() -> None:
    state = StreamState(last_sequence=0, last_value=24.0, last_simulation_time=0.0)
    assert _classify(24.8, 60.0, state).quality is ReadingQuality.GOOD

    jump = _classify(30.0, 60.0, state)
    assert jump.quality is ReadingQuality.SUSPECT
    assert jump.reasons == (QualityReason.RATE_OF_CHANGE.value,)


def test_rate_deadband_absorbs_noise_on_short_dt() -> None:
    state = StreamState(last_sequence=0, last_value=24.0, last_simulation_time=0.0)
    assert _classify(24.3, 1.0, state).quality is ReadingQuality.GOOD


def test_time_reversal_is_bad_and_keeps_baseline() -> None:
    assessor = StreamQualityAssessor()
    _assess(assessor, 0, 24.0, 120.0)
    reversed_ = _assess(assessor, 1, 24.0, 60.0)
    assert reversed_.verdict is not None
    assert reversed_.verdict.quality is ReadingQuality.BAD
    assert QualityReason.TIME_REVERSED.value in reversed_.verdict.reasons

    state = assessor.state_for("temp")
    assert state.last_sequence == 1
    assert state.last_simulation_time == 120.0


def test_ingest_latency_is_suspect() -> None:
    verdict = _classify(
        24.0,
        60.0,
        StreamState(),
        sampled_at=T0,
        ingested_at=T0 + timedelta(seconds=45),
    )
    assert verdict.quality is ReadingQuality.SUSPECT
    assert verdict.reasons == (QualityReason.INGEST_LATENCY.value,)


def test_reasons_accumulate_and_worst_quality_wins() -> None:
    state = StreamState(last_sequence=0, last_value=24.0, last_simulation_time=0.0)
    verdict = _classify(
        50.0,
        60.0,
        state,
        base_quality=ReadingQuality.SUSPECT,
        base_reason="out_of_range_clamped_high",
    )
    assert verdict.quality is ReadingQuality.SUSPECT
    assert verdict.reason_text == "out_of_range_clamped_high;rate_of_change_exceeded"

    bad = _classify(
        24.0,
        -1.0,
        state,
        base_quality=ReadingQuality.SUSPECT,
        base_reason="out_of_range_clamped_high",
    )
    assert bad.quality is ReadingQuality.BAD


def test_reason_text_truncated_to_column_length() -> None:
    assert len(join_reasons(("x" * 100, "y" * 100)) or "") == 128


# ---------------------------------------------------------------------------
# 조회 품질
# ---------------------------------------------------------------------------


def _latest(
    quality: ReadingQuality = ReadingQuality.GOOD,
    t: float = 600.0,
    ingested_at: datetime = T0,
    reason: str | None = None,
) -> LatestReadingView:
    return LatestReadingView(
        quality=quality,
        quality_reason=reason,
        simulation_time=t,
        ingested_at=ingested_at,
    )


def test_health_missing_when_no_readings() -> None:
    verdict = assess_sensor_health(
        None, current_simulation_time=600.0, now=T0, run_running=True
    )
    assert verdict.quality is ReadingQuality.MISSING
    assert verdict.reason == QualityReason.NO_READINGS.value


def test_health_missing_when_latest_is_marker() -> None:
    verdict = assess_sensor_health(
        _latest(ReadingQuality.MISSING, reason="sequence_gap"),
        current_simulation_time=600.0,
        now=T0,
        run_running=True,
    )
    assert verdict.quality is ReadingQuality.MISSING


def test_health_stale_by_simulation_time() -> None:
    verdict = assess_sensor_health(
        _latest(t=300.0),
        current_simulation_time=600.0,
        now=T0,
        run_running=False,
    )
    assert verdict.quality is ReadingQuality.STALE
    assert verdict.reason == QualityReason.STALE_SIMULATION.value
    assert verdict.age_simulation_s == 300.0


def test_health_stale_by_wall_clock_only_while_running() -> None:
    old = _latest(ingested_at=T0 - timedelta(seconds=120))
    running = assess_sensor_health(
        old, current_simulation_time=600.0, now=T0, run_running=True
    )
    assert running.quality is ReadingQuality.STALE
    assert running.reason == QualityReason.STALE_INGEST.value

    paused = assess_sensor_health(
        old, current_simulation_time=600.0, now=T0, run_running=False
    )
    assert paused.quality is ReadingQuality.GOOD


def test_health_passes_stored_quality_when_fresh() -> None:
    verdict = assess_sensor_health(
        _latest(ReadingQuality.SUSPECT, reason="rate_of_change_exceeded"),
        current_simulation_time=600.0,
        now=T0,
        run_running=True,
    )
    assert verdict.quality is ReadingQuality.SUSPECT
    assert verdict.reason == "rate_of_change_exceeded"


# ---------------------------------------------------------------------------
# 통합 (실 DB)
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_farm(require_postgres: None) -> None:
    await seed_mvp(force=True)


@pytest.fixture
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _temp_rows() -> list[SensorReading]:
    async with SessionLocal() as session:
        sensor = await session.scalar(
            select(Sensor).where(Sensor.sensor_type == SensorType.TEMPERATURE)
        )
        assert sensor is not None
        return list(
            (
                await session.scalars(
                    select(SensorReading)
                    .where(SensorReading.sensor_id == sensor.id)
                    .order_by(SensorReading.sequence)
                )
            ).all()
        )


@pytest.mark.asyncio
async def test_step_issues_per_sensor_source_sequence(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    for _ in range(2):
        step = await api_client.post(
            f"/simulations/{RUN_ID}/step",
            json={"steps": 3, "dt_seconds": 60.0},
        )
        assert step.status_code == 200

    rows = await _temp_rows()
    assert [row.source_sequence for row in rows] == [0, 1, 2, 3, 4, 5]
    assert all(row.quality is ReadingQuality.GOOD for row in rows)


@pytest.mark.asyncio
async def test_ingest_rejects_duplicate_and_marks_gap(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")

    def reading(seq: int, t: float, value: float = 24.0) -> dict[str, object]:
        return {
            "sensor_type": "temperature",
            "raw_value": value,
            "input_unit": "C",
            "sequence": seq,
            "simulation_time": t,
        }

    response = await api_client.post(
        f"/simulations/{RUN_ID}/readings",
        json={
            "readings": [
                reading(0, 0.0),
                reading(1, 60.0),
                reading(1, 60.0),  # 중복
                reading(4, 240.0),  # 2·3 누락
                {**reading(5, 300.0), "input_unit": "ppm"},  # 단위 오류
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == 3
    assert body["missing_markers"] == 2
    assert [(r["index"], r["reason"]) for r in body["rejected"]] == [
        (2, "sequence_duplicate"),
        (4, "unit_incompatible"),
    ]
    assert body["quality_counts"] == {"good": 3, "missing": 2}

    rows = await _temp_rows()
    assert [row.source_sequence for row in rows] == [0, 1, 2, 3, 4]
    missing = [row for row in rows if row.quality is ReadingQuality.MISSING]
    assert [row.source_sequence for row in missing] == [2, 3]
    assert all(row.value is None and row.raw_value is None for row in missing)
    assert rows[-1].quality_reason == "sequence_gap"


@pytest.mark.asyncio
async def test_ingest_requires_sequence_and_active_run(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    payload = {
        "readings": [
            {
                "sensor_type": "temperature",
                "raw_value": 24.0,
                "input_unit": "C",
                "simulation_time": 0.0,
            }
        ]
    }
    created = await api_client.post(f"/simulations/{RUN_ID}/readings", json=payload)
    assert created.status_code == 409

    await api_client.post(f"/simulations/{RUN_ID}/start")
    response = await api_client.post(f"/simulations/{RUN_ID}/readings", json=payload)
    assert response.status_code == 200
    assert response.json()["rejected"][0]["reason"] == "sequence_required"


@pytest.mark.asyncio
async def test_sensor_health_reports_latest_quality(
    seeded_farm: None,
    api_client: AsyncClient,
) -> None:
    await api_client.post(f"/simulations/{RUN_ID}/start")
    await api_client.post(
        f"/simulations/{RUN_ID}/step",
        json={"steps": 2, "dt_seconds": 60.0},
    )

    response = await api_client.get(f"/farms/{FARM_ID}/sensors/health")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == str(RUN_ID)
    assert body["current_simulation_time"] == 120.0
    by_type = {item["sensor_type"]: item for item in body["sensors"]}

    temp = by_type["temperature"]
    assert temp["quality"] == "good"
    assert temp["source_sequence"] == 1
    assert temp["recent_counts"] == {"good": 2}
    assert temp["value"] is not None

    # 시뮬 가상 센서가 없는 구역 센서는 측정 이력이 없다
    assert by_type["substrate_ec"]["quality"] == "missing"
    assert by_type["substrate_ec"]["quality_reason"] == "no_readings"
    # 야간 PPFD는 참값 0 + 노이즈라 하한 클램프(suspect)가 될 수 있다
    summary = body["summary"]
    assert summary.get("good", 0) + summary.get("suspect", 0) == 5
