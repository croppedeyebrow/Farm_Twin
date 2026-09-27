/**
 * 랙/거터 레이아웃 상수 (딸기·포도·센서 배치 공유).
 *
 * 하우스 내부: |x| < HALL_WIDTH/2 ≈ 6.6, |z| < ~6.5
 * 벽 밖으로 튀어나오지 않도록 여유를 둔다.
 */

/** @deprecated 구 수직 선반 — Rack.tsx 호환용 */
export const SHELF_HEIGHTS = [0.45, 1.05, 1.65, 2.25] as const

/**
 * 딸기 다단 재배대 거터 높이 (바닥~거터 중심).
 * 단 간격은 작물 높이(≈0.34) + 아래로 늘어진 열매(≈0.13) + 윗단 밑 LED 가 들어가는 최소치.
 */
export const STRAWBERRY_TIER_HEIGHTS = [0.43, 1.05, 1.67] as const

/** 윗단 거터 중심에서 그 아래 LED 바 중심까지 */
export const TIER_LED_DROP = 0.18

/** 대표(가운데) 거터 높이 — 센서 프로브 기준 */
export const GUTTER_HEIGHT = STRAWBERRY_TIER_HEIGHTS[1]

/** 거터 길이 (하우스 깊이 안) */
export const GUTTER_LENGTH = 8.0

/**
 * 딸기 열 X — 중앙~우측 스팬.
 * 우측 벽(≈6.6)에 안 닿게 마지막 열을 안쪽으로.
 */
export const STRAWBERRY_ROW_X = [0.2, 1.6, 3.0, 4.4] as const

/** 포도 폴리터널 반폭 — 배치 간격(2.25)보다 작게 유지 */
export const GRAPE_TUNNEL_HALF_WIDTH = 1.02

/**
 * 포도 터널 배치 (월드 좌표).
 * 좌측 스팬 + 중앙 공백에 추가.
 */
export const GRAPE_CORRIDOR_PLACEMENTS = [
  { position: [-4.45, 0, 0.15] as [number, number, number], label: 'G1' },
  { position: [-2.2, 0, 0.15] as [number, number, number], label: 'G2' },
] as const
