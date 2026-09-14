/**
 * 관제 실시간 Zustand 스토어 (5단계 Day 17).
 *
 * =============================================================================
 * 책임
 * -----------------------------------------------------------------------------
 * - REST snapshot 으로 기준 상태 적재
 * - WS envelope 증분 적용 (sequence 판정은 session 이 한 뒤 apply*)
 * - 연결 상태·stale·lastSequence 표시용 필드
 *
 * Day 18 차트/패널은 이 스토어의 state·actuators 를 구독하면 된다.
 */

import { create } from 'zustand'

import type { FarmSnapshot, FarmStateSnapshot } from '../api/farms'
import type { SocketStatus } from '../realtime/farmSocket'

export type RealtimeStore = {
  farmId: string | null
  socketStatus: SocketStatus
  /** 확정된 마지막 WS sequence (snapshot.stream_sequence 또는 적용 이벤트) */
  lastSequence: number
  /**
   * true 이면 표시 데이터가 스트림과 어긋났을 수 있음
   * (갭 감지 직후 ~ snapshot 복구 완료 전)
   */
  stale: boolean
  snapshot: FarmSnapshot | null
  state: FarmStateSnapshot | null
  simulationStatus: string | null
  lastError: string | null
  recovering: boolean

  setFarmId: (farmId: string) => void
  setSocketStatus: (status: SocketStatus) => void
  setError: (message: string | null) => void
  setRecovering: (value: boolean) => void
  markStale: () => void
  applySnapshot: (snapshot: FarmSnapshot) => void
  applyFarmStatePayload: (payload: Record<string, unknown>, sequence: number) => void
  applySimulationStatusPayload: (
    payload: Record<string, unknown>,
    sequence: number,
  ) => void
  setLastSequence: (sequence: number) => void
}

function numberField(
  payload: Record<string, unknown>,
  key: string,
): number | undefined {
  const value = payload[key]
  return typeof value === 'number' ? value : undefined
}

export const useRealtimeStore = create<RealtimeStore>((set) => ({
  farmId: null,
  socketStatus: 'idle',
  lastSequence: 0,
  stale: false,
  snapshot: null,
  state: null,
  simulationStatus: null,
  lastError: null,
  recovering: false,

  setFarmId: (farmId) => set({ farmId }),

  setSocketStatus: (socketStatus) => set({ socketStatus }),

  setError: (lastError) => set({ lastError }),

  setRecovering: (recovering) => set({ recovering }),

  markStale: () => set({ stale: true }),

  setLastSequence: (lastSequence) => set({ lastSequence }),

  applySnapshot: (snapshot) =>
    set({
      snapshot,
      state: snapshot.state,
      lastSequence: snapshot.stream_sequence,
      stale: false,
      recovering: false,
      lastError: null,
    }),

  applyFarmStatePayload: (payload, sequence) =>
    set((current) => {
      const base = current.state
      const next: FarmStateSnapshot = {
        id: typeof payload.run_id === 'string' ? (base?.id ?? payload.run_id) : (base?.id ?? ''),
        farm_id: current.farmId ?? base?.farm_id ?? '',
        room_id: base?.room_id ?? '',
        version: numberField(payload, 'farm_state_version') ?? base?.version ?? 0,
        temperature_c:
          numberField(payload, 'temperature_c') ?? base?.temperature_c ?? 0,
        humidity_pct: numberField(payload, 'humidity_pct') ?? base?.humidity_pct ?? 0,
        co2_ppm: numberField(payload, 'co2_ppm') ?? base?.co2_ppm ?? 0,
        substrate_moisture_pct:
          numberField(payload, 'substrate_moisture_pct') ??
          base?.substrate_moisture_pct ??
          0,
        ppfd_umol: numberField(payload, 'ppfd_umol') ?? base?.ppfd_umol ?? 0,
        simulation_time:
          numberField(payload, 'simulation_time_seconds') ??
          base?.simulation_time ??
          0,
        updated_at: base?.updated_at ?? new Date().toISOString(),
      }
      return {
        state: next,
        lastSequence: sequence,
        stale: false,
      }
    }),

  applySimulationStatusPayload: (payload, sequence) =>
    set({
      simulationStatus:
        typeof payload.status === 'string' ? payload.status : null,
      lastSequence: sequence,
      stale: false,
    }),
}))
