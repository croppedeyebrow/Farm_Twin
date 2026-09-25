/**
 * 환경 관제 운영 기준 · 시나리오 · 상태 판정
 * (레퍼런스: FarmTwin / OPERATIONS)
 */

import type { ActuatorSummary, FarmStateSnapshot } from '../../api/farms'

export type OpsScenarioId =
  | 'normal'
  | 'heatwave'
  | 'drought'
  | 'sensor_delay'

export type OpsScenario = {
  id: OpsScenarioId
  label: string
  outdoorTempC: number
  banner: string
}

export const OPS_SCENARIOS: OpsScenario[] = [
  {
    id: 'normal',
    label: '정상 운전',
    outdoorTempC: 26.4,
    banner: '시뮬레이션 실행 중 · 모든 센서 정상',
  },
  {
    id: 'heatwave',
    label: '외부 폭염',
    outdoorTempC: 36.7,
    banner: '시뮬레이션 실행 중 · 실내 고온 · 빈번 환기 가동',
  },
  {
    id: 'drought',
    label: '건조 / 관수 부족',
    outdoorTempC: 29.5,
    banner: '시뮬레이션 실행 중 · 토양 건조 위험 · 관수 대기',
  },
  {
    id: 'sensor_delay',
    label: '센서 통신 지연',
    outdoorTempC: 26.0,
    banner: '시뮬레이션 실행 중 · 센서 지연 · 최신값 보류',
  },
]

export const DEFAULT_CONTROL_RULES = {
  coolStartC: 30,
  humidStartPct: 45,
  irrigateStartPct: 30,
} as const

export const SAFETY_RULES = [
  {
    id: 'high_temp',
    title: '고온 감지',
    detail: '> 30℃ · 해제 < 28℃',
  },
  {
    id: 'low_humidity',
    title: '저습 감지',
    detail: '< 45% · 해제 > 55%',
  },
  {
    id: 'dry_soil',
    title: '토양 건조',
    detail: '< 10% · 해제 > 45%',
  },
] as const

export type StatusTone = 'ok' | 'warn' | 'alert' | 'idle' | 'info' | 'run'

export function tempBadge(tempC: number): { label: string; tone: StatusTone } {
  if (tempC > 30) return { label: '고온', tone: 'alert' }
  if (tempC >= 28) return { label: '주의', tone: 'warn' }
  return { label: '정상', tone: 'ok' }
}

export function humidityBadge(pct: number): { label: string; tone: StatusTone } {
  if (pct < 45) return { label: '저습', tone: 'warn' }
  if (pct > 80) return { label: '과습', tone: 'warn' }
  return { label: '정상', tone: 'ok' }
}

export function soilBadge(pct: number): { label: string; tone: StatusTone } {
  if (pct < 10) return { label: '건조', tone: 'alert' }
  if (pct < 40) return { label: '주의', tone: 'warn' }
  return { label: '정상', tone: 'ok' }
}

export function outdoorBadge(
  outdoorC: number,
): { label: string; tone: StatusTone } {
  if (outdoorC >= 35) return { label: '폭염 주의', tone: 'warn' }
  if (outdoorC >= 32) return { label: '고온', tone: 'alert' }
  if (outdoorC <= 28) return { label: '맑음', tone: 'ok' }
  return { label: '참고용', tone: 'info' }
}

export function sensorRowStatus(
  kind: 'temp' | 'humidity' | 'soil',
  state: FarmStateSnapshot | null,
): { label: string; tone: StatusTone } {
  if (!state) return { label: '대기', tone: 'idle' }
  if (kind === 'temp') {
    return state.temperature_c > 30
      ? { label: '경고', tone: 'alert' }
      : { label: '정상', tone: 'ok' }
  }
  if (kind === 'humidity') {
    return state.humidity_pct < 45
      ? { label: '경고', tone: 'warn' }
      : { label: '정상', tone: 'ok' }
  }
  return state.substrate_moisture_pct < 10
    ? { label: '경고', tone: 'alert' }
    : { label: '정상', tone: 'ok' }
}

export function actuatorRunLabel(
  actuators: ActuatorSummary[],
  type: string,
): { label: string; tone: StatusTone } {
  const hit = actuators.find((a) => a.actuator_type === type)
  if (!hit) return { label: '대기', tone: 'idle' }
  if (hit.output_ratio > 0.05) return { label: '가동', tone: 'run' }
  return { label: '대기', tone: 'idle' }
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}

export function formatEventTime(date: Date): string {
  return date.toLocaleTimeString('ko-KR', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export function formatStamp(date: Date): string {
  return date.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}
