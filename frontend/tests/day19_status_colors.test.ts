/**
 * Day 19 — 센서 상태 색 임계 단위 테스트.
 */
import { describe, expect, it } from 'vitest'

import {
  metricStatus,
  sensorTypeToMetric,
  STATUS_COLOR,
} from '../src/scene/statusColors'

describe('sensorTypeToMetric', () => {
  it('maps known sensor types', () => {
    expect(sensorTypeToMetric('temperature')).toBe('temperature_c')
    expect(sensorTypeToMetric('ppfd')).toBe('ppfd_umol')
    expect(sensorTypeToMetric('unknown')).toBeNull()
  })
})

describe('metricStatus', () => {
  it('flags stale first', () => {
    expect(metricStatus('temperature_c', 22, { stale: true })).toBe('stale')
  })

  it('classifies temperature bands', () => {
    expect(metricStatus('temperature_c', 22)).toBe('ok')
    expect(metricStatus('temperature_c', 29)).toBe('warn')
    expect(metricStatus('temperature_c', 35)).toBe('danger')
  })

  it('exposes design colors', () => {
    expect(STATUS_COLOR.ok).toMatch(/^#/)
    expect(STATUS_COLOR.danger).toMatch(/^#/)
  })
})
