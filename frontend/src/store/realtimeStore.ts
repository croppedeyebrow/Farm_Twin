/**
 * 관제 실시간 Zustand 스토어 (5단계 Day 17~18).
 *
 * =============================================================================
 * Day 17
 * -----------------------------------------------------------------------------
 * - REST snapshot 기준 상태 + WS 증분
 * - 연결·sequence·stale
 *
 * Day 18
 * -----------------------------------------------------------------------------
 * - kpiHistory: 참값 ring buffer → 시계열 차트
 * - sensors/actuators: 상세 패널 선택
 * - timeline: REST 제어 이벤트 + 로컬 스트림 이벤트
 * - selectedSensorId / selectedActuatorId / chartMetric: Day 19 3D↔차트 연동
 */

import { create } from 'zustand'

import type {
  ActuatorSummary,
  ControlEventOut,
  FarmSnapshot,
  FarmStateSnapshot,
  SensorSummary,
} from '../api/farms'
import type { SocketStatus } from '../realtime/farmSocket'
import {
  KPI_HISTORY_CAPACITY,
  pushKpiSample,
  sampleFromState,
  type KpiSample,
} from '../realtime/history'
import type { SensorMetricKey } from '../scene/statusColors'

/** 타임라인에 보이는 한 줄 (REST 또는 로컬 파생) */
export type TimelineEntry = {
  id: string
  kind: 'control' | 'simulation' | 'state'
  title: string
  detail: string
  simulation_time: number
  recorded_at: string
}

export type RealtimeStore = {
  farmId: string | null
  socketStatus: SocketStatus
  lastSequence: number
  stale: boolean
  snapshot: FarmSnapshot | null
  state: FarmStateSnapshot | null
  sensors: SensorSummary[]
  actuators: ActuatorSummary[]
  kpiHistory: KpiSample[]
  timeline: TimelineEntry[]
  selectedSensorId: string | null
  selectedActuatorId: string | null
  /** Day 19: 3D 센서 클릭 시 시계열 메트릭 */
  chartMetric: SensorMetricKey
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
  applyActuatorUpdatedPayload: (
    payload: Record<string, unknown>,
    sequence: number,
  ) => void
  setLastSequence: (sequence: number) => void
  setControlEvents: (events: ControlEventOut[]) => void
  selectSensor: (id: string | null) => void
  selectActuator: (id: string | null) => void
  setChartMetric: (metric: SensorMetricKey) => void
  pushTimeline: (entry: TimelineEntry) => void
}

function numberField(
  payload: Record<string, unknown>,
  key: string,
): number | undefined {
  const value = payload[key]
  return typeof value === 'number' ? value : undefined
}

function controlEventsToTimeline(events: ControlEventOut[]): TimelineEntry[] {
  return events.map((event) => ({
    id: `control-${event.id}`,
    kind: 'control' as const,
    title: `${event.event_type}${event.actuator_code ? ` · ${event.actuator_code}` : ''}`,
    detail:
      event.message ??
      `${event.desired_mode ?? '?'} @ ${(event.actual_output_ratio ?? 0).toFixed(2)}`,
    simulation_time: event.simulation_time,
    recorded_at: event.recorded_at,
  }))
}

const TIMELINE_CAPACITY = 80

function mergeTimeline(
  existing: TimelineEntry[],
  incoming: TimelineEntry[],
): TimelineEntry[] {
  const byId = new Map<string, TimelineEntry>()
  for (const item of [...incoming, ...existing]) {
    byId.set(item.id, item)
  }
  return [...byId.values()]
    .sort((a, b) => b.simulation_time - a.simulation_time)
    .slice(0, TIMELINE_CAPACITY)
}

