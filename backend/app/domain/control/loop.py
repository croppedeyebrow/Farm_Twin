"""
폐쇄 제어 루프 러너 (4단계 Day 15).

=============================================================================
목표
-----------------------------------------------------------------------------
UI/DB 없이 순수 도메인만으로

  환경 참값 → 관측 → 규칙 → 게이트 → 명령 → 액추에이터 → (다음) 환경

이 닫힌 사이클을 돌리고, 자동 테스트로
  "온도 올랐다 → 냉방 → 온도 내려갔다 → 정지"
를 증명한다.

=============================================================================
한 스텝(step) 순서
-----------------------------------------------------------------------------
1. 현재 설비 스냅샷 → ActuatorInputs
2. outdoor + actuators + dt → step_environment (참값 갱신)
3. 참값 → MetricReading (MVP: noise/delay 없음 — 인과만 증명)
4. evaluate_ruleset (우선순위·히스테리시스 → START/STOP/HOLD/SKIP)
5. gate_decision (min-on / cooldown / MANUAL)
6. START/STOP 만 execute_decision → Command+Event, actuators 갱신
7. LoopStepRecord 로 history 적재 (감사/테스트용)

다음 step 의 ActuatorInputs 가 이번 적용 결과를 쓰므로
피드백이 환경 모델에 다시 들어간다 = 폐쇄 루프.

왜 true-value reading 인가
--------------------------
Day 10 가상 센서(offset/noise/delay)를 넣으면 테스트가
"센서 노이즈 때문에 실패"와 "루프 버그"를 구별하기 어렵다.
Day 15 는 **제어 인과** 증명에 초점을 맞춘다.
센서 품질·지연은 Day 12 quality 정책과 Day 10 센서 테스트가 따로 담는다.

outdoor 은 러너 밖(테스트)에서 바꿔도 된다
------------------------------------------
예) 고온 외기로 START 유도 → START 후 외기를 낮춰 STOP 이 가능하도록.
ClosedLoopRunner.outdoor 필드를 갱신하면 다음 step 부터 반영된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.control.actuators import ActuatorSnapshot
from app.domain.control.commands import CommandApplication, execute_decision
from app.domain.control.evaluate import (
    MetricReading,
    RuleDecision,
    RuleIntent,
    evaluate_ruleset,
)
from app.domain.control.gates import ControlRuntime, gate_decision
from app.domain.control.schema import RuleDefinition, RuleSet
from app.domain.enums import ActuatorMode, ActuatorType, ReadingQuality, SensorType
from app.domain.simulation.environment import step_environment
from app.domain.simulation.params import DEFAULT_ENV_PARAMS, EnvironmentModelParams
from app.domain.simulation.state import (
    ActuatorInputs,
    EnvironmentState,
    OutdoorCondition,
)


def _readings_from_true_state(state: EnvironmentState) -> dict[SensorType, MetricReading]:
    """
    환경 참값 → GOOD MetricReading.

    폐쇄 루프 인과 증명용. 노이즈·지연·오프셋 없음.
    """
    return {
        SensorType.TEMPERATURE: MetricReading(
            SensorType.TEMPERATURE, state.temperature_c, ReadingQuality.GOOD
        ),
        SensorType.HUMIDITY: MetricReading(
            SensorType.HUMIDITY, state.humidity_pct, ReadingQuality.GOOD
        ),
        SensorType.CO2: MetricReading(
            SensorType.CO2, state.co2_ppm, ReadingQuality.GOOD
        ),
        SensorType.SUBSTRATE_MOISTURE: MetricReading(
            SensorType.SUBSTRATE_MOISTURE,
            state.substrate_moisture_pct,
            ReadingQuality.GOOD,
        ),
        SensorType.PPFD: MetricReading(
            SensorType.PPFD, state.ppfd_umol, ReadingQuality.GOOD
        ),
    }


def _actuators_to_inputs(
    actuators: dict[ActuatorType, ActuatorSnapshot],
) -> ActuatorInputs:
    """스냅샷 dict → 환경 모델이 받는 입력 벡터."""

    def ratio(actuator_type: ActuatorType) -> float:
        snap = actuators.get(actuator_type)
        if snap is None or snap.mode is ActuatorMode.OFF:
            return 0.0
        return snap.output_ratio

    return ActuatorInputs(
        hvac=ratio(ActuatorType.HVAC),
        ventilation_fan=ratio(ActuatorType.VENTILATION_FAN),
        dehumidifier=ratio(ActuatorType.DEHUMIDIFIER),
        irrigation_pump=ratio(ActuatorType.IRRIGATION_PUMP),
        led=ratio(ActuatorType.LED),
    )


def _active_types(
    actuators: dict[ActuatorType, ActuatorSnapshot],
) -> set[ActuatorType]:
    """히스테리시스용: 현재 ON 인 설비 집합."""
    return {
        actuator_type
        for actuator_type, snap in actuators.items()
        if snap.is_active
    }


def _rule_by_name(
    rule_set: RuleSet,
    name: str,
) -> RuleDefinition | None:
    for rule in rule_set.rules:
        if rule.name == name:
            return rule
    return None


@dataclass
class LoopStepRecord:
    """
    한 스텝의 감사 요약.

    테스트는 history 를 훑어 START/STOP 시점과 온도·수분 추이를 검증한다.
    """

    simulation_time: float
    temperature_c: float
    substrate_moisture_pct: float
    decisions: tuple[RuleDecision, ...]
    applications: tuple[CommandApplication, ...]
    hvac_active: bool
    irrigation_active: bool


@dataclass
class ClosedLoopRunner:
    """
    순수 도메인 폐쇄 루프.

    - rule_set / state / outdoor / actuators / runtime 을 한 인스턴스에 유지
    - step() 마다 위 순서로 갱신
    - DB·HTTP·시뮬레이터 프로세스와 무관 (단위 테스트에서 직접 사용)
    """

    rule_set: RuleSet
    state: EnvironmentState
    outdoor: OutdoorCondition
    actuators: dict[ActuatorType, ActuatorSnapshot] = field(default_factory=dict)
    runtime: ControlRuntime = field(default_factory=ControlRuntime)
    params: EnvironmentModelParams = field(default_factory=lambda: DEFAULT_ENV_PARAMS)
    run_key: str = "closed-loop"
    history: list[LoopStepRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        # 누락된 설비는 OFF 로 채워 ActuatorInputs 가 항상 완전하도록 한다.
        for actuator_type in ActuatorType:
            if actuator_type not in self.actuators:
                self.actuators[actuator_type] = ActuatorSnapshot(
                    actuator_type=actuator_type,
                    mode=ActuatorMode.OFF,
                    output_ratio=0.0,
                    code=actuator_type.value,
                )

    def step(self, *, dt_seconds: float) -> LoopStepRecord:
        """
        폐쇄 루프 한 스텝.

        주의: execute_decision 에 이미 게이트된 decision 을 넘기면
        게이트가 한 번 더 돌아가지만 idempotent 하다 (같은 강등 결과).
        """
        # 1~2. 설비 → 환경 전이
        inputs = _actuators_to_inputs(self.actuators)
        outdoor = OutdoorCondition(
            temperature_c=self.outdoor.temperature_c,
            humidity_pct=self.outdoor.humidity_pct,
            simulation_time=self.state.simulation_time + dt_seconds,
            source=self.outdoor.source,
            co2_ppm=self.outdoor.co2_ppm,
        )
        self.state = step_environment(
            self.state,
            outdoor=outdoor,
            actuators=inputs,
            dt_seconds=dt_seconds,
            params=self.params,
        )

        # 3~4. 관측 → 규칙 평가
        readings = _readings_from_true_state(self.state)
        raw_decisions = evaluate_ruleset(
            self.rule_set,
            readings=readings,
            active_actuators=_active_types(self.actuators),
        )

        # 5~6. 게이트 → (START/STOP 만) 명령 적용
        gated: list[RuleDecision] = []
        applications: list[CommandApplication] = []
        for decision in raw_decisions:
            rule = _rule_by_name(self.rule_set, decision.rule_name)
            if rule is None:
                continue
            gated_decision = gate_decision(
                decision,
                rule,
                runtime=self.runtime,
                simulation_time=self.state.simulation_time,
            )
            gated.append(gated_decision)
            if gated_decision.intent in (RuleIntent.START, RuleIntent.STOP):
                current = self.actuators[gated_decision.target_actuator_type]
                app = execute_decision(
                    gated_decision,
                    current,
                    simulation_time=self.state.simulation_time,
                    run_key=self.run_key,
                    rule=rule,
                    runtime=self.runtime,
                )
                if app is not None:
                    self.actuators[app.actuator_after.actuator_type] = app.actuator_after
                    applications.append(app)

        # 7. 감사 기록
        record = LoopStepRecord(
            simulation_time=self.state.simulation_time,
            temperature_c=self.state.temperature_c,
            substrate_moisture_pct=self.state.substrate_moisture_pct,
            decisions=tuple(gated),
            applications=tuple(applications),
            hvac_active=self.actuators[ActuatorType.HVAC].is_active,
            irrigation_active=self.actuators[ActuatorType.IRRIGATION_PUMP].is_active,
        )
        self.history.append(record)
        return record

    def run(self, *, steps: int, dt_seconds: float) -> list[LoopStepRecord]:
        """N 스텝 연속 실행. 반환값은 history 에 추가된 구간과 동일."""
        return [self.step(dt_seconds=dt_seconds) for _ in range(steps)]
