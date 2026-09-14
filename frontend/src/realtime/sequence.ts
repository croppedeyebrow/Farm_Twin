/**
 * sequence 판정 (5단계 Day 17).
 *
 * =============================================================================
 * 왜 필요한가
 * -----------------------------------------------------------------------------
 * WS 는 at-least-once 에 가깝게 동작할 수 있고, 프록시/재연결 사이
 * 메시지가 빠질 수 있다. 서버는 MVP 에서 replay 버퍼를 두지 않으므로
 * 갭이 나면 REST snapshot 으로 latest 를 다시 맞춘다.
 *
 * 판정 규칙 (본 이벤트: farm_state.updated / simulation.status)
 * -----------------------------------------------------------------------------
 * lastKnown = 클라가 확정한 마지막 sequence (snapshot.stream_sequence 또는
 *            직전 적용 이벤트)
 *
 *   sequence === lastKnown + 1  → apply (정상 증분)
 *   sequence <= lastKnown       → duplicate (무시)
 *   sequence >  lastKnown + 1   → gap (snapshot 복구)
 *
 * connection.ready
 * ----------------
 * sequence 를 올리지 않는다. payload.last_sequence 로 기준만 맞춘다.
 * (백엔드 send_connection_ready 와 동일 계약)
 */

export type SequenceDecision =
  | { kind: 'apply'; nextLast: number }
  | { kind: 'duplicate' }
  | { kind: 'gap'; expected: number; got: number }
  | { kind: 'ready'; lastSequence: number }

/**
 * connection.ready 처리: 스트림 기준점만 설정.
 */
export function decideConnectionReady(lastSequence: number): SequenceDecision {
  return { kind: 'ready', lastSequence }
}

/**
 * 본 이벤트 sequence 판정.
 */
export function decideEventSequence(
  lastKnown: number,
  incoming: number,
): SequenceDecision {
  if (incoming <= lastKnown) {
    return { kind: 'duplicate' }
  }
  if (incoming === lastKnown + 1) {
    return { kind: 'apply', nextLast: incoming }
  }
  return { kind: 'gap', expected: lastKnown + 1, got: incoming }
}
