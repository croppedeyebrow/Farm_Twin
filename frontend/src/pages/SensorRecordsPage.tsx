/**
 * 센서 기록 — 측정 이력 테이블
 */

import { useMemo } from 'react'

import { OpsPageChrome } from '../components/ops/OpsPageChrome'
import {
  formatStamp,
  humidityBadge,
  outdoorBadge,
  soilBadge,
  tempBadge,
} from '../components/ops/opsRules'
import type { KpiSample } from '../realtime/history'
import {
  currentScenario,
  useOpsUiStore,
  type ChartWindow,
  type SensorFilter,
} from '../store/opsUiStore'
import { useRealtimeStore } from '../store/realtimeStore'

type RecordRow = {
  id: string
  at: Date
  sensor: string
  code: string
  value: string
  status: string
  tone: string
  source: string
}

const SENSOR_OPTS: { id: SensorFilter; label: string }[] = [
  { id: 'all', label: '전체 센서' },
  { id: 'temp', label: '실내 온도' },
  { id: 'humidity', label: '실내 습도' },
  { id: 'soil', label: '토양수분' },
  { id: 'outdoor', label: '외부 온도' },
]

const WINDOW_OPTS: { id: ChartWindow; label: string }[] = [
  { id: '1h', label: '1시간' },
  { id: '6h', label: '6시간' },
  { id: '24h', label: '24시간' },
]

function windowSeconds(w: ChartWindow): number {
  if (w === '6h') return 6 * 3600
  if (w === '24h') return 24 * 3600
  return 3600
}

function buildRows(
  history: KpiSample[],
  outdoorTempC: number,
  filter: SensorFilter,
  win: ChartWindow,
): RecordRow[] {
  if (history.length === 0) return []
  const lastT = history[history.length - 1].simulation_time
  const minT = lastT - windowSeconds(win)
  const sliced = history.filter((s) => s.simulation_time >= minT)
  const now = Date.now()
  const rows: RecordRow[] = []

  for (let i = sliced.length - 1; i >= 0; i -= 1) {
    const sample = sliced[i]
    const agoSec = lastT - sample.simulation_time
    const at = new Date(now - agoSec * 1000)
    const t = tempBadge(sample.temperature_c)
    const h = humidityBadge(sample.humidity_pct)
    const s = soilBadge(sample.substrate_moisture_pct)
    const o = outdoorBadge(outdoorTempC)

    const candidates: RecordRow[] = [
      {
        id: `${sample.simulation_time}-temp`,
        at,
        sensor: '실내 온도',
        code: 'TEMP-01',
        value: `${sample.temperature_c.toFixed(1)} ℃`,
        status: t.label,
        tone: t.tone,
        source: '시뮬레이션',
      },
      {
        id: `${sample.simulation_time}-hum`,
        at,
        sensor: '실내 습도',
        code: 'HUM-01',
        value: `${sample.humidity_pct.toFixed(1)} %`,
        status: h.label,
        tone: h.tone,
        source: '시뮬레이션',
      },
      {
        id: `${sample.simulation_time}-soil`,
        at,
        sensor: '토양수분',
        code: 'SOIL-01',
        value: `${sample.substrate_moisture_pct.toFixed(1)} %`,
        status: s.label,
        tone: s.tone,
        source: '시뮬레이션',
      },
      {
        id: `${sample.simulation_time}-out`,
        at,
        sensor: '외부 온도',
        code: 'WEATHER',
        value: `${outdoorTempC.toFixed(1)} ℃`,
        status: o.label === '맑음' ? '참고값' : o.label,
        tone: o.tone === 'ok' ? 'info' : o.tone,
        source: '시뮬레이션',
      },
    ]

    for (const row of candidates) {
      if (filter === 'all') rows.push(row)
      else if (filter === 'temp' && row.code === 'TEMP-01') rows.push(row)
      else if (filter === 'humidity' && row.code === 'HUM-01') rows.push(row)
      else if (filter === 'soil' && row.code === 'SOIL-01') rows.push(row)
      else if (filter === 'outdoor' && row.code === 'WEATHER') rows.push(row)
    }
  }

  return rows
}

export function SensorRecordsPage() {
  const kpiHistory = useRealtimeStore((s) => s.kpiHistory)
  const scenarioId = useOpsUiStore((s) => s.scenarioId)
  const sensorFilter = useOpsUiStore((s) => s.sensorFilter)
  const recordsWindow = useOpsUiStore((s) => s.recordsWindow)
  const setSensorFilter = useOpsUiStore((s) => s.setSensorFilter)
  const setRecordsWindow = useOpsUiStore((s) => s.setRecordsWindow)
  const scenario = currentScenario(scenarioId)

  const rows = useMemo(
    () =>
      buildRows(
        kpiHistory,
        scenario.outdoorTempC,
        sensorFilter,
        recordsWindow,
      ),
    [kpiHistory, scenario.outdoorTempC, sensorFilter, recordsWindow],
  )

  const warnCount = rows.filter(
    (r) => r.tone === 'warn' || r.tone === 'alert',
  ).length
  const windowLabel =
    WINDOW_OPTS.find((w) => w.id === recordsWindow)?.label ?? '1시간'

  return (
    <main className="page page-ops" aria-label="센서 기록">
      <OpsPageChrome title="센서 기록" />

      <section className="ops-records-head" aria-label="센서 기록 요약">
        <div>
          <h2>센서 기록</h2>
          <p>기간·센서별 측정값을 조회합니다.</p>
        </div>
        <div className="ops-records-filters">
          <label>
            센서
            <select
              value={sensorFilter}
              onChange={(e) =>
                setSensorFilter(e.target.value as SensorFilter)
              }
            >
              {SENSOR_OPTS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            기간
            <select
              value={recordsWindow}
              onChange={(e) =>
                setRecordsWindow(e.target.value as ChartWindow)
              }
            >
              {WINDOW_OPTS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="ops-metrics ops-metrics-3" aria-label="기록 요약 카드">
        <article className="ops-metric-card">
          <header>
            <span>조회 기간</span>
          </header>
          <strong>{windowLabel}</strong>
          <p>시뮬레이션 표준 시점</p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>표시 기록</span>
          </header>
          <strong>
            {rows.length}
            <span>건</span>
          </strong>
          <p>선택한 센서 기준</p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>주의 · 이상</span>
          </header>
          <strong>
            {warnCount}
            <span>건</span>
          </strong>
          <p>임계값 기준 상태 판정</p>
        </article>
      </section>

      <section className="ops-panel ops-table-panel" aria-label="측정 이력">
        <header className="ops-panel-head">
          <h2>측정 이력</h2>
          <span className="ops-sort-tag">최신순 · {rows.length}건</span>
        </header>
        {rows.length === 0 ? (
          <p className="ops-empty">아직 측정 이력이 없습니다. 시뮬이 진행되면 쌓입니다.</p>
        ) : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>측정 시각</th>
                  <th>센서</th>
                  <th>측정값</th>
                  <th>상태</th>
                  <th>출처</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 120).map((row) => (
                  <tr key={row.id}>
                    <td>{formatStamp(row.at)}</td>
                    <td>
                      <strong>{row.sensor}</strong>
                      <em>{row.code}</em>
                    </td>
                    <td>{row.value}</td>
                    <td>
                      <span className={`ops-badge tone-${row.tone}`}>
                        {row.status}
                      </span>
                    </td>
                    <td>{row.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}
