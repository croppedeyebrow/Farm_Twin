/**
 * 농장 WebSocket 클라이언트 (5단계 Day 17).
 *
 * =============================================================================
 * URL
 * -----------------------------------------------------------------------------
 * 브라우저: `ws(s)://{host}/ws/farms/{farmId}`
 * - Vite: `/ws` proxy → backend :8000 (vite.config.ts)
 * - Compose: Nginx `/ws/` Upgrade → FastAPI
 *
 * 수명
 * ----
 * 1) connect
 * 2) onopen → 상태 connected, backoff reset
 * 3) onmessage → 호출측이 envelope parse·sequence 판정
 * 4) onclose/onerror → 의도적 stop 이 아니면 backoff 후 재연결
 *
 * 이 클래스는 snapshot 을 직접 치지 않는다.
 * 재연결·갭 복구 시 snapshot 은 session/store 가 담당한다.
 */

import { nextBackoffMs } from './backoff'
import { parseEnvelope, type EventEnvelope } from './envelope'

export type SocketStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'stopped'

export type FarmSocketHandlers = {
  onStatus?: (status: SocketStatus) => void
  onEnvelope?: (envelope: EventEnvelope) => void
  onRawError?: (message: string) => void
}

function buildWsUrl(farmId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/farms/${farmId}`
}

export class FarmRealtimeSocket {
  private farmId: string | null = null
  private socket: WebSocket | null = null
  private status: SocketStatus = 'idle'
  private attempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  /** stop() 호출 시 true — close 핸들러가 재연결하지 않음 */
  private stopped = false
  private readonly handlers: FarmSocketHandlers

  constructor(handlers: FarmSocketHandlers = {}) {
    this.handlers = handlers
  }

  getStatus(): SocketStatus {
    return this.status
  }

  /**
   * farm 구독 시작. 이미 연결 중이면 먼저 stop 한다.
   */
  start(farmId: string): void {
    this.stop()
    this.stopped = false
    this.farmId = farmId
    this.attempt = 0
    this.open()
  }

  /**
   * 재연결 루프를 끄고 소켓을 닫는다.
   */
  stop(): void {
    this.stopped = true
    this.clearReconnectTimer()
    if (this.socket) {
      this.socket.onopen = null
      this.socket.onmessage = null
      this.socket.onerror = null
      this.socket.onclose = null
      if (
        this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING
      ) {
        this.socket.close()
      }
      this.socket = null
    }
    this.setStatus('stopped')
  }

  private open(): void {
    if (this.stopped || !this.farmId) return

    this.setStatus(this.attempt === 0 ? 'connecting' : 'reconnecting')
    const url = buildWsUrl(this.farmId)
    const socket = new WebSocket(url)
    this.socket = socket

    socket.onopen = () => {
      this.attempt = 0
      this.setStatus('connected')
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const data: unknown = JSON.parse(event.data)
        const envelope = parseEnvelope(data)
        if (envelope === null) {
          this.handlers.onRawError?.('invalid envelope')
          return
        }
        this.handlers.onEnvelope?.(envelope)
      } catch {
        this.handlers.onRawError?.('json parse failed')
      }
    }

    socket.onerror = () => {
      this.handlers.onRawError?.('websocket error')
    }

    socket.onclose = () => {
      this.socket = null
      if (this.stopped) return
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer()
    const delay = nextBackoffMs(this.attempt)
    this.setStatus('reconnecting')
    this.reconnectTimer = setTimeout(() => {
      this.attempt += 1
      this.open()
    }, delay)
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private setStatus(status: SocketStatus): void {
    this.status = status
    this.handlers.onStatus?.(status)
  }
}
