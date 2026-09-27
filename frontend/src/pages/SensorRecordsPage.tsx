/**
 * 센서 기록 — DB 측정 이력(원시 / 1분 / 5분 집계)·품질 리포트·재현/lineage (Day 23)
 *
 * 이력은 화면 로컬 KPI 링이 아니라 sensor_readings 를 가상 시계 기준으로 조회한다.
 * 집계 평균·범위는 good 행만 쓰고, 품질 분포는 모든 행(누락 마커 포함)을 센다.
 */

import { useMemo, useState } from 'react'

import {
  fetchReadingHistory,
  type HistoryBucket,
  type ReadingHistory,
} from '../api/data'
import type { QualityCounts } from '../api/farms'
import { FaultInjectionPanel } from '../components/ops/FaultInjectionPanel'
import { OpsPageChrome } from '../components/ops/OpsPageChrome'
import { QualityReportPanel } from '../components/ops/QualityReportPanel'
import { ReplayLineagePanel } from '../components/ops/ReplayLineagePanel'
import { SensorQualityPanel } from '../components/ops/SensorQualityPanel'
import {
  QUALITY_LABEL,
  QUALITY_ORDER,
  QUALITY_TONE,
  formatSimTime,
  qualityReasonText,
} from '../realtime/sensorQuality'
import { usePolling } from '../realtime/usePolling'
import { useOpsUiStore, type ChartWindow } from '../store/opsUiStore'
import { useRealtimeStore } from '../store/realtimeStore'

const HISTORY_POLL_MS = 10000

