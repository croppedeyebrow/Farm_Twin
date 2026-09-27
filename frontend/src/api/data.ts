/**
 * 측정 이력·품질 리포트·replay·lineage REST (6단계 Day 23).
 *
 * 이력은 DB sensor_readings 를 가상 시계 기준으로 조회·집계한다
 * (bucket 0 = 원시, 60 = 1분, 300 = 5분). 집계 평균은 good 행만 쓴다.
 */

import type { QualityCounts, ReadingQuality } from './farms'

export type HistoryBucket = 0 | 60 | 300

export type HistoryPoint = {
  t: number
  count: number
  avg: number | null
  min: number | null
  max: number | null
  quality_counts: QualityCounts
  raw_value: number | null
  quality: ReadingQuality | null
  quality_reason: string | null
  source_sequence: number | null
}

export type HistorySeries = {
  sensor_id: string
  sensor_code: string
  sensor_type: string
  unit: string
  points: HistoryPoint[]
}

export type ReadingHistory = {
  run_id: string | null
  bucket_seconds: HistoryBucket
  start_simulation_time: number | null
  end_simulation_time: number | null
  series: HistorySeries[]
}

export type SensorQualityReport = {
  sensor_id: string
  sensor_code: string
  sensor_type: string
  total: number
  quality_counts: QualityCounts
  good_ratio: number | null
  missing_ratio: number | null
  first_simulation_time: number | null
  last_simulation_time: number | null
  top_reasons: { reason: string; count: number }[]
  faults: {
    fault_type: string
    start_simulation_time: number
    end_simulation_time: number | null
  }[]
}

export type QualityReport = {
  run_id: string | null
  run_status: string | null
  generated_at: string
  total: number
  quality_counts: QualityCounts
  good_ratio: number | null
  sensors: SensorQualityReport[]
}

export type LineageRunRef = {
  id: string
  name: string
  status: string
  random_seed: number
  weather_mode: string
  environment_model_version: string
  rule_set_version: string | null
  simulation_time_seconds: number
  replay_of_run_id: string | null
}

export type RunLineage = {
  run: LineageRunRef
  started_at: string | null
  ended_at: string | null
  checkpoint_time: number | null
  telemetry_schema_versions: string[]
  sensor_model_versions: string[]
  rules: {
    id: string
    name: string
    version: number
    enabled: boolean
    metric: string
    target_actuator_type: string
    command_count: number
  }[]
  counts: {
    readings: number
    weather_snapshots: number
    rule_commands: number
    manual_commands: number
    blocked_commands: number
    events: number
    faults: number
  }
  replay_of: LineageRunRef | null
  replays: LineageRunRef[]
}

export type EventLineage = {
  event: {
    id: string
    event_type: string
    message: string | null
    actual_output_ratio: number | null
    simulation_time: number
    recorded_at: string
  }
  command: {
    id: string
    origin: 'rule' | 'manual'
    status: string
    reason: string | null
    desired_mode: string
    desired_output_ratio: number
    simulation_time: number
    idempotency_key: string
    actuator_code: string
    actuator_type: string
  }
  rule: {
    id: string
    name: string
    version_at_command: number | null
    current_version: number
    metric: string
    comparator: string
    start_threshold: number
    stop_threshold: number
  } | null
  trigger_reading: {
    id: string
    sensor_code: string
    sensor_type: string
    source_sequence: number | null
    simulation_time: number
    raw_value: number | null
    value: number | null
    quality: ReadingQuality
    quality_reason: string | null
    telemetry_schema_version: string
    sensor_model_version: string
  } | null
  weather: {
    sequence: number
    source: string
    simulation_time: number
    outdoor_temperature_c: number
    outdoor_humidity_pct: number
  } | null
  run: LineageRunRef
}

/** farmtwin.replay.v1 — 화면에서는 요약 필드만 읽고 그대로 되돌려 보낸다 */
export type ReplayDataset = {
  format: 'farmtwin.replay.v1'
  run: { id: string; name: string; simulation_time_seconds: number }
  initial_state: { simulation_time: number }
  steps: [number, number][]
  readings: unknown[]
  commands: unknown[]
  faults: unknown[]
  manual_actions: unknown[]
  [key: string]: unknown
}

