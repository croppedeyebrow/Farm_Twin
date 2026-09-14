/**
 * Farm REST API 클라이언트 (5단계 Day 17).
 *
 * 경로
 * ----
 * 브라우저: `/api/farms/...`
 * - Vite: proxy 가 `/api` strip → FastAPI `/farms/...`
 * - Compose: Nginx `/api/` strip → 동일
 *
 * Day 17 역할
 * -----------
 * 초기 로딩·재연결·sequence 갭 복구의 **권위 있는 상태**는 항상 REST snapshot.
 * WebSocket 은 그 이후 증분만 적용한다.
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

export type FarmSnapshot = {
  farm: { id: string; site_id: string; code: string; name: string }
  room: { id: string; farm_id: string; code: string; name: string }
  racks: unknown[]
  sensors: unknown[]
  actuators: Array<{
    id: string
    code: string
    name: string
    actuator_type: string
    mode: string
    output_ratio: number
  }>
  state: FarmStateSnapshot | null
  /** Day 17: 이 API 프로세스가 발급한 마지막 WS sequence */
  stream_sequence: number
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