const BUCKET_OPTS: { id: HistoryBucket; label: string }[] = [
  { id: 0, label: '원시' },
  { id: 60, label: '1분 집계' },
  { id: 300, label: '5분 집계' },
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

type HistoryRow = {
  id: string
  t: number
  sensorCode: string
  unit: string
  value: string
  range: string
  count: number
  counts: QualityCounts
  badge: { label: string; tone: string }
  detail: string
}

function fmt(value: number | null, unit: string): string {
  if (value == null) return '—'
  return `${value.toFixed(unit === 'pH' ? 2 : 1)} ${unit}`
}

function countsText(counts: QualityCounts): string {
  const parts = QUALITY_ORDER.filter((q) => (counts[q] ?? 0) > 0).map(
    (q) => `${QUALITY_LABEL[q]} ${counts[q]}`,
  )
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function nonGood(counts: QualityCounts): number {
  return QUALITY_ORDER.filter((q) => q !== 'good').reduce(
    (sum, q) => sum + (counts[q] ?? 0),
    0,
  )
}

function buildRows(history: ReadingHistory | null): HistoryRow[] {
  if (!history) return []
  const raw = history.bucket_seconds === 0
  const rows: HistoryRow[] = []
  for (const series of history.series) {
    for (const point of series.points) {
      const bad = nonGood(point.quality_counts)
      const quality = point.quality
      rows.push({
        id: `${series.sensor_id}-${point.t}-${point.source_sequence ?? ''}`,
        t: point.t,
        sensorCode: series.sensor_code,
        unit: series.unit,
        value: raw ? fmt(point.avg, series.unit) : `평균 ${fmt(point.avg, series.unit)}`,
        range: raw
          ? `원시 ${fmt(point.raw_value, series.unit)}`
          : point.min == null
            ? '정상 측정 없음'
            : `${fmt(point.min, series.unit)} ~ ${fmt(point.max, series.unit)}`,
        count: point.count,
        counts: point.quality_counts,
        badge:
          raw && quality
            ? { label: QUALITY_LABEL[quality], tone: QUALITY_TONE[quality] }
            : bad === 0
              ? { label: '정상', tone: 'ok' }
              : { label: `이상 ${bad}`, tone: bad === point.count ? 'alert' : 'warn' },
        detail: raw
          ? `${qualityReasonText(point.quality_reason)} · seq ${point.source_sequence ?? '—'}`
          : countsText(point.quality_counts),
      })
    }
  }
  return rows.sort((a, b) => b.t - a.t || a.sensorCode.localeCompare(b.sensorCode))
}

export function SensorRecordsPage() {
  const farmId = useRealtimeStore((s) => s.farmId)
  const health = useRealtimeStore((s) => s.sensorHealth)
  const recordsWindow = useOpsUiStore((s) => s.recordsWindow)
  const setRecordsWindow = useOpsUiStore((s) => s.setRecordsWindow)
  const [sensorCode, setSensorCode] = useState('')
  const [bucket, setBucket] = useState<HistoryBucket>(60)

  const runId = health?.run_id ?? null
  const sensors = health?.sensors ?? []
  const key =
    farmId && runId ? `${farmId}|${runId}|${bucket}|${sensorCode}|${recordsWindow}` : null

  const { data: history, error } = usePolling(
    key,
    () => {
      const now = useRealtimeStore.getState().sensorHealth?.current_simulation_time
      return fetchReadingHistory(farmId ?? '', {
        bucketSeconds: bucket,
        sensorCode: sensorCode || undefined,
        start: now != null ? Math.max(0, now - windowSeconds(recordsWindow)) : undefined,
        limit: bucket === 0 ? 500 : 300,
      })
    },
    HISTORY_POLL_MS,
  )

  const rows = useMemo(() => buildRows(history), [history])
  const measured = rows.reduce((sum, row) => sum + row.count, 0)
  const abnormal = rows.reduce((sum, row) => sum + nonGood(row.counts), 0)
  const windowLabel =
    WINDOW_OPTS.find((w) => w.id === recordsWindow)?.label ?? '1시간'
  const bucketLabel = BUCKET_OPTS.find((b) => b.id === bucket)?.label ?? ''

  return (
    <main className="page page-ops" aria-label="센서 기록">
      <OpsPageChrome title="센서 기록" />

      <section className="ops-records-head" aria-label="센서 기록 요약">
        <div>
          <h2>센서 기록</h2>
          <p>DB 에 적재된 측정값을 가상 시계 기준으로 조회·집계합니다.</p>
        </div>
        <div className="ops-records-filters">
          <label>
            센서
            <select value={sensorCode} onChange={(e) => setSensorCode(e.target.value)}>
              <option value="">전체 센서</option>
              {sensors.map((item) => (
                <option key={item.sensor_id} value={item.code}>
                  {item.name} ({item.code})
                </option>
              ))}
            </select>
          </label>
          <label>
            해상도
            <select
              value={bucket}
              onChange={(e) => setBucket(Number(e.target.value) as HistoryBucket)}
            >
              {BUCKET_OPTS.map((opt) => (
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
              onChange={(e) => setRecordsWindow(e.target.value as ChartWindow)}
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
          <p>{bucketLabel} · 가상 시계 기준</p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>측정 건수</span>
          </header>
          <strong>
            {measured}
            <span>건</span>
          </strong>
          <p>
            {bucket === 0 ? '원시 행' : `${rows.length}개 구간`} · 누락 마커 포함
          </p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>품질 이상</span>
          </header>
          <strong>
            {abnormal}
            <span>건</span>
          </strong>
          <p>의심·불량·누락·지연</p>
        </article>
      </section>

      <SensorQualityPanel />

      <FaultInjectionPanel />

      <section className="ops-panel ops-table-panel" aria-label="측정 이력">
        <header className="ops-panel-head">
          <h2>측정 이력</h2>
          <span className="ops-sort-tag">
            최신순 · {bucketLabel} · {rows.length}행
          </span>
        </header>
        {error ? <p className="error">{error}</p> : null}
        {!runId ? (
          <p className="ops-empty">시뮬레이션 run 이 없어 측정 이력이 없습니다.</p>
        ) : rows.length === 0 ? (
          <p className="ops-empty">선택한 기간에 측정 이력이 없습니다. 시뮬이 진행되면 쌓입니다.</p>
        ) : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>{bucket === 0 ? '측정 시각(시뮬)' : '구간 시작(시뮬)'}</th>
                  <th>센서</th>
                  <th>측정값</th>
                  <th>{bucket === 0 ? '원시값' : '범위(정상)'}</th>
                  <th>품질</th>
                  <th>{bucket === 0 ? '사유' : '품질 분포'}</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 200).map((row) => (
                  <tr key={row.id}>
                    <td>{formatSimTime(row.t)}</td>
                    <td>
                      <strong>{row.sensorCode}</strong>
                      {bucket === 0 ? null : <em>{row.count}건</em>}
                    </td>
                    <td>{row.value}</td>
                    <td>{row.range}</td>
                    <td>
                      <span className={`ops-badge tone-${row.badge.tone}`}>
                        {row.badge.label}
                      </span>
                    </td>
                    <td>{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <QualityReportPanel />

      <ReplayLineagePanel />
    </main>
  )
}
