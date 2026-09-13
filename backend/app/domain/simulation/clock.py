"""
SimulationClock (3단계 Day 8).

가상 시계는 wall-clock 과 독립이다.
- now_seconds: 현재 시뮬레이션 시각(초)
- step_seconds: 한 스텝 진행량
- speed_multiplier: 배속 (1.0 = 실시간 비율 개념, 스텝 크기와 별개로 기록)

재현성: 동일 seed + 동일 step 수 → 동일 now_seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationClock:
    """
    단조 증가하는 가상 시계.

    pause 되면 advance() 가 시각을 올리지 않는다.
    """

    seed: int
    step_seconds: float = 1.0
    speed_multiplier: float = 1.0
    now_seconds: float = 0.0
    paused: bool = False
    step_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.step_seconds <= 0:
            raise ValueError("step_seconds must be > 0")
        if self.speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be > 0")
        if self.now_seconds < 0:
            raise ValueError("now_seconds must be >= 0")

    def advance(self) -> float:
        """
        한 스텝 진행하고 새 now_seconds 를 반환한다.

        실제 진행량 = step_seconds * speed_multiplier
        (예: step=1, speed=60 → 한 호출에 60초 가상 시간)
        """
        if self.paused:
            return self.now_seconds
        delta = self.step_seconds * self.speed_multiplier
        self.now_seconds += delta
        self.step_count += 1
        return self.now_seconds

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def reset(self, *, now_seconds: float = 0.0) -> None:
        """시각·스텝 카운터를 초기화한다. seed 는 유지."""
        if now_seconds < 0:
            raise ValueError("now_seconds must be >= 0")
        self.now_seconds = now_seconds
        self.step_count = 0
        self.paused = False
