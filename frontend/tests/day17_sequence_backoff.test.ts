/**
 * Day 17 — sequence 판정·backoff 단위 테스트.
 *
 * Vitest. DB/브라우저 없이 복구 규칙을 고정한다.
 */
import { describe, expect, it } from 'vitest'

import { nextBackoffMs } from '../src/realtime/backoff'
import {
  decideConnectionReady,
  decideEventSequence,
} from '../src/realtime/sequence'

describe('decideEventSequence', () => {
  it('applies monotonic next sequence', () => {
    expect(decideEventSequence(3, 4)).toEqual({ kind: 'apply', nextLast: 4 })
  })

  it('ignores duplicates and older sequences', () => {
    expect(decideEventSequence(5, 5)).toEqual({ kind: 'duplicate' })
    expect(decideEventSequence(5, 2)).toEqual({ kind: 'duplicate' })
  })

  it('detects gaps for snapshot recovery', () => {
    expect(decideEventSequence(2, 5)).toEqual({
      kind: 'gap',
      expected: 3,
      got: 5,
    })
  })

  it('treats first event after empty stream as apply from 0', () => {
    expect(decideEventSequence(0, 1)).toEqual({ kind: 'apply', nextLast: 1 })
  })
})

describe('decideConnectionReady', () => {
  it('sets baseline without implying a gap by itself', () => {
    expect(decideConnectionReady(7)).toEqual({
      kind: 'ready',
      lastSequence: 7,
    })
  })
})

describe('nextBackoffMs', () => {
  it('grows exponentially and caps at max', () => {
    expect(nextBackoffMs(0)).toBe(500)
    expect(nextBackoffMs(1)).toBe(1000)
    expect(nextBackoffMs(2)).toBe(2000)
    expect(nextBackoffMs(10)).toBe(15_000)
  })
})
