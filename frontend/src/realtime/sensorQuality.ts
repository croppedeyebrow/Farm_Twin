/**
 * 센서 reading 품질 표시 규칙 (6단계 Day 21).
 *
 * backend quality_reason 은 ";" 로 이어진 코드 문자열이다.
 * 3D 색은 프론트엔드 설계 5절 — 의심=주황 이상, 불량/누락/stale=회색.
 */

import type { ReadingQuality, SensorHealthReport } from '../api/farms'
import type { StatusLevel } from '../scene/statusColors'

export const QUALITY_ORDER: ReadingQuality[] = [
  'good',
  'suspect',
  'bad',
  'missing',
  'stale',
]

export const QUALITY_LABEL: Record<ReadingQuality, string> = {
  good: '정상',
  suspect: '의심',
  bad: '불량',
  missing: '누락',
  stale: '지연',
}

/** ops-badge tone-* 클래스 */
export const QUALITY_TONE: Record<ReadingQuality, string> = {
  good: 'ok',
  suspect: 'warn',
  bad: 'alert',
  missing: 'info',
  stale: 'info',
}

const REASON_LABEL: Record<string, string> = {
  sequence_gap: 'sequence 누락 후 수신',
  sequence_duplicate: 'sequence 중복',
  sequence_out_of_order: 'sequence 역순',
  time_reversed: '측정 시각 역전',
  flatline_detected: '값 고정(stuck) 의심',
  rate_of_change_exceeded: '변화율 초과',
  ingest_latency_exceeded: '수집 지연 초과',
  no_readings: '미수집',
  stale_simulation_time: '측정 갱신 끊김',
  stale_ingest_timeout: '수신 시간 초과',
  out_of_range_clamped_low: '측정 범위 하한 보정',
  out_of_range_clamped_high: '측정 범위 상한 보정',
}

export function qualityReasonText(reason: string | null): string {
  if (!reason) return '—'
  return reason
    .split(';')
    .map((code) => REASON_LABEL[code] ?? code)
    .join(' · ')
}

export function formatAge(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds.toFixed(0)}초`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}분`
  return `${(seconds / 3600).toFixed(1)}시간`
}

/** 임계 기반 상태에 품질을 덮어쓴다 — 믿을 수 없는 값은 색으로 판단하지 않는다. */
export function applyQualityToStatus(
  level: StatusLevel,
  quality: ReadingQuality | undefined,
): StatusLevel {
  if (!quality || quality === 'good') return level
  if (quality === 'suspect') return level === 'ok' ? 'warn' : level
  return 'stale'
}

/** 실행 중인 run 이 있을 때만 sensor_id → quality 를 돌려준다. */
export function qualityBySensor(
  report: SensorHealthReport | null,
): Map<string, ReadingQuality> {
  const map = new Map<string, ReadingQuality>()
  if (!report?.run_id) return map
  for (const item of report.sensors) {
    map.set(item.sensor_id, item.quality)
  }
  return map
}
