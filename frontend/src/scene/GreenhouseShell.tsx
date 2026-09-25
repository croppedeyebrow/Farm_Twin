/**
 * 멀티스팬 비닐하우스 외피·골조·기초.
 *
 * 레퍼런스: docs/refs/greenhouse-exterior.jpg
 * ---------------------------------------------------------------------------
 * - 고딕 아치 지붕이 이어진 다중 스팬
 * - 반투명 필름 너머로 보이는 파이프 골조 격자
 * - 박공면 하부 불투명 백색 패널 + 꼭대기 사각 환기창
 * - 콘크리트 블록 기초 + 하단 검정 스커트
 * - 측벽은 수직 후 아치로 이어짐
 */

import { useMemo } from 'react'
import {
  BufferGeometry,
  DoubleSide,
  Float32BufferAttribute,
} from 'three'

export const SPAN_COUNT = 3
export const SPAN_WIDTH = 4.4
export const HALL_DEPTH = 14
/** 측벽 수직부 높이 (아치 시작) */
export const EAVES_HEIGHT = 2.85
/** 아치 마루 높이 */
export const RIDGE_HEIGHT = 4.55

export const HALL_WIDTH = SPAN_COUNT * SPAN_WIDTH
export const HALL_Z0 = -HALL_DEPTH / 2 + 0.4
export const HALL_Z1 = HALL_DEPTH / 2 + 0.4

const Z0 = HALL_Z0
const Z1 = HALL_Z1
const MID_Z = (Z0 + Z1) / 2

const FRAME = '#9aa3ab'
const FRAME_DARK = '#7a848e'
/** 레퍼런스처럼 우유빛 반투명 비닐 */
const VINYL = '#e8eef3'
const FOUNDATION = '#aeb0aa'
const SKIRT = '#141414'
const WHITE_PANEL = '#f7f7f7'
const VENT = '#4d565f'
const GROUND = '#c4b59a'

const vinylMat = {
  color: VINYL,
  transparent: true,
  opacity: 0.52,
  roughness: 0.38,
  metalness: 0.0,
  side: DoubleSide,
  depthWrite: false,
} as const

/** 고딕 아치 (살짝 뾰족) — 레퍼런스 지붕 윤곽 */
function gothicArchPoints(
  halfW: number,
  eavesY: number,
  ridgeY: number,
  segments = 20,
): Array<[number, number]> {
  const pts: Array<[number, number]> = []
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments
    const x = -halfW + t * halfW * 2
    const nx = Math.abs(x) / halfW
    const arch = Math.pow(1 - nx, 0.62)
    const y = eavesY + (ridgeY - eavesY) * arch
    pts.push([x, y])
  }
  return pts
}

/** 아치 곡면을 Z방향으로 한 장으로 밀어 연속 비닐 스킨 생성 (평면 교차 없음) */
function createArchVinylGeometry(
  halfW: number,
  eavesY: number,
  ridgeY: number,
  z0: number,
  z1: number,
  segments = 28,
): BufferGeometry {
  const pts = gothicArchPoints(halfW, eavesY, ridgeY, segments)
  const positions: number[] = []
  const uvs: number[] = []
  const indices: number[] = []

  for (let i = 0; i < pts.length; i += 1) {
    const [x, y] = pts[i]
    positions.push(x, y, z0, x, y, z1)
    const u = i / (pts.length - 1)
    uvs.push(u, 0, u, 1)
  }

  for (let i = 0; i < pts.length - 1; i += 1) {
    const a = i * 2
    const b = a + 1
    const c = a + 2
    const d = a + 3
    indices.push(a, c, b, b, c, d)
  }

  const geo = new BufferGeometry()
  geo.setAttribute('position', new Float32BufferAttribute(positions, 3))
  geo.setAttribute('uv', new Float32BufferAttribute(uvs, 2))
  geo.setIndex(indices)
  geo.computeVertexNormals()
  return geo
}

