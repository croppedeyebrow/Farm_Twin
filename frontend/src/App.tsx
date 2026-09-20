/**
 * 관제 셸 (1단계~5단계 Day 19).
 *
 * 레이아웃
 * --------
 * - 풀블리드 3D: 포도 터널 + 딸기 랙 + 센서/설비 비주얼 (Day 19)
 * - 좌측 overlay: 브랜드 + 연결 상태
 * - 우측 dashboard: KPI · 시계열 · 상세 · 타임라인
 *
 * 연동
 * ----
 * 3D 센서 클릭 → selectSensor + chartMetric
 * 상세 패널 센서 선택 → 동일 chartMetric
 */
import { useEffect, useState } from 'react'
import './App.css'
import { DetailPanel } from './components/DetailPanel'
import { EventTimeline } from './components/EventTimeline'
import { KpiStrip } from './components/KpiStrip'
import { TimeSeriesChart } from './components/TimeSeriesChart'
import { DEMO_FARM_ID } from './config'
import {
  startFarmRealtimeSession,
  stopFarmRealtimeSession,
} from './realtime/session'
import { GrowingRoomScene } from './scene/GrowingRoomScene'
import { sensorTypeToMetric } from './scene/statusColors'
import { useRealtimeStore } from './store/realtimeStore'

/** UI에 표시하는 health 조회 상태. */
type HealthState = 'loading' | 'ok' | 'error'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [ready, setReady] = useState<HealthState>('loading')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)

  const socketStatus = useRealtimeStore((s) => s.socketStatus)
  const lastSequence = useRealtimeStore((s) => s.lastSequence)
  const stale = useRealtimeStore((s) => s.stale)
  const recovering = useRealtimeStore((s) => s.recovering)
  const state = useRealtimeStore((s) => s.state)
  const sensors = useRealtimeStore((s) => s.sensors)
  const actuators = useRealtimeStore((s) => s.actuators)
  const kpiHistory = useRealtimeStore((s) => s.kpiHistory)
  const timeline = useRealtimeStore((s) => s.timeline)
  const selectedSensorId = useRealtimeStore((s) => s.selectedSensorId)
  const selectedActuatorId = useRealtimeStore((s) => s.selectedActuatorId)
  const simulationStatus = useRealtimeStore((s) => s.simulationStatus)
  const realtimeError = useRealtimeStore((s) => s.lastError)
  const selectSensor = useRealtimeStore((s) => s.selectSensor)
  const selectActuator = useRealtimeStore((s) => s.selectActuator)
  const setChartMetric = useRealtimeStore((s) => s.setChartMetric)

  useEffect(() => {
    let cancelled = false

    async function checkApi() {
      try {
        const healthResponse = await fetch('/api/health')
        if (!healthResponse.ok) {
          throw new Error(`health ${healthResponse.status}`)
        }
        if (!cancelled) {
          setHealth('ok')
        }

        const readyResponse = await fetch('/api/health/ready')
        if (!cancelled) {
          setReady(readyResponse.ok ? 'ok' : 'error')
          if (!readyResponse.ok) {
            const body = (await readyResponse.json().catch(() => null)) as
              | { detail?: string }
              | null
            setErrorDetail(body?.detail ?? `ready ${readyResponse.status}`)
          }
        }
      } catch (error) {
        if (!cancelled) {
          setHealth('error')
          setReady('error')
          setErrorDetail(error instanceof Error ? error.message : 'request failed')
        }
      }
    }

    void checkApi()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void startFarmRealtimeSession(DEMO_FARM_ID)
    return () => {
      stopFarmRealtimeSession()
    }
  }, [])

  return (
    <main className="shell">
      <div className="viewport" aria-label="3D 재배실" data-testid="farm-3d-viewport">
        <GrowingRoomScene />
      </div>

      <header className="overlay">
        <p className="brand-name">FarmTwin</p>
        <h1>실내 스마트팜 운영 트윈</h1>
        <p className="lede">
          포도 터널·딸기 랙 — 3D 선택과 KPI·차트가 같은 상태를 봅니다.
        </p>

        <section className="status" aria-live="polite">
          <div className="status-row">
            <span>API /health</span>
            <strong data-state={health}>{labelFor(health)}</strong>
          </div>
          <div className="status-row">
            <span>API /health/ready</span>
            <strong data-state={ready}>{labelFor(ready)}</strong>
          </div>
          <div className="status-row">
            <span>WebSocket</span>
            <strong data-state={socketDataState(socketStatus)}>
              {socketLabel(socketStatus)}
            </strong>
          </div>
          <div className="status-row">
            <span>WS sequence</span>
            <strong>{lastSequence}</strong>
          </div>
          <div className="status-row">
            <span>데이터</span>
            <strong data-state={stale || recovering ? 'error' : 'ok'}>
              {recovering ? '복구 중' : stale ? 'stale' : '최신'}
            </strong>
          </div>
          {simulationStatus ? (
            <div className="status-row">
              <span>Run</span>
              <strong>{simulationStatus}</strong>
            </div>
          ) : null}
          {errorDetail ? <p className="error">{errorDetail}</p> : null}
          {realtimeError ? <p className="error">{realtimeError}</p> : null}
        </section>
      </header>

      <aside className="dashboard" aria-label="관제 대시보드">
        <KpiStrip state={state} stale={stale} />
        <TimeSeriesChart history={kpiHistory} />
        <DetailPanel
          sensors={sensors}
          actuators={actuators}
          selectedSensorId={selectedSensorId}
          selectedActuatorId={selectedActuatorId}
          onSelectSensor={(id) => {
            selectSensor(id)
            if (id == null) return
            const sensor = sensors.find((item) => item.id === id)
            const metric = sensor
              ? sensorTypeToMetric(sensor.sensor_type)
              : null
            if (metric) setChartMetric(metric)
          }}
          onSelectActuator={selectActuator}
        />
        <EventTimeline entries={timeline} />
      </aside>
    </main>
  )
}

function labelFor(state: HealthState): string {
  if (state === 'loading') return '확인 중'
  if (state === 'ok') return '정상'
  return '실패'
}

function socketLabel(status: string): string {
  switch (status) {
    case 'connected':
      return '연결됨'
    case 'connecting':
      return '연결 중'
    case 'reconnecting':
      return '재연결 중'
    case 'stopped':
      return '중지'
    default:
      return status
  }
}

function socketDataState(status: string): HealthState {
  if (status === 'connected') return 'ok'
  if (status === 'reconnecting' || status === 'connecting') return 'loading'
  return 'error'
}

export default App
