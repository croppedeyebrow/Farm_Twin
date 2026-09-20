/**
 * 다중 아치(멀티스팬) 온실 외피·골조·기초.
 *
 * 레퍼런스: docs/refs/greenhouse-exterior.jpg
 * - 고딕형 아치 지붕 × SPAN_COUNT
 * - 아연도금 파이프 골조 + 반투명 필름
 * - 콘크리트 블록 기초 + 하단 검정 스커트
 * - 박공면 환기창 · 일부 불투명 백색 패널
 *
 * CAD 정밀 복제가 아니라 관제용 반복 모듈로 외관 인지도를 높인다.
 */

import { useMemo } from 'react'
import { DoubleSide } from 'three'

/** 스팬(베이) 개수 — 사진의 연결된 아치 열 */
export const SPAN_COUNT = 3
/** 한 스팬 폭 (월드 유닛 ≈ m) */
export const SPAN_WIDTH = 4.2
/** 온실 길이 (Z) */
export const HALL_DEPTH = 12
/** 측벽 높이 (아치 시작점) */
export const EAVES_HEIGHT = 2.55
/** 아치 꼭대기 높이 */
export const RIDGE_HEIGHT = 4.35

const HALL_WIDTH = SPAN_COUNT * SPAN_WIDTH
const Z0 = -HALL_DEPTH / 2 + 0.6
const Z1 = HALL_DEPTH / 2 + 0.6

const FRAME = '#8a939c'
const FRAME_DARK = '#6b737c'
const FILM = '#e8f2f8'
const FOUNDATION = '#b8b8b4'
const SKIRT = '#1a1a1a'
const WHITE_PANEL = '#f5f5f5'

/** 고딕 아치 단면 점 (로컬 x: -halfW..halfW, y: 0..ridge) */
function gothicArchPoints(
  halfW: number,
  eavesY: number,
  ridgeY: number,
  segments = 18,
): Array<[number, number]> {
  const pts: Array<[number, number]> = []
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments // 0..1 left → right
    const x = -halfW + t * halfW * 2
    // 뾰족한 고딕: 두 원호가 중앙에서 만남
    const nx = Math.abs(x) / halfW // 0 center → 1 edge
    const arch = Math.pow(1 - nx, 0.72)
    const y = eavesY + (ridgeY - eavesY) * arch
    pts.push([x, y])
  }
  return pts
}

/** 아치 리브: 곡선 따라 짧은 실린더 체인 */
function ArchRib({
  spanIndex,
  z,
}: {
  spanIndex: number
  z: number
}) {
  const halfW = SPAN_WIDTH / 2
  const cx = -HALL_WIDTH / 2 + spanIndex * SPAN_WIDTH + halfW
  const pts = useMemo(
    () => gothicArchPoints(halfW, EAVES_HEIGHT, RIDGE_HEIGHT, 16),
    [halfW],
  )

  return (
    <group position={[cx, 0, z]}>
      {pts.slice(0, -1).map((p, i) => {
        const n = pts[i + 1]
        const mx = (p[0] + n[0]) / 2
        const my = (p[1] + n[1]) / 2
        const dx = n[0] - p[0]
        const dy = n[1] - p[1]
        const len = Math.hypot(dx, dy)
        const angle = Math.atan2(dy, dx)
        return (
          <mesh
            key={`rib-${i}`}
            position={[mx, my, 0]}
            rotation={[0, 0, angle]}
          >
            <cylinderGeometry args={[0.028, 0.028, len, 5]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.55}
              roughness={0.35}
            />
          </mesh>
        )
      })}
    </group>
  )
}

