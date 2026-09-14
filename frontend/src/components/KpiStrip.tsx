/**
 * KPI 스트립 (5단계 Day 18).
 *
 * FarmState 참값 5지표를 한 줄로 보여 차트·3D 와 동일 소스를 쓴다.
 * (설계: 온도·습도·CO₂·배지수분·PPFD)
 */

import type { FarmStateSnapshot } from '../api/farms'

type Props = {
  state: FarmStateSnapshot | null
  stale: boolean
}

const METRICS: Array<{
  key: keyof Pick<
    FarmStateSnapshot,
    | 'temperature_c'
    | 'humidity_pct'
    | 'co2_ppm'
    | 'substrate_moisture_pct'
    | 'ppfd_umol'
  >
  label: string
  unit: string
  digits: number
}> = [
  { key: 'temperature_c', label: '온도', unit: '°C', digits: 1 },
  { key: 'humidity_pct', label: '습도', unit: '%', digits: 1 },
  { key: 'co2_ppm', label: 'CO₂', unit: 'ppm', digits: 0 },
  { key: 'substrate_moisture_pct', label: '배지', unit: '%', digits: 1 },
  { key: 'ppfd_umol', label: 'PPFD', unit: '', digits: 0 },
]

export function KpiStrip({ state, stale }: Props) {
  return (
    <section className="kpi-strip" aria-label="환경 KPI">
      <div className="panel-title-row">
        <h2>환경 KPI</h2>
        {stale ? <span className="badge-warn">stale</span> : null}
      </div>
      <div className="kpi-grid">
        {METRICS.map((metric) => {
          const value = state?.[metric.key]
          return (
            <div key={metric.key} className="kpi-card">
              <span>{metric.label}</span>
              <strong>
                {value == null
                  ? '—'
                  : `${value.toFixed(metric.digits)}${metric.unit ? ` ${metric.unit}` : ''}`}
              </strong>
            </div>
          )
        })}
      </div>
    </section>
  )
}
