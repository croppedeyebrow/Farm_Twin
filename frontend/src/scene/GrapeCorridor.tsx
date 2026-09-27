/**
 * 포도 폴리터널.
 *
 * 레퍼런스: 포도 재배 구역 — 반투명 비닐 아치 터널, 능선·측면 도리,
 * 양옆 수직 트렐리스(지주+수평선+유인줄)에 올린 포도 생울타리, 가운데 우드칩 통로,
 * 안쪽 끝 출입문. 송이는 grape.glb 를 통로 쪽 과실 높이에 매단다.
 */

import { Suspense, useLayoutEffect, useMemo, useRef } from 'react'
import {
  BufferGeometry,
  CatmullRomCurve3,
  Color,
  DoubleSide,
  Float32BufferAttribute,
  Object3D,
  Path,
  Shape,
  Vector3,
} from 'three'
import type { InstancedMesh } from 'three'

import { useCropTuneStore } from '../store/cropTuneStore'
import { GrapePlantModel } from './CropModel'
import { GRAPE_TUNNEL_HALF_WIDTH } from './rackLayout'

const HOOP_COUNT = 9
const HOOP_SPACING = 0.82
const TUNNEL_LEN = (HOOP_COUNT - 1) * HOOP_SPACING
const HALF_W = GRAPE_TUNNEL_HALF_WIDTH
const PEAK_Y = 2.45
/** 1 보다 작을수록 옆벽이 서고 지붕이 평평해진다 (폴리터널 단면) */
const PROFILE_EXP = 0.72
const ROW_X = 0.62
const TRELLIS_TOP = 1.85
const WIRE_YS = [0.45, 0.9, 1.35, TRELLIS_TOP] as const
const PROFILE_STEPS = 28

const FILM = '#eef2f5'
const STEEL = '#aab1b8'

function profilePoint(t: number): { x: number; y: number } {
  const theta = Math.PI * (1 - t)
  const c = Math.cos(theta)
  const s = Math.sin(theta)
  return {
    x: HALF_W * Math.sign(c) * Math.abs(c) ** PROFILE_EXP,
    y: PEAK_Y * Math.max(0, s) ** PROFILE_EXP,
  }
}

function profilePoints(): Array<{ x: number; y: number }> {
  return Array.from({ length: PROFILE_STEPS + 1 }, (_, i) =>
    profilePoint(i / PROFILE_STEPS),
  )
}

function seeded(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 4294967296
  }
}

/** 단면을 Z 로 쓸어 만든 비닐 외피 */
function useFilmGeometry(): BufferGeometry {
  return useMemo(() => {
    const pts = profilePoints()
    const positions: number[] = []
    const indices: number[] = []
    const zFront = 0.12
    const zBack = -TUNNEL_LEN - 0.04
    pts.forEach(({ x, y }) => {
      positions.push(x, y, zFront, x, y, zBack)
    })
    for (let i = 0; i < pts.length - 1; i += 1) {
      const a = i * 2
      indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2)
    }
    const geo = new BufferGeometry()
    geo.setAttribute('position', new Float32BufferAttribute(positions, 3))
    geo.setIndex(indices)
    geo.computeVertexNormals()
    return geo
  }, [])
}

/** 안쪽 끝 막음 비닐 (출입문 개구 포함) */
function useEndWallShape(): Shape {
  return useMemo(() => {
    const pts = profilePoints()
    const shape = new Shape()
    shape.moveTo(pts[0].x, 0)
    pts.forEach(({ x, y }) => shape.lineTo(x, y))
    shape.lineTo(pts[pts.length - 1].x, 0)
    shape.closePath()
    const door = new Path()
    door.moveTo(-0.4, 0)
    door.lineTo(-0.4, 1.9)
    door.lineTo(0.4, 1.9)
    door.lineTo(0.4, 0)
    door.closePath()
    shape.holes.push(door)
    return shape
  }, [])
}

function useHoopCurve(): CatmullRomCurve3 {
  return useMemo(
    () =>
      new CatmullRomCurve3(profilePoints().map(({ x, y }) => new Vector3(x, y, 0))),
    [],
  )
}

type LeafItem = {
  position: [number, number, number]
  rotation: [number, number, number]
  scale: number
  color: string
}

function InstancedLeaves({ items }: { items: LeafItem[] }) {
  const ref = useRef<InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = ref.current
    if (!mesh) return
    const dummy = new Object3D()
    const color = new Color()
    items.forEach((leaf, i) => {
      dummy.position.set(...leaf.position)
      dummy.rotation.set(...leaf.rotation)
      dummy.scale.setScalar(leaf.scale)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      mesh.setColorAt(i, color.set(leaf.color))
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [items])

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, items.length]}>
      <circleGeometry args={[0.5, 7]} />
      <meshStandardMaterial side={DoubleSide} roughness={0.85} />
    </instancedMesh>
  )
}

