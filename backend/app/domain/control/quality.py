"""
규칙 판정용 측정 품질 정책 (4단계 Day 12).

=============================================================================
왜 필요한가
-----------------------------------------------------------------------------
폐쇄 루프는 센서 **측정값**으로 규칙을 판정한다.
품질이 bad/missing/stale 인 값으로 HVAC 를 켜면
고장·통신 장애가 제어 사고로 이어진다.

정책 (MVP 기본)
---------------
| quality | QualityAction | 의미 |
|---------|---------------|------|
| good    | USE           | 값으로 START/STOP 조건 평가 |
| suspect | HOLD          | 이번 스텝 결정 보류(설비 상태 유지) |
| bad     | REJECT → SKIP | 사용 불가, 명령 없음 |
| missing | REJECT → SKIP | 기대 샘플 없음 |
| stale   | REJECT → SKIP | 허용 지연 초과 |

HOLD vs REJECT
--------------
- HOLD: "모르겠다, 건드리지 마" (이미 켠 냉방을 갑자기 끄지 않음)
- REJECT/SKIP: "이 측정으로는 새 명령을 내지 마"

QualityPolicy 는 주입 가능 — 시나리오마다 suspect 를 USE 로 바꿀 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import ReadingQuality


class QualityAction(StrEnum):
    """측정 품질에 대한 규칙 엔진 행동."""

    USE = "use"
    HOLD = "hold"
    REJECT = "reject"


@dataclass(frozen=True)
class QualityPolicy:
    """ReadingQuality → QualityAction 매핑 (보수적 기본값)."""

    good: QualityAction = QualityAction.USE
    suspect: QualityAction = QualityAction.HOLD
    bad: QualityAction = QualityAction.REJECT
    missing: QualityAction = QualityAction.REJECT
    stale: QualityAction = QualityAction.REJECT

    def action_for(self, quality: ReadingQuality) -> QualityAction:
        """품질 태그 하나에 대한 엔진 행동."""
        return {
            ReadingQuality.GOOD: self.good,
            ReadingQuality.SUSPECT: self.suspect,
            ReadingQuality.BAD: self.bad,
            ReadingQuality.MISSING: self.missing,
            ReadingQuality.STALE: self.stale,
        }[quality]


DEFAULT_QUALITY_POLICY = QualityPolicy()
