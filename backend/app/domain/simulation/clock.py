"""
SimulationClock (3단계 Day 8).

=============================================================================
개념
-----------------------------------------------------------------------------
가상 시계(simulation_time)는 wall-clock(실제 벽시계)과 독립이다.

  - 상태전이·센서 샘플·규칙 판정은 **전부** 이 시계를 기준으로 한다.
  - 배속 데모: step_seconds=1, speed_multiplier=60 → advance 한 번에 60초 가상시간.
  - pause: advance 가 시각을 올리지 않음 → dt=0 → 환경 상태 동결에 연결 가능.

재현성
------
동일 seed + 동일 advance 호출 횟수/인자 → 동일 now_seconds.
(seed 자체는 Day 8 시계에선 위상·추후 RNG 스트림 키로 쓰이고,
 시각 진행식에는 직접 들어가지 않는다.)

상태전이와의 연결
----------------
runner 의사코드:
    prev = clock.now_seconds
    now = clock.advance()
    dt = now - prev
    state = step_environment(state, outdoor, actuators, dt_seconds=dt)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationClock:
    """
    단조 증가하는 가상 시계.

    mutable: 시뮬레이션 루프가 같은 인스턴스를 전진시킨다.
    (EnvironmentState 는 불변 스냅샷, Clock 은 루프 커서)
    """

    seed: int
    # 한 번 advance 할 때 기본으로 더할 초 (배율 적용 전)
    step_seconds: float = 1.0
    # 배속. 실제 Δt = step_seconds * speed_multiplier
    speed_multiplier: float = 1.0
    now_seconds: float = 0.0
    paused: bool = False
    # advance 가 실제로 시각을 올린 횟수 (pause 중 호출은 안 셈)
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

            Δt = step_seconds × speed_multiplier
            now ← now + Δt   (paused 이면 변경 없음)

        예: step=1, speed=60 → 호출당 가상 60초 (1분 데모 가속).
        """
        if self.paused:
            return self.now_seconds
        delta = self.step_seconds * self.speed_multiplier
        self.now_seconds += delta
        self.step_count += 1
        return self.now_seconds

    def pause(self) -> None:
        """가상 시간 정지. 이후 advance 는 no-op."""
        self.paused = True

    def resume(self) -> None:
        """정지 해제."""
        self.paused = False

    def reset(self, *, now_seconds: float = 0.0) -> None:
        """시각·스텝 카운터 초기화. seed 는 실험 식별용으로 유지."""
        if now_seconds < 0:
            raise ValueError("now_seconds must be >= 0")
        self.now_seconds = now_seconds
        self.step_count = 0
        self.paused = False
