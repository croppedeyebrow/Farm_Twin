/**
 * 랙/거터 레이아웃 상수 (딸기·센서 배치 공유).
 */

/** @deprecated 구 수직 선반 — Rack.tsx 호환용 */
export const SHELF_HEIGHTS = [0.45, 1.05, 1.65, 2.25] as const

/** 현수 거터 높이 (바닥~거터 중심, ≈ 허리 높이) */
export const GUTTER_HEIGHT = 1.05

/** 기본 거터 길이 (Z) */
export const GUTTER_LENGTH = 9.5

/** 딸기 열 X 위치 (통로를 사이에 두고 평행) */
export const STRAWBERRY_ROW_X = [-1.15, 1.15, 3.35] as const
