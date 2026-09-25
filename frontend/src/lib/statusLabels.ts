/** 연결 상태 표시용 공통 라벨 */

export type HealthState = 'loading' | 'ok' | 'error'

export function labelFor(state: HealthState): string {
  if (state === 'loading') return '확인 중'
  if (state === 'ok') return '정상'
  return '실패'
}

export function socketLabel(status: string): string {
  switch (status) {
    case 'connected':
      return '연결됨'
    case 'connecting':
      return '연결 중'
    case 'reconnecting':
      return '재연결 중'
    case 'stopped':
      return '중지'
    default:
      return status
  }
}

export function socketDataState(status: string): HealthState {
  if (status === 'connected') return 'ok'
  if (status === 'reconnecting' || status === 'connecting') return 'loading'
  return 'error'
}
