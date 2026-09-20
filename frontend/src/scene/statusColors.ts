/**
 * 3D 상태 색·임계값 (5단계 Day 19).
 *
 * 프론트엔드 설계 5절
 * -------------------
 * 정상=녹색, 주의=주황, 위험=적색(점멸), 불량/stale=회색
 *
 * KPI 참값으로 센서 마커 색을 정한다.
 * (가상 센서 quality 는 readings API — Day 19 MVP 는 참값 임계로 충분)
 */

export type StatusLevel = 'ok' | 'warn' | 'danger' | 'stale'

export const STATUS_COLOR: Record<StatusLevel, string> = {
  ok: '#2f9e44',
  warn: '#e67700',
  danger: '#c92a2a',
  stale: '#868e96',
}

/** 센서 타입 → KPI 필드 */
export type SensorMetricKey =
  | 'temperature_c'
  | 'humidity_pct'
  | 'co2_ppm'
  | 'substrate_moisture_pct'
  | 'ppfd_umol'

export function sensorTypeToMetric(sensorType: string): SensorMetricKey | null {
  switch (sensorType) {
    case 'temperature':
      return 'temperature_c'
    case 'humidity':
      return 'humidity_pct'
    case 'co2':
      return 'co2_ppm'
    case 'substrate_moisture':
      return 'substrate_moisture_pct'
    case 'ppfd':
      return 'ppfd_umol'
    default:
      return null
  }
}

/**
 * 실내 스마트팜 교육용 대략 임계 (엄밀 생리 모델 아님).
 */
export function metricStatus(
  metric: SensorMetricKey,
  value: number,
  options: { stale?: boolean } = {},
): StatusLevel {
  if (options.stale) return 'stale'
  switch (metric) {
    case 'temperature_c':
      if (value < 15 || value > 32) return 'danger'
      if (value < 18 || value > 28) return 'warn'
      return 'ok'
    case 'humidity_pct':
      if (value < 35 || value > 90) return 'danger'
      if (value < 45 || value > 80) return 'warn'
      return 'ok'
    case 'co2_ppm':
      if (value < 300 || value > 2000) return 'danger'
      if (value < 400 || value > 1200) return 'warn'
      return 'ok'
    case 'substrate_moisture_pct':
      if (value < 20 || value > 85) return 'danger'
      if (value < 30 || value > 70) return 'warn'
      return 'ok'
    case 'ppfd_umol':
      if (value > 900) return 'danger'
      if (value > 600 || value < 50) return 'warn'
      return 'ok'
  }
}