function WoodChips({ count, width }: { count: number; width: number }) {
  const ref = useRef<InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = ref.current
    if (!mesh) return
    const rnd = seeded(71)
    const dummy = new Object3D()
    const color = new Color()
    for (let i = 0; i < count; i += 1) {
      dummy.position.set((rnd() - 0.5) * width, 0.022, 0.1 - rnd() * (TUNNEL_LEN + 0.2))
      dummy.rotation.set(0, rnd() * Math.PI, 0)
      dummy.scale.set(0.05 + rnd() * 0.05, 1, 0.02 + rnd() * 0.02)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      mesh.setColorAt(i, color.setHSL(0.08 + rnd() * 0.03, 0.4, 0.3 + rnd() * 0.22))
    }
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [count, width])

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <boxGeometry args={[1, 0.012, 1]} />
      <meshStandardMaterial roughness={0.95} />
    </instancedMesh>
  )
}

function AlongZ({
  x,
  y,
  radius,
  color,
  length = TUNNEL_LEN,
}: {
  x: number
  y: number
  radius: number
  color: string
  length?: number
}) {
  return (
    <mesh position={[x, y, -length / 2]} rotation={[Math.PI / 2, 0, 0]}>
      <cylinderGeometry args={[radius, radius, length, 6]} />
      <meshStandardMaterial color={color} metalness={0.4} roughness={0.45} />
    </mesh>
  )
}

