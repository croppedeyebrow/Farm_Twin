/**
 * 트윈 운영 제어 — 설비 수동 출력 + 입구 문 개폐.
 */

import { ActuatorManualPanel } from './ActuatorManualPanel'
import type { ActuatorSummary, FarmStateSnapshot } from '../api/farms'
import { useTwinOpsStore } from '../store/twinOpsStore'

type Props = {
  actuators: ActuatorSummary[]
  state: FarmStateSnapshot | null
  selectedActuatorId: string | null
  onSelectActuator: (id: string | null) => void
}

export function ControlPanel({
  actuators,
  state,
  selectedActuatorId,
  onSelectActuator,
}: Props) {
  const doorOpen = useTwinOpsStore((s) => s.doorOpen)
  const setDoorOpen = useTwinOpsStore((s) => s.setDoorOpen)
  const toggleDoor = useTwinOpsStore((s) => s.toggleDoor)

  return (
    <section className="control-panel" aria-label="환경 제어">
      <div className="panel-title-row">
        <h2>제어</h2>
      </div>

      <ActuatorManualPanel
        actuators={actuators}
        state={state}
        selectedActuatorId={selectedActuatorId}
        onSelectActuator={onSelectActuator}
        compactList
      />

      <div className="control-door">
        <div className="control-led-head">
          <strong>입구 문</strong>
          <em data-on={doorOpen > 0.5 ? 'true' : 'false'}>
            {doorOpen > 0.5 ? '열림' : '닫힘'}
          </em>
        </div>
        <label className="control-slider-row">
          <span>
            개도
            <em>{Math.round(doorOpen * 100)}%</em>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(doorOpen * 100)}
            onChange={(event) => setDoorOpen(Number(event.target.value) / 100)}
          />
        </label>
        <div className="control-actions">
          <button
            type="button"
            className="control-on"
            disabled={doorOpen >= 0.99}
            onClick={() => setDoorOpen(1)}
          >
            열기
          </button>
          <button
            type="button"
            className="control-off"
            disabled={doorOpen <= 0.01}
            onClick={() => setDoorOpen(0)}
          >
            닫기
          </button>
          <button type="button" className="control-apply" onClick={toggleDoor}>
            토글
          </button>
        </div>
        <p className="control-hint">
          문 개폐는 트윈 로컬입니다. 천창·측창(vent_motor)은 API 수동 제어로
          외기 혼합에 반영됩니다.
        </p>
      </div>
    </section>
  )
}
