"""
센서 스트림 품질 판정 (6단계 Day 21).

=============================================================================
판정 위치
-----------------------------------------------------------------------------
Day 20 파이프라인은 reading 한 건만 보고 범위 clamp → SUSPECT 를 붙였다.
Day 21 은 **같은 센서 스트림의 직전 상태**를 함께 봐야 알 수 있는 이상을 다룬다.

  송신측(센서/시뮬)  : 센서별 source_sequence 를 1씩 증가시켜 보낸다.
  수신측(이 모듈)    : 직전 sequence·값·시각과 비교해 품질을 판정한다.

=============================================================================
저장 품질 (reading 한 건에 붙는다)
-----------------------------------------------------------------------------
| 검사            | 결과                        | 사유 코드                     |
|-----------------|-----------------------------|-------------------------------|
| sequence 중복   | 거부 (저장 안 함)           | sequence_duplicate            |
| sequence 역순   | 거부 (저장 안 함)           | sequence_out_of_order         |
| sequence 누락   | 빈 번호마다 MISSING 마커 행 | sequence_gap                  |
| 시간 역전       | BAD                         | time_reversed                 |
| 원시값 고정     | BAD                         | flatline_detected (Day 22)    |
| 변화율 초과     | SUSPECT                     | rate_of_change_exceeded       |
| 적재 지연 초과  | SUSPECT                     | ingest_latency_exceeded       |
| 범위 밖 (Day20) | SUSPECT                     | out_of_range_clamped_low/high |

여러 검사가 동시에 걸리면 가장 나쁜 품질(BAD > SUSPECT > GOOD)을 쓰고
사유는 `;` 로 이어 붙인다.

=============================================================================
조회 품질 (최신값을 조회 시점에 다시 본다)
-----------------------------------------------------------------------------
stale 은 "값이 틀렸다"가 아니라 "값이 너무 오래됐다"라서 저장 시점엔 알 수 없다.
그래서 assess_sensor_health 가 조회 시각 기준으로 판정한다.

- 측정 이력 없음              → MISSING (no_readings)
- 최신 행이 누락 마커          → MISSING (sequence_gap)
- 가상 시각 기준 경과 초과      → STALE   (stale_simulation_time)
- run 이 RUNNING 인데 적재 끊김 → STALE   (stale_ingest_timeout)
- 그 외                        → 최신 행의 저장 품질
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.enums import ReadingQuality, SensorType

QUALITY_REASON_MAX_LENGTH = 128  # sensor_readings.quality_reason 컬럼 길이


class QualityReason(StrEnum):
    """Day 21 품질 사유 코드. 범위 사유(Day 20)는 normalize.py 에 있다."""

    SEQUENCE_GAP = "sequence_gap"
    SEQUENCE_DUPLICATE = "sequence_duplicate"
    SEQUENCE_OUT_OF_ORDER = "sequence_out_of_order"
    TIME_REVERSED = "time_reversed"
    FLATLINE = "flatline_detected"
    RATE_OF_CHANGE = "rate_of_change_exceeded"
    INGEST_LATENCY = "ingest_latency_exceeded"
    NO_READINGS = "no_readings"
    STALE_SIMULATION = "stale_simulation_time"
    STALE_INGEST = "stale_ingest_timeout"


# ---------------------------------------------------------------------------
# sequence
# ---------------------------------------------------------------------------


class SequenceStatus(StrEnum):
    FIRST = "first"
    OK = "ok"
    GAP = "gap"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


@dataclass(frozen=True)
class SequenceCheck:
    status: SequenceStatus
    missing_count: int = 0

    @property
    def accepted(self) -> bool:
        return self.status in (SequenceStatus.FIRST, SequenceStatus.OK, SequenceStatus.GAP)


def check_sequence(last: int | None, incoming: int) -> SequenceCheck:
    """
    센서 스트림의 직전 sequence 와 새 sequence 를 비교한다.

    GAP 이면 missing_count = 건너뛴 번호 개수.
    """
    if incoming < 0:
        raise ValueError("sequence must be >= 0")
    if last is None:
        return SequenceCheck(SequenceStatus.FIRST)
    if incoming == last:
        return SequenceCheck(SequenceStatus.DUPLICATE)
    if incoming < last:
        return SequenceCheck(SequenceStatus.OUT_OF_ORDER)
    if incoming == last + 1:
        return SequenceCheck(SequenceStatus.OK)
    return SequenceCheck(SequenceStatus.GAP, missing_count=incoming - last - 1)


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimit:
    """
    허용 변화량 = deadband + per_second · dt.

    deadband 가 없으면 dt 가 짧은 ingest 에서 센서 노이즈만으로 SUSPECT 가 난다.
    """

    per_second: float
    deadband: float

    def allowed_delta(self, dt_seconds: float) -> float:
        return self.deadband + self.per_second * max(dt_seconds, 0.0)


# 엽면습윤(건조 시 0으로 리셋)·관수 유량(밸브 on/off)은 계단 변화가 정상이라 제외.
DEFAULT_RATE_LIMITS: dict[SensorType, RateLimit] = {
    SensorType.TEMPERATURE: RateLimit(per_second=0.05, deadband=0.5),
    SensorType.HUMIDITY: RateLimit(per_second=0.25, deadband=3.0),
    SensorType.CO2: RateLimit(per_second=5.0, deadband=30.0),
    SensorType.SUBSTRATE_MOISTURE: RateLimit(per_second=0.1, deadband=3.0),
    SensorType.PPFD: RateLimit(per_second=40.0, deadband=100.0),
    SensorType.SUBSTRATE_EC: RateLimit(per_second=0.02, deadband=0.3),
    SensorType.SUBSTRATE_TEMPERATURE: RateLimit(per_second=0.05, deadband=0.5),
    SensorType.NUTRIENT_PH: RateLimit(per_second=0.01, deadband=0.2),
}

# 아날로그 잡음이 항상 있는 센서만 원시값 고정(stuck)을 본다.
# PPFD 는 야간에 실측 0 이 반복되는 게 정상이라 제외한다.
DEFAULT_FLATLINE_SENSOR_TYPES: frozenset[SensorType] = frozenset(
    {
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.CO2,
        SensorType.SUBSTRATE_MOISTURE,
    }
)


@dataclass(frozen=True)
class QualityConfig:
    rate_limits: Mapping[SensorType, RateLimit] = field(
        default_factory=lambda: dict(DEFAULT_RATE_LIMITS)
    )
    flatline_sensor_types: frozenset[SensorType] = DEFAULT_FLATLINE_SENSOR_TYPES
    # 같은 raw 가 이 개수만큼 연속되면 BAD
    flatline_samples: int = 4
    max_ingest_latency_s: float = 30.0
    expected_period_s: float = 60.0
    stale_after_periods: float = 3.0
    stale_ingest_wall_s: float = 60.0
    # 긴 끊김 뒤 한 번에 수천 행이 생기지 않도록 상한
    max_missing_markers: int = 60

    @property
    def stale_after_simulation_s(self) -> float:
        return self.expected_period_s * self.stale_after_periods


DEFAULT_QUALITY_CONFIG = QualityConfig()


# ---------------------------------------------------------------------------
# reading 한 건 판정
# ---------------------------------------------------------------------------

_SEVERITY: dict[ReadingQuality, int] = {
    ReadingQuality.GOOD: 0,
    ReadingQuality.SUSPECT: 1,
    ReadingQuality.STALE: 2,
    ReadingQuality.MISSING: 3,
    ReadingQuality.BAD: 4,
}


def worse_quality(a: ReadingQuality, b: ReadingQuality) -> ReadingQuality:
    return a if _SEVERITY[a] >= _SEVERITY[b] else b


def join_reasons(reasons: tuple[str, ...]) -> str | None:
    if not reasons:
        return None
    return ";".join(reasons)[:QUALITY_REASON_MAX_LENGTH]


@dataclass(frozen=True)
class QualityVerdict:
    quality: ReadingQuality
    reasons: tuple[str, ...] = ()

    @property
    def reason_text(self) -> str | None:
        return join_reasons(self.reasons)


@dataclass(frozen=True)
class StreamState:
    """
    센서 스트림 하나의 수신측 기준 상태.

    last_value / last_simulation_time 은 마지막 **사용 가능한** 값이다.
    BAD(시간 역전·고정) 행은 기준으로 삼지 않는다.
    last_raw / flat_run 은 BAD 여부와 무관하게 직전 원시값과 그 연속 횟수다.
    """

    last_sequence: int | None = None
    last_value: float | None = None
    last_simulation_time: float | None = None
    last_raw: float | None = None
    flat_run: int = 0


def flatline_run(state: StreamState, raw_value: float) -> int:
    """이번 raw 를 포함한 같은 원시값 연속 횟수."""
    if state.last_raw is not None and raw_value == state.last_raw:
        return state.flat_run + 1
    return 1


def classify_stream_reading(
    *,
    sensor_type: SensorType,
    value: float,
    simulation_time: float,
    base_quality: ReadingQuality,
    base_reason: str | None,
    state: StreamState,
    raw_value: float | None = None,
    sampled_at: datetime | None = None,
    ingested_at: datetime | None = None,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> QualityVerdict:
    """
    Day 20 범위 판정 결과(base_*)에 스트림 검사를 더한다.

    sequence 검사는 여기서 하지 않는다 — 거부/마커 생성이 걸려 있어
    StreamQualityAssessor.assess 가 먼저 처리한다.
    """
    quality = base_quality
    reasons: list[str] = [base_reason] if base_reason else []

    if (
        raw_value is not None
        and sensor_type in config.flatline_sensor_types
        and flatline_run(state, raw_value) >= config.flatline_samples
    ):
        quality = worse_quality(quality, ReadingQuality.BAD)
        reasons.append(QualityReason.FLATLINE.value)

    last_t = state.last_simulation_time
    if last_t is not None and simulation_time < last_t:
        quality = worse_quality(quality, ReadingQuality.BAD)
        reasons.append(QualityReason.TIME_REVERSED.value)
    elif state.last_value is not None and last_t is not None:
        limit = config.rate_limits.get(sensor_type)
        if limit is not None:
            delta = abs(value - state.last_value)
            if delta > limit.allowed_delta(simulation_time - last_t):
                quality = worse_quality(quality, ReadingQuality.SUSPECT)
                reasons.append(QualityReason.RATE_OF_CHANGE.value)

    if sampled_at is not None and ingested_at is not None:
        latency = (ingested_at - sampled_at).total_seconds()
        if latency > config.max_ingest_latency_s:
            quality = worse_quality(quality, ReadingQuality.SUSPECT)
            reasons.append(QualityReason.INGEST_LATENCY.value)

    return QualityVerdict(quality=quality, reasons=tuple(reasons))


# ---------------------------------------------------------------------------
# 스트림 판정기 (수신측 상태 보유)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissingMarker:
    """누락된 sequence 한 칸. value 없이 quality=MISSING 으로 저장된다."""

    source_sequence: int
    simulation_time: float
    reason: str = QualityReason.SEQUENCE_GAP.value


@dataclass(frozen=True)
class StreamAssessment:
    sequence: SequenceCheck
    verdict: QualityVerdict | None
    missing_markers: tuple[MissingMarker, ...] = ()
    # max_missing_markers 를 넘어 마커를 만들지 않은 개수
    missing_truncated: int = 0
    reject_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.verdict is not None


def _missing_markers(
    *,
    last_sequence: int,
    incoming_sequence: int,
    last_simulation_time: float | None,
    simulation_time: float,
    limit: int,
) -> tuple[tuple[MissingMarker, ...], int]:
    """
    빈 sequence 마다 마커를 만든다.

    simulation_time 은 앞뒤 수신 시각 사이를 sequence 위치로 선형 보간한다.
    """
    missing = incoming_sequence - last_sequence - 1
    start_t = last_simulation_time if last_simulation_time is not None else simulation_time
    span = incoming_sequence - last_sequence
    markers: list[MissingMarker] = []
    for offset in range(1, min(missing, limit) + 1):
        fraction = offset / span
        markers.append(
            MissingMarker(
                source_sequence=last_sequence + offset,
                simulation_time=start_t + (simulation_time - start_t) * fraction,
            )
        )
    return tuple(markers), max(missing - limit, 0)


class StreamQualityAssessor:
    """
    센서 스트림별 상태를 들고 reading 을 한 건씩 판정한다.

    key 는 스트림 식별자(보통 sensor_id). 호출자가 DB 에서 복원한
    초기 상태를 넘기면 HTTP 호출을 나눠도 판정이 이어진다.
    """

    def __init__(
        self,
        config: QualityConfig = DEFAULT_QUALITY_CONFIG,
        states: Mapping[Hashable, StreamState] | None = None,
    ) -> None:
        self.config = config
        self._states: dict[Hashable, StreamState] = dict(states or {})

    def state_for(self, key: Hashable) -> StreamState:
        return self._states.get(key, StreamState())

    def next_sequence(self, key: Hashable) -> int:
        """수신측이 마지막으로 받은 sequence 다음 번호."""
        last = self.state_for(key).last_sequence
        return 0 if last is None else last + 1

    def assess(
        self,
        key: Hashable,
        *,
        sensor_type: SensorType,
        source_sequence: int,
        value: float,
        simulation_time: float,
        base_quality: ReadingQuality = ReadingQuality.GOOD,
        base_reason: str | None = None,
        raw_value: float | None = None,
        sampled_at: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> StreamAssessment:
        state = self.state_for(key)
        seq = check_sequence(state.last_sequence, source_sequence)

        if seq.status is SequenceStatus.DUPLICATE:
            return StreamAssessment(
                sequence=seq,
                verdict=None,
                reject_reason=QualityReason.SEQUENCE_DUPLICATE.value,
            )
        if seq.status is SequenceStatus.OUT_OF_ORDER:
            return StreamAssessment(
                sequence=seq,
                verdict=None,
                reject_reason=QualityReason.SEQUENCE_OUT_OF_ORDER.value,
            )

        markers: tuple[MissingMarker, ...] = ()
        truncated = 0
        if seq.status is SequenceStatus.GAP and state.last_sequence is not None:
            markers, truncated = _missing_markers(
                last_sequence=state.last_sequence,
                incoming_sequence=source_sequence,
                last_simulation_time=state.last_simulation_time,
                simulation_time=simulation_time,
                limit=self.config.max_missing_markers,
            )

        verdict = classify_stream_reading(
            sensor_type=sensor_type,
            value=value,
            simulation_time=simulation_time,
            base_quality=base_quality,
            base_reason=base_reason,
            state=state,
            raw_value=raw_value,
            sampled_at=sampled_at,
            ingested_at=ingested_at,
            config=self.config,
        )
        if seq.status is SequenceStatus.GAP:
            verdict = QualityVerdict(
                quality=verdict.quality,
                reasons=(*verdict.reasons, QualityReason.SEQUENCE_GAP.value),
            )

        usable = verdict.quality is not ReadingQuality.BAD
        self._states[key] = StreamState(
            last_sequence=source_sequence,
            last_value=value if usable else state.last_value,
            last_simulation_time=simulation_time if usable else state.last_simulation_time,
            last_raw=raw_value if raw_value is not None else state.last_raw,
            flat_run=(
                flatline_run(state, raw_value) if raw_value is not None else state.flat_run
            ),
        )
        return StreamAssessment(
            sequence=seq,
            verdict=verdict,
            missing_markers=markers,
            missing_truncated=truncated,
        )


# ---------------------------------------------------------------------------
# 조회 시점 판정 (stale / missing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestReadingView:
    quality: ReadingQuality
    quality_reason: str | None
    simulation_time: float
    ingested_at: datetime


@dataclass(frozen=True)
class SensorHealthVerdict:
    quality: ReadingQuality
    reason: str | None
    age_simulation_s: float | None = None
    age_wall_s: float | None = None


def assess_sensor_health(
    latest: LatestReadingView | None,
    *,
    current_simulation_time: float | None,
    now: datetime,
    run_running: bool,
    config: QualityConfig = DEFAULT_QUALITY_CONFIG,
) -> SensorHealthVerdict:
    """센서의 현재 품질. 최신 행 품질에 조회 시각 기준 stale/missing 을 덧씌운다."""
    if latest is None:
        return SensorHealthVerdict(ReadingQuality.MISSING, QualityReason.NO_READINGS.value)

    age_sim = (
        max(current_simulation_time - latest.simulation_time, 0.0)
        if current_simulation_time is not None
        else None
    )
    age_wall = max((now - latest.ingested_at).total_seconds(), 0.0)

    def verdict(quality: ReadingQuality, reason: str | None) -> SensorHealthVerdict:
        return SensorHealthVerdict(quality, reason, age_sim, age_wall)

    if latest.quality is ReadingQuality.MISSING:
        return verdict(
            ReadingQuality.MISSING,
            latest.quality_reason or QualityReason.SEQUENCE_GAP.value,
        )
    if age_sim is not None and age_sim > config.stale_after_simulation_s:
        return verdict(ReadingQuality.STALE, QualityReason.STALE_SIMULATION.value)
    if run_running and age_wall > config.stale_ingest_wall_s:
        return verdict(ReadingQuality.STALE, QualityReason.STALE_INGEST.value)
    return verdict(latest.quality, latest.quality_reason)