/** 박공면 고딕 아치 채움 (XY 평면, 교차 없는 단일 메시) */
function createGableVinylGeometry(
  halfW: number,
  eavesY: number,
  ridgeY: number,
  segments = 24,
): BufferGeometry {
  const arch = gothicArchPoints(halfW, eavesY, ridgeY, segments)
  const positions: number[] = []
  const indices: number[] = []

  // 중심(처마선 중앙) + 아치 점들로 팬 삼각형
  positions.push(0, eavesY, 0)
  for (const [x, y] of arch) {
    positions.push(x, y, 0)
  }
  for (let i = 1; i < arch.length; i += 1) {
    indices.push(0, i, i + 1)
  }

  // 처마 아래 수직 벽 사각형
  const left = positions.length / 3
  positions.push(-halfW, 0, 0, -halfW, eavesY, 0, halfW, eavesY, 0, halfW, 0, 0)
  indices.push(left, left + 1, left + 2, left, left + 2, left + 3)

  const geo = new BufferGeometry()
  geo.setAttribute('position', new Float32BufferAttribute(positions, 3))
  geo.setIndex(indices)
  geo.computeVertexNormals()
  return geo
}

function ArchRib({ spanIndex, z }: { spanIndex: number; z: number }) {
  const halfW = SPAN_WIDTH / 2 * 0.97
  const cx = -HALL_WIDTH / 2 + spanIndex * SPAN_WIDTH + SPAN_WIDTH / 2
  const pts = useMemo(
    () => gothicArchPoints(halfW, EAVES_HEIGHT, RIDGE_HEIGHT - 0.06, 18),
    [halfW],
  )

  return (
    <group position={[cx, -0.03, z]}>
      {pts.slice(0, -1).map((p, i) => {
        const n = pts[i + 1]
        const mx = (p[0] + n[0]) / 2
        const my = (p[1] + n[1]) / 2
        const dx = n[0] - p[0]
        const dy = n[1] - p[1]
        const len = Math.hypot(dx, dy)
        const angle = Math.atan2(dy, dx)
        return (
          <mesh key={i} position={[mx, my, 0]} rotation={[0, 0, angle]}>
            <cylinderGeometry args={[0.028, 0.028, len, 6]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.45}
              roughness={0.4}
            />
          </mesh>
        )
      })}
    </group>
  )
}

/** 스팬당 연속 비닐 지붕 — 평면 패치 교차 없음 */
function ArchVinyl({ spanIndex }: { spanIndex: number }) {
  const halfW = SPAN_WIDTH / 2
  const cx = -HALL_WIDTH / 2 + spanIndex * SPAN_WIDTH + halfW
  const geometry = useMemo(
    () =>
      createArchVinylGeometry(
        halfW,
        EAVES_HEIGHT,
        RIDGE_HEIGHT,
        Z0 - 0.05,
        Z1 + 0.05,
        28,
      ),
    [halfW],
  )

  return (
    <mesh geometry={geometry} position={[cx, 0, 0]}>
      <meshStandardMaterial {...vinylMat} />
    </mesh>
  )
}