export type ReplayCompare = {
  run_id: string
  source_run_id: string
  status: string
  checkpoint_time: number
  simulation_time_seconds: number
  end_simulation_time: number
  completed: boolean
  rule_set_version_expected: string | null
  rule_set_version_actual: string | null
  rule_set_match: boolean
  readings_expected: number
  readings_actual: number
  readings_matched: number
  readings_mismatched: number
  readings_missing: number
  readings_extra: number
  commands_expected: number
  commands_actual: number
  commands_matched: boolean
  reproduced: boolean
  reading_mismatches: {
    sensor_code: string
    source_sequence: number | null
    simulation_time: number
    expected: unknown[] | null
    actual: unknown[] | null
  }[]
  command_mismatches: {
    index: number
    expected: unknown[] | null
    actual: unknown[] | null
  }[]
}

export type ReplayRunResult = {
  run_id: string
  steps_applied: number
  steps_remaining: number
  paused_run_ids: string[]
  compare: ReplayCompare
}

export type SimulationRunOut = {
  id: string
  name: string
  status: string
  simulation_time_seconds: number
  replay_of_run_id: string | null
  rule_set_version: string | null
}

async function errorDetail(response: Response, label: string): Promise<Error> {
  const body = (await response.json().catch(() => null)) as
    | { detail?: unknown }
    | null
  const detail = typeof body?.detail === 'string' ? body.detail : null
  return new Error(detail ?? `${label} ${response.status}`)
}

async function getJson<T>(url: string, label: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) throw await errorDetail(response, label)
  return (await response.json()) as T
}

async function postJson<T>(url: string, body: unknown, label: string): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await errorDetail(response, label)
  return (await response.json()) as T
}

/** GET /api/farms/{farmId}/readings/history */
export function fetchReadingHistory(
  farmId: string,
  options: {
    bucketSeconds: HistoryBucket
    sensorCode?: string
    start?: number
    limit?: number
  },
): Promise<ReadingHistory> {
  const params = new URLSearchParams({
    bucket_seconds: String(options.bucketSeconds),
    limit: String(options.limit ?? 240),
  })
  if (options.sensorCode) params.set('sensor_code', options.sensorCode)
  if (options.start != null) params.set('start', String(options.start))
  return getJson(`/api/farms/${farmId}/readings/history?${params}`, 'history')
}

/** GET /api/farms/{farmId}/quality-report */
export function fetchQualityReport(farmId: string): Promise<QualityReport> {
  return getJson(`/api/farms/${farmId}/quality-report`, 'quality-report')
}

/** GET /api/simulations/{runId}/lineage */
export function fetchRunLineage(runId: string): Promise<RunLineage> {
  return getJson(`/api/simulations/${runId}/lineage`, 'lineage')
}

/** GET /api/control-events/{eventId}/lineage */
export function fetchEventLineage(eventId: string): Promise<EventLineage> {
  return getJson(`/api/control-events/${eventId}/lineage`, 'event-lineage')
}

/** GET /api/simulations/{runId}/dataset */
export function exportReplayDataset(runId: string): Promise<ReplayDataset> {
  return getJson(`/api/simulations/${runId}/dataset`, 'dataset')
}

/** POST /api/simulations/replay */
export function importReplayDataset(dataset: ReplayDataset): Promise<SimulationRunOut> {
  return postJson('/api/simulations/replay', { dataset }, 'import')
}

/** POST /api/simulations/{runId}/replay/run */
export function runReplay(runId: string): Promise<ReplayRunResult> {
  return postJson(`/api/simulations/${runId}/replay/run`, {}, 'replay')
}

/** GET /api/simulations/{runId}/replay/compare */
export function fetchReplayCompare(runId: string): Promise<ReplayCompare> {
  return getJson(`/api/simulations/${runId}/replay/compare`, 'compare')
}
