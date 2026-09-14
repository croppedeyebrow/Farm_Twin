/**
 * Farm REST 확장 (5단계 Day 17 snapshot + Day 18 events).
 *
 * 경로
 * ----
 * 브라우저: `/api/farms/...`
 * - Vite: proxy 가 `/api` strip → FastAPI `/farms/...`
 * - Compose: Nginx `/api/` strip → 동일
 *
 * Day 17: snapshot 이 권위 있는 상태
 * Day 18: events 로 제어 타임라인 이력 채움
 */

export type FarmStateSnapshot = {
  id: string
  farm_id: string
  room_id: string
  version: number
  temperature_c: number
  humidity_pct: number
  co2_ppm: number
  substrate_moisture_pct: number
  ppfd_umol: number
  simulation_time: number
  updated_at: string
}

export type SensorSummary = {
  id: string
  room_id: string
  rack_id: string | null
  code: string
  name: string
  sensor_type: string
  unit: string
  model_version: string
}

export type ActuatorSummary = {
  id: string
  code: string
  name: string
  actuator_type: string
  mode: string
  output_ratio: number
}

export type FarmSnapshot = {
  farm: { id: string; site_id: string; code: string; name: string }
  room: { id: string; farm_id: string; code: string; name: string }
  racks: unknown[]
  sensors: SensorSummary[]
  actuators: ActuatorSummary[]
  state: FarmStateSnapshot | null
  /** Day 17: 이 API 프로세스가 발급한 마지막 WS sequence */
  stream_sequence: number
}

export type ControlEventOut = {
  id: string
  event_type: string
  message: string | null
  actual_output_ratio: number | null
  simulation_time: number
  recorded_at: string
  command_id: string
  simulation_run_id: string
  actuator_code: string | null
  actuator_type: string | null
  desired_mode: string | null
  command_status: string | null
}

/**
 * GET /api/farms/{farmId}/snapshot
 *
 * stream_sequence 로 클라 lastSequence 를 맞춘 뒤 WS 증분을 이어간다.
 */
export async function fetchFarmSnapshot(farmId: string): Promise<FarmSnapshot> {
  const response = await fetch(`/api/farms/${farmId}/snapshot`)
  if (!response.ok) {
    throw new Error(`snapshot ${response.status}`)
  }
  return (await response.json()) as FarmSnapshot
}

/**
 * GET /api/farms/{farmId}/events?limit=
 *
 * 제어 Command/Event append-only 이력 (최신순).
 */
export async function fetchFarmEvents(
  farmId: string,
  limit = 50,
): Promise<ControlEventOut[]> {
  const response = await fetch(`/api/farms/${farmId}/events?limit=${limit}`)
  if (!response.ok) {
    throw new Error(`events ${response.status}`)
  }
  return (await response.json()) as ControlEventOut[]
}
