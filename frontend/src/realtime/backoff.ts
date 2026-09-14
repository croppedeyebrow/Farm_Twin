/**
 * WebSocket 재연결 exponential backoff (5단계 Day 17).
 *
 * =============================================================================
 * 정책
 * -----------------------------------------------------------------------------
 * attempt 0 → initialMs
 * attempt 1 → initialMs * factor
 * … cap 이 maxMs
 *
 * 연결 성공 시 attempt 를 0 으로 리셋한다 (farmSocket).
 * 무한 재시도 — 관제 화면은 끊겨도 복구를 포기하지 않는다.
 *
 * 기본값: 500ms → 1s → 2s → … → 15s
 */

export type BackoffOptions = {
  initialMs?: number
  factor?: number
  maxMs?: number
}

export const DEFAULT_BACKOFF: Required<BackoffOptions> = {
  initialMs: 500,
  factor: 2,
  maxMs: 15_000,
}

/**
 * 이번 재연결까지 기다릴 밀리초.
 *
 * @param attempt 실패 횟수 (0 = 첫 재시도)
 */
export function nextBackoffMs(
  attempt: number,
  options: BackoffOptions = {},
): number {
  const { initialMs, factor, maxMs } = { ...DEFAULT_BACKOFF, ...options }
  const safeAttempt = Math.max(0, attempt)
  const raw = initialMs * factor ** safeAttempt
  return Math.min(maxMs, Math.round(raw))
}
