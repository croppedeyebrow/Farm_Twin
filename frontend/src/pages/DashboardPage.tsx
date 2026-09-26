/**
 * 환경 관제 — FarmTwin / OPERATIONS
 *
 * 목적: 룸 KPI + 작물 구역(딸기/포도) + 이벤트·운전 기준을 한 화면에.
 * 구역 패널은 setpoint·관수·병해·LED/DLI 요구를 룸과 분리해 보여 준다.
 */

import { OpsDeviceStatus } from '../components/ops/OpsDeviceStatus'
import {
  OpsEventFeed,
  OpsSafetyRules,
} from '../components/ops/OpsEventFeed'
import { OpsMetricCards } from '../components/ops/OpsMetricCards'
import { OpsPageChrome } from '../components/ops/OpsPageChrome'
import { OpsTrendChart } from '../components/ops/OpsTrendChart'
import { OpsZonePanel } from '../components/ops/OpsZonePanel'
import { currentScenario, useOpsUiStore } from '../store/opsUiStore'
import { useRealtimeStore } from '../store/realtimeStore'

export function DashboardPage() {
  const state = useRealtimeStore((s) => s.state)
  const zones = useRealtimeStore((s) => s.zones)
  const stale = useRealtimeStore((s) => s.stale)
  const kpiHistory = useRealtimeStore((s) => s.kpiHistory)
  const actuators = useRealtimeStore((s) => s.actuators)
  const timeline = useRealtimeStore((s) => s.timeline)

  const scenarioId = useOpsUiStore((s) => s.scenarioId)
  const chartWindow = useOpsUiStore((s) => s.chartWindow)
  const setChartWindow = useOpsUiStore((s) => s.setChartWindow)
  const scenario = currentScenario(scenarioId)

  return (
    <main className="page page-ops" aria-label="환경 관제">
      <OpsPageChrome title="환경 관제" />

      <OpsMetricCards
        state={state}
        outdoorTempC={scenario.outdoorTempC}
        stale={stale}
      />

      <div className="ops-mid-row">
        <OpsTrendChart
          history={kpiHistory}
          chartWindow={chartWindow}
          onWindowChange={setChartWindow}
        />
        <OpsDeviceStatus state={state} actuators={actuators} />
      </div>

      <div className="ops-bottom-row">
        <OpsEventFeed
          timeline={timeline}
          state={state}
          scenarioLabel={scenario.label}
          outdoorTempC={scenario.outdoorTempC}
        />
        <div className="ops-bottom-stack">
          <OpsZonePanel zones={zones} />
          <OpsSafetyRules />
        </div>
      </div>

      <footer className="ops-page-foot">
        FarmTwin 스마트팜 인터랙티브 UI · 레퍼런스 데이터 대시보드 시뮬레이션
      </footer>
    </main>
  )
}

