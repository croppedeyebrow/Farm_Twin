/**
 * 환경 관제 — FarmTwin / OPERATIONS
 */

import { OpsDeviceStatus } from '../components/ops/OpsDeviceStatus'
import {
  OpsEventFeed,
  OpsSafetyRules,
} from '../components/ops/OpsEventFeed'
import { OpsMetricCards } from '../components/ops/OpsMetricCards'
import { OpsPageChrome } from '../components/ops/OpsPageChrome'
import { OpsTrendChart } from '../components/ops/OpsTrendChart'
import { currentScenario, useOpsUiStore } from '../store/opsUiStore'
import { useRealtimeStore } from '../store/realtimeStore'

export function DashboardPage() {
  const state = useRealtimeStore((s) => s.state)
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
        <OpsSafetyRules />
      </div>

      <footer className="ops-page-foot">
        FarmTwin 스마트팜 인터랙티브 UI · 레퍼런스 데이터 대시보드 시뮬레이션
      </footer>
    </main>
  )
}
