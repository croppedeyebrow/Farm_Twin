/**
 * Day 18 — KPI ring buffer 단위 테스트.
 */
import { describe, expect, it } from 'vitest'

import {
  KPI_HISTORY_CAPACITY,
  pushKpiSample,
  pushRing,
  sampleFromState,
} from '../src/realtime/history'

describe('pushRing', () => {
  it('appends until capacity then drops oldest', () => {
    let buf: number[] = []
    for (let i = 1; i <= 5; i += 1) {
      buf = pushRing(buf, i, 3)
    }
    expect(buf).toEqual([3, 4, 5])
  })
})

describe('pushKpiSample', () => {
  it('replaces same simulation_time instead of duplicating', () => {
    const first = {
      simulation_time: 60,
      temperature_c: 22,
      humidity_pct: 50,
      co2_ppm: 400,
      substrate_moisture_pct: 40,
      ppfd_umol: 0,
    }
    const second = { ...first, temperature_c: 23 }
    const buf = pushKpiSample(pushKpiSample([], first, 10), second, 10)
    expect(buf).toHaveLength(1)
    expect(buf[0]?.temperature_c).toBe(23)
  })

  it('respects default capacity constant', () => {
    expect(KPI_HISTORY_CAPACITY).toBeGreaterThan(10)
  })
})

describe('sampleFromState', () => {
  it('maps FarmStateSnapshot fields', () => {
    const sample = sampleFromState({
      id: '1',
      farm_id: '2',
      room_id: '3',
      version: 1,
      temperature_c: 24.5,
      humidity_pct: 55,
      co2_ppm: 800,
      substrate_moisture_pct: 42,
      ppfd_umol: 200,
      simulation_time: 120,
      updated_at: '2026-01-01T00:00:00Z',
    })
    expect(sample.temperature_c).toBe(24.5)
    expect(sample.simulation_time).toBe(120)
  })
})
