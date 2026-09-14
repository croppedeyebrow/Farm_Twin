/**
 * 관제 세션 오케스트레이터 (5단계 Day 17).
 *
 * =============================================================================
 * 부트 플로우
 * -----------------------------------------------------------------------------
 * 1) REST snapshot 적용 (상태 + stream_sequence)
 * 2) WebSocket 연결
 * 3) connection.ready → lastSequence 재확인
 * 4) 본 이벤트 → sequence 판정
 *      apply     → store 증분
 *      duplicate → 무시
 *      gap       → stale + snapshot 재조회 + (소켓은 유지, 기준만 재설정)
 *
 * 재연결
 * ------
 * 소켓 onclose → FarmRealtimeSocket 이 backoff 재연결.
 * 다시 open 되면 connection.ready 가 오고, 필요 시 snapshot 을 다시 맞춘다.
 * (단절 동안 놓친 이벤트는 서버 replay 가 없으므로 snapshot 이 권위)
 *
 * 새로고침
 * --------
 * 페이지 로드 = 위 부트 플로우와 동일 → Day 17 테스트 "브라우저 새로고침 복구".
 */

import { fetchFarmSnapshot } from '../api/farms'
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

async function reloadSnapshot(reason: string): Promise<void> {
  if (!activeFarmId || recovering) return
  recovering = true
  const store = useRealtimeStore.getState()
  store.setRecovering(true)
  store.markStale()
  try {
    const snapshot = await fetchFarmSnapshot(activeFarmId)
    useRealtimeStore.getState().applySnapshot(snapshot)
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
    // ready: 서버 기준이 클라보다 앞서 있으면 snapshot 으로 맞춤
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

  // apply
  if (envelope.event_type === 'farm_state.updated') {
    store.applyFarmStatePayload(envelope.payload, decision.nextLast)
    return
  }
  if (envelope.event_type === 'simulation.status') {
    store.applySimulationStatusPayload(envelope.payload, decision.nextLast)
  }
}

function handleStatus(status: SocketStatus): void {
  useRealtimeStore.getState().setSocketStatus(status)
  // 재연결 성공 직후 단절 구간 누락을 snapshot 으로 메운다
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

  await reloadSnapshot('boot')

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
  socket?.stop()
  socket = null
}
