/**
 * 3D 트윈 · 장치 제어 페이지.
 */

import { ControlPanel } from '../components/ControlPanel'
import { CropTunePanel } from '../components/CropTunePanel'
import { GrowingRoomScene } from '../scene/GrowingRoomScene'
import { useRealtimeStore } from '../store/realtimeStore'

export function TwinControlPage() {
  const state = useRealtimeStore((s) => s.state)
  const actuators = useRealtimeStore((s) => s.actuators)
  const selectedActuatorId = useRealtimeStore((s) => s.selectedActuatorId)
  const selectActuator = useRealtimeStore((s) => s.selectActuator)

  return (
    <main className="page page-twin" aria-label="3D 트윈 제어">
      <section className="twin-pane" aria-label="3D 디지털 트윈">
        <div className="viewport" data-testid="farm-3d-viewport">
          <GrowingRoomScene />
          <CropTunePanel />
        </div>
        <header className="twin-chrome">
          <p className="twin-chrome-title">3D 트윈</p>
          <p className="twin-chrome-sub">라인·작물·설비 관찰 · 수동 제어</p>
        </header>
      </section>

      <aside className="twin-side" aria-label="장치 제어">
        <header className="page-header page-header-compact">
          <div>
            <h1>장치 제어</h1>
            <p className="lede">LED·입구 문 등 트윈에 즉시 반영됩니다.</p>
          </div>
        </header>
        <div className="page-stack">
          <ControlPanel
            actuators={actuators}
            state={state}
            selectedActuatorId={selectedActuatorId}
            onSelectActuator={selectActuator}
          />
        </div>
      </aside>
    </main>
  )
}