/** 스팬 반투명 지붕 필름 (평면 패치 체인) */
function ArchFilm({ spanIndex }: { spanIndex: number }) {
  const halfW = SPAN_WIDTH / 2
  const cx = -HALL_WIDTH / 2 + spanIndex * SPAN_WIDTH + halfW
  const pts = useMemo(
    () => gothicArchPoints(halfW, EAVES_HEIGHT, RIDGE_HEIGHT, 12),
    [halfW],
  )
  const depth = HALL_DEPTH

  return (
    <group position={[cx, 0, (Z0 + Z1) / 2]}>
      {pts.slice(0, -1).map((p, i) => {
        const n = pts[i + 1]
        const mx = (p[0] + n[0]) / 2
        const my = (p[1] + n[1]) / 2
        const dx = n[0] - p[0]
        const dy = n[1] - p[1]
        const w = Math.hypot(dx, dy)
        const angle = Math.atan2(dy, dx)
        return (
          <mesh
            key={`film-${i}`}
            position={[mx, my, 0]}
            rotation={[0, 0, angle - Math.PI / 2]}
          >
            <planeGeometry args={[w * 1.05, depth]} />
            <meshStandardMaterial
              color={FILM}
              transparent
              opacity={0.28}
              roughness={0.15}
              metalness={0.05}
              side={DoubleSide}
              depthWrite={false}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function Foundation() {
  const blockW = 0.55
  const blockH = 0.42
  const cols = Math.ceil(HALL_WIDTH / blockW)
  const blocks: Array<[number, number, number]> = []
  for (let i = 0; i < cols; i += 1) {
    const x = -HALL_WIDTH / 2 + blockW / 2 + i * blockW
    blocks.push([x, -blockH / 2, Z0 - 0.08])
    blocks.push([x, -blockH / 2, Z1 + 0.08])
  }
  // 측면
  const rows = Math.ceil(HALL_DEPTH / blockW)
  for (let i = 0; i < rows; i += 1) {
    const z = Z0 + blockW / 2 + i * blockW
    blocks.push([-HALL_WIDTH / 2 - 0.08, -blockH / 2, z])
    blocks.push([HALL_WIDTH / 2 + 0.08, -blockH / 2, z])
  }

  return (
    <group>
      {blocks.map((pos, i) => (
        <mesh key={`blk-${i}`} position={pos}>
          <boxGeometry args={[blockW * 0.96, blockH, blockW * 0.96]} />
          <meshStandardMaterial color={FOUNDATION} roughness={0.92} />
        </mesh>
      ))}
      {/* 하단 검정 스커트 */}
      <mesh position={[0, 0.06, (Z0 + Z1) / 2]}>
        <boxGeometry args={[HALL_WIDTH + 0.2, 0.12, HALL_DEPTH + 0.25]} />
        <meshStandardMaterial color={SKIRT} roughness={0.8} />
      </mesh>
    </group>
  )
}

function EndWall({ z, flip }: { z: number; flip?: boolean }) {
  const vents = Array.from({ length: SPAN_COUNT }, (_, i) => {
    const halfW = SPAN_WIDTH / 2
    const cx = -HALL_WIDTH / 2 + i * SPAN_WIDTH + halfW
    return (
      <mesh key={`vent-${i}`} position={[cx, RIDGE_HEIGHT - 0.55, 0]}>
        <boxGeometry args={[0.55, 0.45, 0.08]} />
        <meshStandardMaterial color="#4a5560" metalness={0.3} roughness={0.5} />
      </mesh>
    )
  })

  return (
    <group position={[0, 0, z]} rotation={[0, flip ? Math.PI : 0, 0]}>
      {/* 반투명 박공 면 — 스팬별 대략적 채움 */}
      {Array.from({ length: SPAN_COUNT }, (_, i) => {
        const halfW = SPAN_WIDTH / 2
        const cx = -HALL_WIDTH / 2 + i * SPAN_WIDTH + halfW
        return (
          <mesh key={`gable-${i}`} position={[cx, EAVES_HEIGHT / 2 + 0.2, 0]}>
            <planeGeometry args={[SPAN_WIDTH * 0.98, EAVES_HEIGHT + 0.4]} />
            <meshStandardMaterial
              color={FILM}
              transparent
              opacity={0.22}
              side={DoubleSide}
              depthWrite={false}
            />
          </mesh>
        )
      })}
      {/* 백색 불투명 하부 패널 (사진의 흰 구간) */}
      <mesh position={[-SPAN_WIDTH * 0.35, 0.85, 0.02]}>
        <boxGeometry args={[SPAN_WIDTH * 1.15, 1.7, 0.06]} />
        <meshStandardMaterial color={WHITE_PANEL} roughness={0.75} />
      </mesh>
      {vents}
      {/* 골조 수직·수평 */}
      {Array.from({ length: SPAN_COUNT + 1 }, (_, i) => {
        const x = -HALL_WIDTH / 2 + i * SPAN_WIDTH
        return (
          <mesh key={`col-${i}`} position={[x, EAVES_HEIGHT / 2, 0]}>
            <cylinderGeometry args={[0.04, 0.04, EAVES_HEIGHT, 6]} />
            <meshStandardMaterial
              color={FRAME_DARK}
              metalness={0.5}
              roughness={0.4}
            />
          </mesh>
        )
      })}
    </group>
  )
}

/** 천장 파이프 그리드 (내부 사진의 격자) */
export function CeilingPipeGrid() {
  const beamsX: number[] = []
  for (let x = -HALL_WIDTH / 2 + 0.5; x <= HALL_WIDTH / 2 - 0.5; x += 1.05) {
    beamsX.push(x)
  }
  const beamsZ: number[] = []
  for (let z = Z0 + 0.8; z <= Z1 - 0.8; z += 1.2) {
    beamsZ.push(z)
  }
  const y = RIDGE_HEIGHT - 0.85

  return (
    <group>
      {beamsX.map((x) => (
        <mesh
          key={`px-${x}`}
          position={[x, y, (Z0 + Z1) / 2]}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <cylinderGeometry args={[0.022, 0.022, HALL_DEPTH - 1.2, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.6}
            roughness={0.35}
          />
        </mesh>
      ))}
      {beamsZ.map((z) => (
        <mesh
          key={`pz-${z}`}
          position={[0, y, z]}
          rotation={[0, 0, Math.PI / 2]}
        >
          <cylinderGeometry args={[0.02, 0.02, HALL_WIDTH - 0.8, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.6}
            roughness={0.35}
          />
        </mesh>
      ))}
      {/* 오버헤드 조명 박스 */}
      {beamsZ
        .filter((_, i) => i % 2 === 0)
        .map((z) =>
          [-3.5, 0, 3.5].map((x) => (
            <mesh key={`lamp-${x}-${z}`} position={[x, y - 0.15, z]}>
              <boxGeometry args={[0.55, 0.08, 0.22]} />
              <meshStandardMaterial
                color="#f8f9fa"
                emissive="#fff8e7"
                emissiveIntensity={0.85}
              />
            </mesh>
          )),
        )}
    </group>
  )
}

function SideWall({ x }: { x: number }) {
  return (
    <group>
      <mesh
        position={[x, EAVES_HEIGHT / 2, (Z0 + Z1) / 2]}
        rotation={[0, Math.PI / 2, 0]}
      >
        <planeGeometry args={[HALL_DEPTH, EAVES_HEIGHT]} />
        <meshStandardMaterial
          color={FILM}
          transparent
          opacity={0.2}
          side={DoubleSide}
          depthWrite={false}
        />
      </mesh>
      {/* 세로 지주 */}
      {Array.from({ length: 7 }, (_, i) => {
        const z = Z0 + 0.5 + i * ((HALL_DEPTH - 1) / 6)
        return (
          <mesh key={`sw-${z}`} position={[x, EAVES_HEIGHT / 2, z]}>
            <cylinderGeometry args={[0.035, 0.035, EAVES_HEIGHT, 5]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.5}
              roughness={0.4}
            />
          </mesh>
        )
      })}
    </group>
  )
}

export function GreenhouseShell() {
  const ribZs = useMemo(() => {
    const zs: number[] = []
    for (let z = Z0 + 0.4; z <= Z1 - 0.4; z += 1.35) zs.push(z)
    return zs
  }, [])

  const columns = useMemo(() => {
    const items: Array<[number, number, number]> = []
    for (let s = 0; s <= SPAN_COUNT; s += 1) {
      const x = -HALL_WIDTH / 2 + s * SPAN_WIDTH
      for (const z of ribZs) {
        items.push([x, EAVES_HEIGHT / 2, z])
      }
    }
    return items
  }, [ribZs])

  return (
    <group>
      {/* 흰 바닥 시트 (내부 레퍼런스) */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.01, (Z0 + Z1) / 2]}
        receiveShadow
      >
        <planeGeometry args={[HALL_WIDTH - 0.3, HALL_DEPTH - 0.4]} />
        <meshStandardMaterial color="#f7f7f5" roughness={0.55} />
      </mesh>

      <Foundation />
      <SideWall x={-HALL_WIDTH / 2} />
      <SideWall x={HALL_WIDTH / 2} />
      <EndWall z={Z0} />
      <EndWall z={Z1} flip />

      {Array.from({ length: SPAN_COUNT }, (_, s) => (
        <group key={`span-${s}`}>
          <ArchFilm spanIndex={s} />
          {ribZs.map((z) => (
            <ArchRib key={`ar-${s}-${z}`} spanIndex={s} z={z} />
          ))}
        </group>
      ))}

      {columns.map((pos, i) => (
        <mesh key={`col-${i}`} position={pos}>
          <cylinderGeometry args={[0.05, 0.05, EAVES_HEIGHT, 6]} />
          <meshStandardMaterial
            color={FRAME_DARK}
            metalness={0.55}
            roughness={0.38}
          />
        </mesh>
      ))}

      {/* 처마 가로 퍼린 */}
      {Array.from({ length: SPAN_COUNT + 1 }, (_, s) => {
        const x = -HALL_WIDTH / 2 + s * SPAN_WIDTH
        return (
          <mesh
            key={`eave-${s}`}
            position={[x, EAVES_HEIGHT, (Z0 + Z1) / 2]}
            rotation={[Math.PI / 2, 0, 0]}
          >
            <cylinderGeometry args={[0.03, 0.03, HALL_DEPTH, 5]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.5}
              roughness={0.4}
            />
          </mesh>
        )
      })}

      <CeilingPipeGrid />
    </group>
  )
}
