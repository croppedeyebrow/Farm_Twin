/**
 * 센서 고장 주입 REST (6단계 Day 22).
 *
 * 주입·해제는 run 단위, 조회는 farm 최신 run 기준.
 * 고장은 측정에만 적용되고 참값(FarmState)은 그대로다.
 */

export type FaultType = 'spike' | 'stuck' | 'dropout'

export type SensorFault = {
  id: string
  simulation_run_id: string
  sensor_id: string
  sensor_code: string
  sensor_type: string
  fault_type: FaultType
  active: boolean
  magnitude: number | null
  stuck_value: number | null
  start_simulation_time: number
  end_simulation_time: number | null
  started_at: string
  cleared_at: string | null
  reason: string | null
  notes: string | null
}

export type FaultList = {
  run_id: string | null
  faults: SensorFault[]
}

export type FaultInjectBody = {
  sensor_id: string
  fault_type: FaultType
  magnitude?: number
  stuck_value?: number
  reason?: string
}

async function errorDetail(response: Response, label: string): Promise<Error> {
  const body = (await response.json().catch(() => null)) as
    | { detail?: unknown }
    | null
  const detail = typeof body?.detail === 'string' ? body.detail : null
  return new Error(detail ?? `${label} ${response.status}`)
}

/** GET /api/farms/{farmId}/faults */
export async function fetchFarmFaults(farmId: string): Promise<FaultList> {
  const response = await fetch(`/api/farms/${farmId}/faults`)
  if (!response.ok) throw await errorDetail(response, 'faults')
  return (await response.json()) as FaultList
}

/** POST /api/simulations/{runId}/faults */
export async function injectFault(
  runId: string,
  body: FaultInjectBody,
): Promise<SensorFault> {
  const response = await fetch(`/api/simulations/${runId}/faults`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await errorDetail(response, 'inject')
  return (await response.json()) as SensorFault
}

/** POST /api/simulations/{runId}/faults/{faultId}/clear */
export async function clearFault(
  runId: string,
  faultId: string,
): Promise<SensorFault> {
  const response = await fetch(
    `/api/simulations/${runId}/faults/${faultId}/clear`,
    { method: 'POST' },
  )
  if (!response.ok) throw await errorDetail(response, 'clear')
  return (await response.json()) as SensorFault
}
