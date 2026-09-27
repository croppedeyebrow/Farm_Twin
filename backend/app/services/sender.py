"""
시뮬 송신측 센서별 source_sequence (6단계 Day 22, Day 23 체크포인트).

dropout 중에도 번호는 진행하지만 저장되는 행이 없어 DB 만으로는 복원할 수 없다.
그래서 프로세스 메모리에 커서를 두고, 수신측 상태(DB 복원)가 커서를 만든
시점과 같을 때만 이어 쓴다. 재시작·재시드로 어긋나면 수신측 기준으로 돌아간다
(그 경우 복구 시 누락 마커가 생기지 않을 뿐 stale 판정은 유지된다).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.telemetry import StreamQualityAssessor


@dataclass
class _SenderCursor:
    issued: int
    # 발급 시점에 수신측이 마지막으로 받은 번호 — DB 와 어긋나면 커서를 버린다
    received: int | None


class SenderSequences:
    def __init__(self) -> None:
        self._cursors: dict[tuple[uuid.UUID, uuid.UUID], _SenderCursor] = {}

    def clear(self) -> None:
        self._cursors.clear()

    def issue(
        self,
        run_id: uuid.UUID,
        sensor_id: uuid.UUID,
        assessor: StreamQualityAssessor,
    ) -> int:
        received = assessor.state_for(sensor_id).last_sequence
        cursor = self._cursors.get((run_id, sensor_id))
        sequence = assessor.next_sequence(sensor_id)
        if cursor is not None and cursor.received == received:
            sequence = max(sequence, cursor.issued + 1)
        self._cursors[(run_id, sensor_id)] = _SenderCursor(issued=sequence, received=received)
        return sequence

    def delivered(self, run_id: uuid.UUID, sensor_id: uuid.UUID, sequence: int) -> None:
        self._cursors[(run_id, sensor_id)] = _SenderCursor(issued=sequence, received=sequence)

    def last_issued(
        self,
        run_id: uuid.UUID,
        sensor_id: uuid.UUID,
        received: int | None,
    ) -> int | None:
        """체크포인트용 — dropout 으로 전달 못 한 번호까지 포함한 마지막 발급 번호."""
        cursor = self._cursors.get((run_id, sensor_id))
        if cursor is None or cursor.received != received:
            return received
        return cursor.issued

    def seed(
        self,
        run_id: uuid.UUID,
        sensor_id: uuid.UUID,
        *,
        issued: int,
        received: int | None,
    ) -> None:
        """재생 run 첫 스텝 — 원본 체크포인트의 송신 커서를 이어 받는다."""
        self._cursors[(run_id, sensor_id)] = _SenderCursor(issued=issued, received=received)


SENDER_SEQUENCES = SenderSequences()
