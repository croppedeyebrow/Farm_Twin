/**
 * 센서 데이터 품질 패널 (6단계 Day 21).
 *
 * GET /farms/{id}/sensors/health — 센서별 현재 품질·사유·경과·최근 분포.
 */

import type { QualityCounts, SensorHealth } from '../../api/farms'
import {
  QUALITY_LABEL,
  QUALITY_ORDER,
  QUALITY_TONE,
  formatAge,
  qualityReasonText,
} from '../../realtime/sensorQuality'
import { useRealtimeStore } from '../../store/realtimeStore'

function countsText(counts: QualityCounts): string {
  const parts = QUALITY_ORDER.filter((q) => (counts[q] ?? 0) > 0).map(
    (q) => `${QUALITY_LABEL[q]} ${counts[q]}`,
  )
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function valueText(item: SensorHealth): string {
  if (item.value == null) return '—'
  return `${item.value.toFixed(item.unit === 'pH' ? 2 : 1)} ${item.unit}`
}

export function SensorQualityPanel() {
  const report = useRealtimeStore((s) => s.sensorHealth)

  if (!report) {
    return (
      <section className="ops-panel ops-table-panel" aria-label="센서 데이터 품질">
        <header className="ops-panel-head">
          <h2>센서 데이터 품질</h2>
        </header>
        <p className="ops-empty">품질 정보를 불러오는 중입니다.</p>
      </section>
    )
  }

  return (
    <section className="ops-panel ops-table-panel" aria-label="센서 데이터 품질">
      <header className="ops-panel-head">
        <h2>센서 데이터 품질</h2>
        <span className="ops-sort-tag">
          {report.run_id ? `run ${report.run_status ?? '?'}` : 'run 없음'} ·{' '}
          {countsText(report.summary)}
        </span>
      </header>
      {!report.run_id ? (
        <p className="ops-empty">
          시뮬레이션 run 이 없어 판정할 측정값이 없습니다.
        </p>
      ) : (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>센서</th>
                <th>품질</th>
                <th>사유</th>
                <th>마지막 값</th>
                <th>seq</th>
                <th>경과(시뮬)</th>
                <th>최근 {report.recent_window}건</th>
              </tr>
            </thead>
            <tbody>
              {report.sensors.map((item) => (
                <tr key={item.sensor_id}>
                  <td>
                    <strong>{item.name}</strong>
                    <em>{item.code}</em>
                  </td>
                  <td>
                    <span className={`ops-badge tone-${QUALITY_TONE[item.quality]}`}>
                      {QUALITY_LABEL[item.quality]}
                    </span>
                  </td>
                  <td>{qualityReasonText(item.quality_reason)}</td>
                  <td>{valueText(item)}</td>
                  <td>{item.source_sequence ?? '—'}</td>
                  <td>{formatAge(item.age_simulation_s)}</td>
                  <td>{countsText(item.recent_counts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
