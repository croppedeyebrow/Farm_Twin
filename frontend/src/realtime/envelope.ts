/**
 * WS 이벤트 envelope Zod 계약 (5단계 Day 17).
 *
 * 백엔드 `app.websocket.envelope` (events.v1) 과 필드를 맞춘다.
 * 런타임 검증에 실패하면 메시지를 버리고(로그), 스트림을 오염시키지 않는다.
 */

import { z } from 'zod'

/** 백엔드 EVENT_SCHEMA_VERSION 과 동일 */
export const EVENT_SCHEMA_VERSION = 'events.v1'

export const realtimeEventTypeSchema = z.enum([
  'connection.ready',
  'farm_state.updated',
  'simulation.status',
])

export const eventEnvelopeSchema = z.object({
  event_id: z.string().uuid(),
  event_type: realtimeEventTypeSchema,
  schema_version: z.literal(EVENT_SCHEMA_VERSION),
  farm_id: z.string().uuid(),
  room_id: z.string().uuid().nullable().optional(),
  simulation_run_id: z.string().uuid().nullable().optional(),
  sequence: z.number().int().nonnegative(),
  simulation_time: z.number().nullable().optional(),
  occurred_at: z.string(),
  payload: z.record(z.string(), z.unknown()),
})

export type EventEnvelope = z.infer<typeof eventEnvelopeSchema>
export type RealtimeEventType = z.infer<typeof realtimeEventTypeSchema>

/**
 * 알 수 없는 JSON → envelope 또는 null.
 * null 이면 호출측이 무시한다.
 */
export function parseEnvelope(data: unknown): EventEnvelope | null {
  const parsed = eventEnvelopeSchema.safeParse(data)
  return parsed.success ? parsed.data : null
}