export function GrapeCorridor() {
  const crop = useCropTuneStore((s) => s.grape)
  const film = useFilmGeometry()
  const endWall = useEndWallShape()
  const hoopCurve = useHoopCurve()

  const vineZs = useMemo(
    () => Array.from({ length: HOOP_COUNT }, (_, i) => -i * HOOP_SPACING),
    [],
  )
  const trellisPostZs = useMemo(
    () => vineZs.filter((_, i) => i % 2 === 0 || i === HOOP_COUNT - 1),
    [vineZs],
  )

  const leaves = useMemo(() => {
    const rnd = seeded(29)
    const items: LeafItem[] = []
    for (const side of [-1, 1] as const) {
      const rowX = side * ROW_X
      for (let z = 0.05; z >= -TUNNEL_LEN - 0.05; z -= 0.09) {
        const perSlice = 7
        for (let k = 0; k < perSlice; k += 1) {
          const h = 0.3 + (1 - rnd() ** 1.6) * (TRELLIS_TOP + 0.12 - 0.3)
          const shade = rnd()
          items.push({
            position: [rowX + (rnd() - 0.5) * 0.34, h, z + (rnd() - 0.5) * 0.08],
            rotation: [
              (rnd() - 0.6) * 0.9,
              (side < 0 ? Math.PI / 2 : -Math.PI / 2) + (rnd() - 0.5) * 1.1,
              (rnd() - 0.5) * 0.8,
            ],
            scale: 0.15 + rnd() * 0.09,
            color: new Color()
              .setHSL(0.26 + shade * 0.04, 0.55 + shade * 0.2, 0.12 + shade * 0.12)
              .getStyle(),
          })
        }
      }
    }
    return items
  }, [])

  const bunches = useMemo(() => {
    const rnd = seeded(113)
    const items: Array<{
      position: [number, number, number]
      rotation: [number, number, number]
      scale: number
    }> = []
    for (const side of [-1, 1] as const) {
      const faceX = side * ROW_X - side * 0.16
      for (const vz of vineZs) {
        for (const dz of [-0.24, 0.02, 0.26]) {
          const scale = 1.0 + rnd() * 0.3
          const hangY = 1.05 + rnd() * 0.35
          items.push({
            position: [faceX + (rnd() - 0.5) * 0.06, hangY - 0.25 * scale, vz + dz],
            rotation: [0, rnd() * Math.PI * 2, side * 0.08],
            scale,
          })
        }
      }
    }
    return items
  }, [vineZs])

  return (
    <group position={[0, 0, 0.5]}>
      {/* 바닥: 가장자리 흙 + 재배열 + 가운데 우드칩 통로 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, -TUNNEL_LEN / 2]} receiveShadow>
        <planeGeometry args={[HALF_W * 2, TUNNEL_LEN + 0.3]} />
        <meshStandardMaterial color="#6f5d47" roughness={0.97} />
      </mesh>
      {([-ROW_X, ROW_X] as const).map((x) => (
        <mesh
          key={`bed-${x}`}
          rotation={[-Math.PI / 2, 0, 0]}
          position={[x, 0.012, -TUNNEL_LEN / 2]}
          receiveShadow
        >
          <planeGeometry args={[0.34, TUNNEL_LEN + 0.2]} />
          <meshStandardMaterial color="#4e3d2e" roughness={0.98} />
        </mesh>
      ))}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.016, -TUNNEL_LEN / 2]} receiveShadow>
        <planeGeometry args={[(ROW_X - 0.2) * 2, TUNNEL_LEN + 0.3]} />
        <meshStandardMaterial color="#a07c55" roughness={0.98} />
      </mesh>
      <WoodChips count={360} width={(ROW_X - 0.22) * 2} />

      {/* 아치 파이프 + 도리 */}
      {vineZs.map((z) => (
        <mesh key={`hoop-${z}`} position={[0, 0, z]}>
          <tubeGeometry args={[hoopCurve, 36, 0.014, 5, false]} />
          <meshStandardMaterial color={STEEL} metalness={0.45} roughness={0.4} />
        </mesh>
      ))}
      <AlongZ x={0} y={PEAK_Y} radius={0.013} color={STEEL} />
      {[0.22, 0.78].map((t) => {
        const p = profilePoint(t)
        return <AlongZ key={`purlin-${t}`} x={p.x} y={p.y} radius={0.011} color={STEEL} />
      })}
      {[-1, 1].map((side) => (
        <AlongZ key={`base-${side}`} x={side * (HALF_W - 0.01)} y={0.12} radius={0.02} color="#8d8f91" />
      ))}

      {/* 반투명 비닐 */}
      <mesh geometry={film} renderOrder={2}>
        <meshStandardMaterial
          color={FILM}
          transparent
          opacity={0.2}
          roughness={0.35}
          side={DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, 0, -TUNNEL_LEN - 0.04]} renderOrder={2}>
        <shapeGeometry args={[endWall, 24]} />
        <meshStandardMaterial
          color={FILM}
          transparent
          opacity={0.32}
          side={DoubleSide}
          depthWrite={false}
        />
      </mesh>
      {([-0.4, 0.4] as const).map((x) => (
        <mesh key={`door-${x}`} position={[x, 0.95, -TUNNEL_LEN - 0.02]}>
          <boxGeometry args={[0.04, 1.9, 0.04]} />
          <meshStandardMaterial color="#8a9096" metalness={0.3} />
        </mesh>
      ))}
      <mesh position={[0, 1.9, -TUNNEL_LEN - 0.02]}>
        <boxGeometry args={[0.84, 0.04, 0.04]} />
        <meshStandardMaterial color="#8a9096" metalness={0.3} />
      </mesh>

      {/* 트렐리스: 지주 + 수평선 */}
      {([-ROW_X, ROW_X] as const).map((x) => (
        <group key={`trellis-${x}`}>
          {trellisPostZs.map((z) => (
            <mesh key={`tp-${z}`} position={[x, TRELLIS_TOP / 2 + 0.05, z]}>
              <boxGeometry args={[0.04, TRELLIS_TOP + 0.1, 0.04]} />
              <meshStandardMaterial color="#8c7355" roughness={0.9} />
            </mesh>
          ))}
          {WIRE_YS.map((y) => (
            <AlongZ key={`w-${y}`} x={x} y={y} radius={0.0035} color="#dee2e6" />
          ))}
          <AlongZ x={x + (x < 0 ? 0.1 : -0.1)} y={0.04} radius={0.014} color="#1a1b1e" />
        </group>
      ))}

      {/* 포도나무 원줄기 + 유인줄 */}
      {vineZs.flatMap((z) =>
        ([-ROW_X, ROW_X] as const).map((x) => (
          <group key={`vine-${x}-${z}`} position={[x, 0, z]}>
            <mesh position={[0, 0.5, 0]} rotation={[0.06, 0, x < 0 ? 0.05 : -0.05]} castShadow>
              <cylinderGeometry args={[0.022, 0.034, 1.0, 6]} />
              <meshStandardMaterial color="#5c4033" roughness={0.93} />
            </mesh>
            <mesh position={[0, (TRELLIS_TOP + 0.1) / 2, 0.02]}>
              <cylinderGeometry args={[0.003, 0.003, TRELLIS_TOP - 0.1, 3]} />
              <meshStandardMaterial color="#f1f3f5" />
            </mesh>
          </group>
        )),
      )}

      <InstancedLeaves items={leaves} />

      <Suspense fallback={null}>
        {bunches.map((bunch, index) => (
          <GrapePlantModel
            key={`bunch-${index}`}
            position={[
              bunch.position[0] + crop.offsetX,
              bunch.position[1] + crop.offsetY,
              bunch.position[2] + crop.offsetZ,
            ]}
            rotation={bunch.rotation}
            scale={bunch.scale * crop.scale}
          />
        ))}
      </Suspense>
    </group>
  )
}
