/**
 * 관제 세션 오케스트레이터 (5단계 Day 17~18).
 *
 * =============================================================================
 * 부트 플로우
 * -----------------------------------------------------------------------------
 * 1) REST snapshot 적용 (상태 + stream_sequence + sensors/actuators)
 * 2) REST events → 타임라인 (Day 18)
 * 3) WebSocket 연결
 * 4) connection.ready → lastSequence 재확인
 * 5) 본 이벤트 → sequence 판정 + KPI ring / 로컬 타임라인
 *
 * 재연결·갭: snapshot(+events) 재조회로 latest 정렬.
 *
 * Day 21: 센서 품질(health)은 WS 이벤트가 없어 REST 주기 조회한다.
 * stale 은 "새 값이 안 오는 것"이라 이벤트 기반으로는 감지할 수 없다.
 *
 * Day 22: 고장 이력과 제어 이벤트(품질 차단 기록 포함)도 같은 주기로 갱신한다.
 */

import {
  fetchFarmEvents,
  fetchFarmSnapshot,
  fetchSensorHealth,
} from '../api/farms'
import { fetchFarmFaults } from '../api/faults'
import { FarmRealtimeSocket, type SocketStatus } from './farmSocket'
import type { EventEnvelope } from './envelope'
import {
  decideConnectionReady,
  decideEventSequence,
} from './sequence'
import { useRealtimeStore } from '../store/realtimeStore'

let socket: FarmRealtimeSocket | null = null
let activeFarmId: string | null = null
/** 갭 복구 중 중복 snapshot 요청 방지 */
let recovering = false
let healthTimer: ReturnType<typeof setInterval> | null = null
let healthInFlight = false

const HEALTH_POLL_MS = 5000

/** 센서 품질·고장 이력·제어 이벤트 재조회. 고장 주입/해제 직후에도 호출한다. */
export async function reloadSensorPanels(): Promise<void> {
  const farmId = activeFarmId
  if (!farmId || healthInFlight) return
  healthInFlight = true
  try {
    const [health, faults] = await Promise.allSettled([
      fetchSensorHealth(farmId),
      fetchFarmFaults(farmId),
    ])
    if (farmId !== activeFarmId) return
    const store = useRealtimeStore.getState()
    // 품질·고장 패널은 보조 — 실패해도 세션을 깨지 않는다
    if (health.status === 'fulfilled') store.setSensorHealth(health.value)
    if (faults.status === 'fulfilled') store.setFaults(faults.value)
    await reloadControlEvents()
  } finally {
    healthInFlight = false
  }
}

async function reloadControlEvents(): Promise<void> {
  if (!activeFarmId) return
  try {
    const events = await fetchFarmEvents(activeFarmId, 50)
    useRealtimeStore.getState().setControlEvents(events)
  } catch {
    // 타임라인은 보조 — 실패해도 세션을 깨지 않는다
  }
}

async function reloadSnapshot(reason: string): Promise<void> {
  if (!activeFarmId || recovering) return
  recovering = true
  const store = useRealtimeStore.getState()
  store.setRecovering(true)
  store.markStale()
  try {
    const snapshot = await fetchFarmSnapshot(activeFarmId)
    useRealtimeStore.getState().applySnapshot(snapshot)
    void reloadSensorPanels()
  } catch (error) {
    const message =
      error instanceof Error ? error.message : `snapshot failed (${reason})`
    useRealtimeStore.getState().setError(message)
  } finally {
    recovering = false
    useRealtimeStore.getState().setRecovering(false)
  }
}

function handleEnvelope(envelope: EventEnvelope): void {
  const store = useRealtimeStore.getState()

  if (envelope.event_type === 'connection.ready') {
    const last =
      typeof envelope.payload.last_sequence === 'number'
        ? envelope.payload.last_sequence
        : envelope.sequence
    const decision = decideConnectionReady(last)
    if (decision.kind === 'ready' && decision.lastSequence > store.lastSequence) {
      void reloadSnapshot('connection.ready ahead')
      return
    }
    if (decision.kind === 'ready') {
      store.setLastSequence(decision.lastSequence)
    }
    return
  }

  const decision = decideEventSequence(store.lastSequence, envelope.sequence)
  if (decision.kind === 'duplicate') {
    return
  }
  if (decision.kind === 'gap') {
    void reloadSnapshot(
      `sequence gap expected=${decision.expected} got=${decision.got}`,
    )
    return
  }
  if (decision.kind !== 'apply') {
    return
  }

  if (envelope.event_type === 'farm_state.updated') {
    store.applyFarmStatePayload(envelope.payload, decision.nextLast)
    return
  }
  if (envelope.event_type === 'simulation.status') {
    store.applySimulationStatusPayload(envelope.payload, decision.nextLast)
    return
  }
  if (envelope.event_type === 'actuator.updated') {
    store.applyActuatorUpdatedPayload(envelope.payload, decision.nextLast)
  }
}

function handleStatus(status: SocketStatus): void {
  useRealtimeStore.getState().setSocketStatus(status)
  if (status === 'connected' && activeFarmId) {
    void reloadSnapshot('ws reconnected')
  }
}

/**
 * farm 관제 세션 시작.
 * 이미 다른 farm 이 있으면 교체한다.
 */
export async function startFarmRealtimeSession(farmId: string): Promise<void> {
  stopFarmRealtimeSession()
  activeFarmId = farmId
  useRealtimeStore.getState().setFarmId(farmId)
  useRealtimeStore.getState().setSensorHealth(null)
  useRealtimeStore.getState().setFaults(null)

  await reloadSnapshot('boot')
  healthTimer = setInterval(() => void reloadSensorPanels(), HEALTH_POLL_MS)

  socket = new FarmRealtimeSocket({
    onStatus: handleStatus,
    onEnvelope: handleEnvelope,
    onRawError: (message) => useRealtimeStore.getState().setError(message),
  })
  socket.start(farmId)
}

export function stopFarmRealtimeSession(): void {
  activeFarmId = null
  recovering = false
  if (healthTimer) clearInterval(healthTimer)
  healthTimer = null
  socket?.stop()
  socket = null
}