/** 스팬 사이 골(거터) 라인 */
function ValleyGutters() {
  return (
    <group>
      {Array.from({ length: SPAN_COUNT - 1 }, (_, i) => {
        const x = -HALL_WIDTH / 2 + (i + 1) * SPAN_WIDTH
        return (
          <mesh key={i} position={[x, EAVES_HEIGHT - 0.04, MID_Z]}>
            <boxGeometry args={[0.12, 0.06, HALL_DEPTH + 0.2]} />
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

function Foundation() {
  const blockW = 0.48
  const blockH = 0.5
  const blocks: Array<[number, number, number]> = []
  const cols = Math.ceil((HALL_WIDTH + 0.4) / blockW)
  for (let i = 0; i < cols; i += 1) {
    const x = -HALL_WIDTH / 2 - 0.1 + blockW / 2 + i * blockW
    blocks.push([x, -blockH / 2, Z0 - 0.12])
    blocks.push([x, -blockH / 2, Z1 + 0.12])
  }
  const rows = Math.ceil((HALL_DEPTH + 0.4) / blockW)
  for (let i = 0; i < rows; i += 1) {
    const z = Z0 + blockW / 2 + i * blockW
    blocks.push([-HALL_WIDTH / 2 - 0.14, -blockH / 2, z])
    blocks.push([HALL_WIDTH / 2 + 0.14, -blockH / 2, z])
  }

  return (
    <group>
      {blocks.map((pos, i) => (
        <mesh key={i} position={pos}>
          <boxGeometry args={[blockW * 0.94, blockH, blockW * 0.94]} />
          <meshStandardMaterial color={FOUNDATION} roughness={0.95} />
        </mesh>
      ))}
      {/* 검정 스커트 — 벽 하단 실링 */}
      <mesh position={[0, 0.08, MID_Z]}>
        <boxGeometry args={[HALL_WIDTH + 0.28, 0.16, HALL_DEPTH + 0.35]} />
        <meshStandardMaterial color={SKIRT} roughness={0.85} />
      </mesh>
    </group>
  )
}

/** 박공면: 연속 비닐 채움 + 하부 백색 패널 + 스팬별 환기창 */
function EndWall({
  z,
  flip,
  doorOpening,
}: {
  z: number
  flip?: boolean
  /** 입구 문 개구 (중앙만 비우고 하부는 전체 피복) */
  doorOpening?: boolean
}) {
  const gables = useMemo(() => {
    const halfW = SPAN_WIDTH / 2 - 0.02
    return Array.from({ length: SPAN_COUNT }, (_, i) => {
      const cx = -HALL_WIDTH / 2 + i * SPAN_WIDTH + SPAN_WIDTH / 2
      const geo = createGableVinylGeometry(
        halfW,
        EAVES_HEIGHT,
        RIDGE_HEIGHT,
        24,
      )
      return { geo, cx }
    })
  }, [])

  // 하부 백색 피복 높이 (= 문 높이). 위는 처마까지 이어 붙인다.
  const cladH = 2.2
  const doorHalf = 1.15
  const sideW = HALL_WIDTH / 2 - doorHalf
  const upperH = Math.max(0.2, EAVES_HEIGHT - cladH)

  return (
    <group position={[0, 0, z]} rotation={[0, flip ? Math.PI : 0, 0]}>
      {gables.map(({ geo, cx }, i) => (
        <mesh key={`gable-${i}`} geometry={geo} position={[cx, 0, 0.02]}>
          <meshStandardMaterial {...vinylMat} />
        </mesh>
      ))}

      {doorOpening ? (
        <>
          {/* 문 왼쪽 — 벽 끝~문까지 통피복 */}
          <mesh position={[-(doorHalf + sideW / 2), cladH / 2, 0.05]}>
            <boxGeometry args={[sideW, cladH, 0.07]} />
            <meshStandardMaterial color={WHITE_PANEL} roughness={0.7} />
          </mesh>
          {/* 문 오른쪽 */}
          <mesh position={[doorHalf + sideW / 2, cladH / 2, 0.05]}>
            <boxGeometry args={[sideW, cladH, 0.07]} />
            <meshStandardMaterial color={WHITE_PANEL} roughness={0.7} />
          </mesh>
          {/* 문 위~처마 — 가로 전체 */}
          <mesh position={[0, cladH + upperH / 2, 0.05]}>
            <boxGeometry args={[HALL_WIDTH, upperH, 0.07]} />
            <meshStandardMaterial color={WHITE_PANEL} roughness={0.7} />
          </mesh>
        </>
      ) : (
        <>
          {/* 후면 박공: 하부 전폭 피복 (조각 패널 금지) */}
          <mesh position={[0, cladH / 2, 0.05]}>
            <boxGeometry args={[HALL_WIDTH, cladH, 0.07]} />
            <meshStandardMaterial color={WHITE_PANEL} roughness={0.7} />
          </mesh>
          <mesh position={[0, cladH + upperH / 2, 0.05]}>
            <boxGeometry args={[HALL_WIDTH, upperH, 0.07]} />
            <meshStandardMaterial color={WHITE_PANEL} roughness={0.7} />
          </mesh>
        </>
      )}

      {/* 스팬별 꼭대기 환기창 — 박공면에 flush, 지붕 위로 안 튀어나오게 */}
      {Array.from({ length: SPAN_COUNT }, (_, i) => {
        const cx = -HALL_WIDTH / 2 + i * SPAN_WIDTH + SPAN_WIDTH / 2
        return (
          <group key={`vent-${i}`} position={[cx, RIDGE_HEIGHT - 0.75, 0.01]}>
            <mesh>
              <boxGeometry args={[0.45, 0.36, 0.05]} />
              <meshStandardMaterial
                color={VENT}
                metalness={0.35}
                roughness={0.45}
              />
            </mesh>
            {[-0.08, 0.02, 0.12].map((vy) => (
              <mesh key={vy} position={[0, vy, 0.03]}>
                <boxGeometry args={[0.36, 0.028, 0.012]} />
                <meshStandardMaterial color="#2f363d" />
              </mesh>
            ))}
          </group>
        )
      })}

      {Array.from({ length: SPAN_COUNT + 1 }, (_, i) => {
        const x = -HALL_WIDTH / 2 + i * SPAN_WIDTH
        return (
          <mesh key={`ecol-${i}`} position={[x, EAVES_HEIGHT / 2, 0]}>
            <cylinderGeometry args={[0.045, 0.045, EAVES_HEIGHT, 6]} />
            <meshStandardMaterial
              color={FRAME_DARK}
              metalness={0.5}
              roughness={0.38}
            />
          </mesh>
        )
      })}
      {[0.7, 1.5, 2.3].map((y) => (
        <mesh key={`ep-${y}`} position={[0, y, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.025, 0.025, HALL_WIDTH, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.45}
            roughness={0.4}
          />
        </mesh>
      ))}
    </group>
  )
}

function SideWall({ x }: { x: number }) {
  return (
    <group>
      {/* 상부 연속 비닐 */}
      <mesh
        position={[x, EAVES_HEIGHT / 2 + 0.35, MID_Z]}
        rotation={[0, Math.PI / 2, 0]}
      >
        <planeGeometry args={[HALL_DEPTH + 0.1, EAVES_HEIGHT - 0.5]} />
        <meshStandardMaterial {...vinylMat} />
      </mesh>
      {/* 하부 백색 불투명 */}
      <mesh position={[x, 0.7, MID_Z]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[HALL_DEPTH + 0.1, 1.4]} />
        <meshStandardMaterial
          color={WHITE_PANEL}
          roughness={0.72}
          side={DoubleSide}
        />
      </mesh>
      {Array.from({ length: 10 }, (_, i) => {
        const z = Z0 + 0.4 + i * ((HALL_DEPTH - 0.8) / 9)
        return (
          <mesh key={z} position={[x, EAVES_HEIGHT / 2, z]}>
            <cylinderGeometry args={[0.038, 0.038, EAVES_HEIGHT, 5]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.5}
              roughness={0.4}
            />
          </mesh>
        )
      })}
      {[0.9, 1.8, EAVES_HEIGHT].map((y) => (
        <mesh
          key={y}
          position={[x, y, MID_Z]}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <cylinderGeometry args={[0.028, 0.028, HALL_DEPTH, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.45}
            roughness={0.4}
          />
        </mesh>
      ))}
    </group>
  )
}

export function CeilingPipeGrid() {
  // 처마 아래 내부만 — 아치 골을 뚫고 나가지 않도록
  const y = EAVES_HEIGHT - 0.45
  const beamsX: number[] = []
  for (let x = -HALL_WIDTH / 2 + 0.7; x <= HALL_WIDTH / 2 - 0.7; x += 1.15) {
    beamsX.push(x)
  }
  const beamsZ: number[] = []
  for (let z = Z0 + 1.0; z <= Z1 - 1.0; z += 1.35) {
    beamsZ.push(z)
  }

  return (
    <group>
      {beamsX.map((x) => (
        <mesh
          key={`px-${x}`}
          position={[x, y, MID_Z]}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <cylinderGeometry args={[0.02, 0.02, HALL_DEPTH - 2.2, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.55}
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
          <cylinderGeometry args={[0.018, 0.018, HALL_WIDTH - 1.2, 5]} />
          <meshStandardMaterial
            color={FRAME}
            metalness={0.55}
            roughness={0.35}
          />
        </mesh>
      ))}
      {/*
        천장 카세트 = 온·습도 조절장치 (HVAC/제습) — LED 아님.
        LED 생장등은 StrawberryRack GrowLightStrip.
      */}
      {beamsZ
        .filter((_, i) => i % 2 === 0)
        .flatMap((z) =>
          [-3.8, 0, 3.8].map((x) => (
            <group key={`climate-${x}-${z}`} position={[x, y - 0.12, z]}>
              <mesh>
                <boxGeometry args={[0.55, 0.14, 0.32]} />
                <meshStandardMaterial
                  color="#e9ecef"
                  roughness={0.55}
                  metalness={0.08}
                />
              </mesh>
              {/* 흡배기 그릴 */}
              <mesh position={[0, -0.075, 0]}>
                <boxGeometry args={[0.48, 0.02, 0.26]} />
                <meshStandardMaterial color="#868e96" roughness={0.7} />
              </mesh>
              {[-0.12, 0, 0.12].map((gz) => (
                <mesh key={`g-${gz}`} position={[0, -0.086, gz]}>
                  <boxGeometry args={[0.42, 0.008, 0.025]} />
                  <meshStandardMaterial color="#495057" />
                </mesh>
              ))}
              {/* 측면 배관 연결 */}
              <mesh position={[0.3, 0.02, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.025, 0.025, 0.12, 6]} />
                <meshStandardMaterial
                  color={FRAME}
                  metalness={0.5}
                  roughness={0.4}
                />
              </mesh>
            </group>
          )),
        )}
    </group>
  )
}

export function GreenhouseShell() {
  const ribZs = useMemo(() => {
    const zs: number[] = []
    for (let z = Z0 + 0.35; z <= Z1 - 0.35; z += 1.05) zs.push(z)
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
      {/* 외부 대지 (레퍼런스 밭/접근로) */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.52, MID_Z]}
        receiveShadow
      >
        <planeGeometry args={[HALL_WIDTH + 18, HALL_DEPTH + 16]} />
        <meshStandardMaterial color={GROUND} roughness={0.95} />
      </mesh>

      {/* 내부 흰 바닥 */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.01, MID_Z]}
        receiveShadow
      >
        <planeGeometry args={[HALL_WIDTH - 0.35, HALL_DEPTH - 0.5]} />
        <meshStandardMaterial color="#f4f4f2" roughness={0.55} />
      </mesh>

      <Foundation />
      <SideWall x={-HALL_WIDTH / 2} />
      <SideWall x={HALL_WIDTH / 2} />
      <EndWall z={Z0} />
      <EndWall z={Z1} flip doorOpening />
      <ValleyGutters />

      {Array.from({ length: SPAN_COUNT }, (_, s) => (
        <group key={`span-${s}`}>
          <ArchVinyl spanIndex={s} />
          {ribZs.map((z) => (
            <ArchRib key={`${s}-${z}`} spanIndex={s} z={z} />
          ))}
        </group>
      ))}

      {columns.map((pos, i) => (
        <mesh key={`col-${i}`} position={pos}>
          <cylinderGeometry args={[0.052, 0.052, EAVES_HEIGHT, 6]} />
          <meshStandardMaterial
            color={FRAME_DARK}
            metalness={0.5}
            roughness={0.38}
          />
        </mesh>
      ))}

      {Array.from({ length: SPAN_COUNT + 1 }, (_, s) => {
        const x = -HALL_WIDTH / 2 + s * SPAN_WIDTH
        return (
          <mesh
            key={`eave-${s}`}
            position={[x, EAVES_HEIGHT, MID_Z]}
            rotation={[Math.PI / 2, 0, 0]}
          >
            <cylinderGeometry args={[0.034, 0.034, HALL_DEPTH, 5]} />
            <meshStandardMaterial
              color={FRAME}
              metalness={0.45}
              roughness={0.4}
            />
          </mesh>
        )
      })}

      {/* 아치 리브 안쪽 퍼린 — 비닐 아래로 살짝 inset */}
      {Array.from({ length: SPAN_COUNT }, (_, s) => {
        const halfW = SPAN_WIDTH / 2
        const cx = -HALL_WIDTH / 2 + s * SPAN_WIDTH + halfW
        const pts = gothicArchPoints(halfW * 0.96, EAVES_HEIGHT, RIDGE_HEIGHT - 0.08, 8)
        return pts
          .filter((_, i) => i > 0 && i < pts.length - 1 && i % 2 === 0)
          .map((p, i) => (
            <mesh
              key={`purl-${s}-${i}`}
              position={[cx + p[0], p[1] - 0.04, MID_Z]}
              rotation={[Math.PI / 2, 0, 0]}
            >
              <cylinderGeometry args={[0.016, 0.016, HALL_DEPTH - 1.2, 4]} />
              <meshStandardMaterial
                color={FRAME}
                metalness={0.4}
                roughness={0.45}
              />
            </mesh>
          ))
      })}

      <CeilingPipeGrid />
    </group>
  )
}