export const useRealtimeStore = create<RealtimeStore>((set) => ({
  farmId: null,
  socketStatus: 'idle',
  lastSequence: 0,
  stale: false,
  snapshot: null,
  state: null,
  sensors: [],
  actuators: [],
  kpiHistory: [],
  timeline: [],
  selectedSensorId: null,
  selectedActuatorId: null,
  chartMetric: 'temperature_c',
  simulationStatus: null,
  lastError: null,
  recovering: false,

  setFarmId: (farmId) => set({ farmId }),
  setSocketStatus: (socketStatus) => set({ socketStatus }),
  setError: (lastError) => set({ lastError }),
  setRecovering: (recovering) => set({ recovering }),
  markStale: () => set({ stale: true }),
  setLastSequence: (lastSequence) => set({ lastSequence }),

  selectSensor: (selectedSensorId) => set({ selectedSensorId }),
  selectActuator: (selectedActuatorId) => set({ selectedActuatorId }),
  setChartMetric: (chartMetric) => set({ chartMetric }),

  pushTimeline: (entry) =>
    set((current) => ({
      timeline: mergeTimeline(current.timeline, [entry]),
    })),

  setControlEvents: (events) =>
    set((current) => ({
      timeline: mergeTimeline(
        current.timeline.filter((item) => item.kind !== 'control'),
        controlEventsToTimeline(events),
      ),
    })),

  applySnapshot: (snapshot) =>
    set((current) => {
      const history =
        snapshot.state != null
          ? pushKpiSample(current.kpiHistory, sampleFromState(snapshot.state))
          : current.kpiHistory
      return {
        snapshot,
        state: snapshot.state,
        sensors: snapshot.sensors,
        actuators: snapshot.actuators,
        lastSequence: snapshot.stream_sequence,
        kpiHistory: history,
        stale: false,
        recovering: false,
        lastError: null,
      }
    }),

  applyFarmStatePayload: (payload, sequence) =>
    set((current) => {
      const base = current.state
      const next: FarmStateSnapshot = {
        id:
          typeof payload.run_id === 'string'
            ? (base?.id ?? payload.run_id)
            : (base?.id ?? ''),
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
      const entry: TimelineEntry = {
        id: `state-${sequence}`,
        kind: 'state',
        title: 'farm_state.updated',
        detail: `T=${next.temperature_c.toFixed(1)}°C · t=${next.simulation_time.toFixed(0)}s`,
        simulation_time: next.simulation_time,
        recorded_at: new Date().toISOString(),
      }
      return {
        state: next,
        lastSequence: sequence,
        stale: false,
        kpiHistory: pushKpiSample(current.kpiHistory, sampleFromState(next)),
        timeline: mergeTimeline(current.timeline, [entry]),
      }
    }),

  applySimulationStatusPayload: (payload, sequence) =>
    set((current) => {
      const status = typeof payload.status === 'string' ? payload.status : null
      const simTime =
        numberField(payload, 'simulation_time_seconds') ??
        current.state?.simulation_time ??
        0
      const entry: TimelineEntry = {
        id: `sim-${sequence}`,
        kind: 'simulation',
        title: 'simulation.status',
        detail: status ?? 'unknown',
        simulation_time: simTime,
        recorded_at: new Date().toISOString(),
      }
      return {
        simulationStatus: status,
        lastSequence: sequence,
        stale: false,
        timeline: mergeTimeline(current.timeline, [entry]),
      }
    }),

  applyActuatorUpdatedPayload: (payload, sequence) =>
    set((current) => {
      const id = typeof payload.id === 'string' ? payload.id : null
      if (!id) {
        return { lastSequence: sequence, stale: false }
      }
      const nextActuators = current.actuators.map((item) => {
        if (item.id !== id) return item
        return {
          ...item,
          mode: typeof payload.mode === 'string' ? payload.mode : item.mode,
          output_ratio:
            typeof payload.output_ratio === 'number'
              ? payload.output_ratio
              : item.output_ratio,
          code: typeof payload.code === 'string' ? payload.code : item.code,
          name: typeof payload.name === 'string' ? payload.name : item.name,
          actuator_type:
            typeof payload.actuator_type === 'string'
              ? payload.actuator_type
              : item.actuator_type,
        }
      })
      const code =
        typeof payload.code === 'string'
          ? payload.code
          : (nextActuators.find((a) => a.id === id)?.code ?? 'actuator')
      const ratio =
        typeof payload.output_ratio === 'number' ? payload.output_ratio : 0
      const mode = typeof payload.mode === 'string' ? payload.mode : '?'
      const entry: TimelineEntry = {
        id: `actuator-${sequence}`,
        kind: 'control',
        title: `actuator.updated · ${code}`,
        detail: `${mode} @ ${ratio.toFixed(2)}`,
        simulation_time: current.state?.simulation_time ?? 0,
        recorded_at: new Date().toISOString(),
      }
      return {
        actuators: nextActuators,
        lastSequence: sequence,
        stale: false,
        timeline: mergeTimeline(current.timeline, [entry]),
      }
    }),
}))

export { KPI_HISTORY_CAPACITY }
