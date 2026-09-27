/**
 * 데이터 품질 리포트 패널 (6단계 Day 23).
 *
 * GET /farms/{id}/quality-report — 최신 run 전체 구간의 센서별 품질 분포,
 * 주요 사유, 고장 주입 구간. 현재 품질(SensorQualityPanel)과 달리 누적 관점이다.
 */

import { fetchQualityReport, type SensorQualityReport } from '../../api/data'
import type { QualityCounts } from '../../api/farms'
import {
  QUALITY_LABEL,
  QUALITY_ORDER,
  formatSimTime,
  qualityReasonText,
} from '../../realtime/sensorQuality'
import { usePolling } from '../../realtime/usePolling'
import { useRealtimeStore } from '../../store/realtimeStore'

const REPORT_POLL_MS = 15000

const FAULT_LABEL: Record<string, string> = {
  spike: '스파이크',
  stuck: '고정',
  dropout: '끊김',
}

function pct(value: number | null): string {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function ratioTone(value: number | null): string {
  if (value == null) return 'info'
  if (value >= 0.95) return 'ok'
  if (value >= 0.8) return 'warn'
  return 'alert'
}

function countsText(counts: QualityCounts): string {
  const parts = QUALITY_ORDER.filter((q) => (counts[q] ?? 0) > 0).map(
    (q) => `${QUALITY_LABEL[q]} ${counts[q]}`,
  )
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function faultsText(item: SensorQualityReport): string {
  if (item.faults.length === 0) return '—'
  return item.faults
    .map(
      (f) =>
        `${FAULT_LABEL[f.fault_type] ?? f.fault_type} ${formatSimTime(f.start_simulation_time)}~${
          f.end_simulation_time == null ? '진행 중' : formatSimTime(f.end_simulation_time)
        }`,
    )
    .join(', ')
}

export function QualityReportPanel() {
  const farmId = useRealtimeStore((s) => s.farmId)
  const runId = useRealtimeStore((s) => s.sensorHealth?.run_id ?? null)
  const { data: report, error } = usePolling(
    farmId && runId ? `${farmId}|${runId}` : null,
    () => fetchQualityReport(farmId ?? ''),
    REPORT_POLL_MS,
  )

  return (
    <section className="ops-panel ops-table-panel" aria-label="데이터 품질 리포트">
      <header className="ops-panel-head">
        <h2>데이터 품질 리포트</h2>
        <span className="ops-sort-tag">
          {report?.run_id
            ? `run 전체 ${report.total}건 · 정상 ${pct(report.good_ratio)}`
            : 'run 없음'}
        </span>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {!report?.run_id ? (
        <p className="ops-empty">리포트를 만들 측정 이력이 없습니다.</p>
      ) : (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>센서</th>
                <th>건수</th>
                <th>정상 비율</th>
                <th>품질 분포</th>
                <th>주요 사유</th>
                <th>고장 구간</th>
              </tr>
            </thead>
            <tbody>
              {report.sensors.map((item) => (
                <tr key={item.sensor_id}>
                  <td>
                    <strong>{item.sensor_code}</strong>
                    <em>
                      {formatSimTime(item.first_simulation_time)} ~{' '}
                      {formatSimTime(item.last_simulation_time)}
                    </em>
                  </td>
                  <td>{item.total}</td>
                  <td>
                    <span className={`ops-badge tone-${ratioTone(item.good_ratio)}`}>
                      {pct(item.good_ratio)}
                    </span>
                  </td>
                  <td>{countsText(item.quality_counts)}</td>
                  <td>
                    {item.top_reasons.length === 0
                      ? '—'
                      : item.top_reasons
                          .map((r) => `${qualityReasonText(r.reason)} ${r.count}`)
                          .join(', ')}
                  </td>
                  <td>{faultsText(item)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
