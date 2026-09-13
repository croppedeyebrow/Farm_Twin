"""
제어 규칙 도메인 패키지 (4단계 Day 12~15).

=============================================================================
한눈에 보는 흐름
-----------------------------------------------------------------------------
  MetricReading + RuleSet
        │
        ▼
  evaluate.py     → RuleDecision (START/STOP/HOLD/SKIP)
        │             · schema version, comparator, priority
        │             · quality policy (good/suspect/bad/…)
        ▼
  gates.py        → 강등된 RuleDecision
        │             · min_on / cooldown / AUTO|MANUAL
        ▼
  commands.py     → CommandDraft ≠ EventDraft
        │             · idempotency
        ▼
  actuators.py    → ActuatorSnapshot 갱신
        │
        ▼
  loop.py         → step_environment 로 피드백 (Day 15 폐쇄 루프)

ORM ControlRule/Command/Event 는 이 도메인의 영속 투영이다.
시뮬레이터·테스트는 여기 순수 함수만으로 루프를 증명할 수 있다.
"""
