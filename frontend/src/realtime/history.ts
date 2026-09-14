/**
 * KPI 시계열 ring buffer (5단계 Day 18).
 *
 * =============================================================================
 * 왜 ring buffer 인가
 * -----------------------------------------------------------------------------
 * 프론트엔드 설계 7절: 차트는 고정 길이 버퍼.
 * WS 로 참값이 계속 들어오면 배열이 무한히 커지지 않게 한다.
 *
 * 기본 capacity=120 → 약 1~2초 간격이면 ~2–4분 분량.
 * simulation_time 을 x 축으로 쓰면 가상 시계와 KPI/3D 가 같은 기준을 쓴다.
 */

import type { FarmStateSnapshot } from '../api/farms'

/** 차트에 유지할 최대 샘플 수 */
export const KPI_HISTORY_CAPACITY = 120

export type KpiSample = {
  /** 가상 시계(초) — FarmState.simulation_time */
  simulation_time: number
  temperature_c: number
  humidity_pct: number
  co2_ppm: number
  substrate_moisture_pct: number
  ppfd_umol: number
}

export function sampleFromState(state: FarmStateSnapshot): KpiSample {
  return {
    simulation_time: state.simulation_time,
    temperature_c: state.temperature_c,
    humidity_pct: state.humidity_pct,
    co2_ppm: state.co2_ppm,
    substrate_moisture_pct: state.substrate_moisture_pct,
    ppfd_umol: state.ppfd_umol,
  }
}

/**
 * 고정 길이 append. capacity 초과 시 가장 오래된 것부터 버린다.
 */
export function pushRing<T>(buffer: readonly T[], item: T, capacity: number): T[] {
  if (capacity <= 0) return []
  if (buffer.length < capacity) {
    return [...buffer, item]
  }
  return [...buffer.slice(buffer.length - capacity + 1), item]
}

/**
 * 동일 simulation_time 이면 마지막 값으로 교체 (중복 tick 방지).
 */
export function pushKpiSample(
  buffer: readonly KpiSample[],
  sample: KpiSample,
  capacity: number = KPI_HISTORY_CAPACITY,
): KpiSample[] {
  const last = buffer[buffer.length - 1]
  if (last && last.simulation_time === sample.simulation_time) {
    return [...buffer.slice(0, -1), sample]
  }
  return pushRing(buffer, sample, capacity)
}
