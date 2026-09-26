/**
 * 포도 터널 — 아치 수관 + grape.glb 송이 고밀도 배치.
 *
 * 목적: 레퍼런스 터널 구조는 유지하되, 송이는 crop-c021(=grape.glb)로 표현.
 * 이유: 흰 봉지 primitive 대신 실제 포도 메시가 관제·작물 식별에 맞음.
 * 에셋: public/models/grape.glb (== docs/refs/crop-c021.glb)
 */

import { Suspense, useMemo } from 'react'
import { DoubleSide } from 'three'

import { useCropTuneStore } from '../store/cropTuneStore'
import { GrapePlantModel } from './CropModel'

const ARCH_COUNT = 9
const ARCH_SPACING = 0.82
const AISLE_HALF = 0.5
const POST_X = 1.2
const ARCH_PEAK_Y = 2.48
const CORDON_Y = 1.32

function archPoint(t: number): { x: number; y: number } {
  const x = -POST_X + 2 * POST_X * t
  const y = CORDON_Y + (ARCH_PEAK_Y - CORDON_Y) * Math.sin(Math.PI * t)
  return { x, y }
}

function ArchFrame({ z }: { z: number }) {
  const segments = useMemo(() => {
    const items: Array<{
      pos: [number, number, number]
      rot: [number, number, number]
      len: number
    }> = []
    const steps = 12
    for (let i = 0; i < steps; i += 1) {
      const t0 = i / steps
      const t1 = (i + 1) / steps
      const p0 = archPoint(t0)
      const p1 = archPoint(t1)
      const mx = (p0.x + p1.x) / 2
      const my = (p0.y + p1.y) / 2
      const dx = p1.x - p0.x
      const dy = p1.y - p0.y
      items.push({
        pos: [mx, my, 0],
        rot: [0, 0, Math.atan2(dy, dx)],
        len: Math.hypot(dx, dy),
      })
    }
    return items
  }, [])

  return (
    <group position={[0, 0, z]}>
      {([-POST_X, POST_X] as const).map((x) => (
        <mesh key={`post-${x}`} position={[x, CORDON_Y / 2, 0]} castShadow>
          <cylinderGeometry args={[0.022, 0.028, CORDON_Y, 6]} />
          <meshStandardMaterial color="#9aa0a6" metalness={0.4} roughness={0.42} />
        </mesh>
      ))}
      {segments.map((s, i) => (
        <mesh key={`arc-${i}`} position={s.pos} rotation={s.rot}>
          <cylinderGeometry args={[0.01, 0.01, s.len, 5]} />
          <meshStandardMaterial color="#b0b6bc" metalness={0.3} roughness={0.48} />
        </mesh>
      ))}
    </group>
  )
}

function VineTrunk({ x, z }: { x: number; z: number }) {
  const side = x < 0 ? -1 : 1
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.68, 0]} castShadow>
        <cylinderGeometry args={[0.035, 0.05, 1.36, 7]} />
        <meshStandardMaterial color="#5c4033" roughness={0.93} />
      </mesh>
      <mesh
        position={[-side * 0.28, 1.28, 0]}
        rotation={[0.15, 0, side * 0.55]}
      >
        <cylinderGeometry args={[0.016, 0.024, 0.85, 6]} />
        <meshStandardMaterial color="#6b5344" roughness={0.9} />
      </mesh>
    </group>
  )
}

function CanopyLeaf({
  position,
  rotation,
  w,
  h,
  shade,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  w: number
  h: number
  shade: number
}) {
  const r = Math.round(28 + shade * 18)
  const g = Math.round(100 + shade * 70)
  const b = Math.round(36 + shade * 12)
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={[w, h]} />
      <meshStandardMaterial
        color={`rgb(${r},${g},${b})`}
        side={DoubleSide}
        roughness={0.88}
      />
    </mesh>
  )
}

function DripLine({ x, length = 7.0 }: { x: number; length?: number }) {
  return (
    <mesh
      position={[x, 0.035, -length / 2 + 0.2]}
      rotation={[Math.PI / 2, 0, 0]}
    >
      <cylinderGeometry args={[0.016, 0.016, length, 6]} />
      <meshStandardMaterial color="#1a1b1e" roughness={0.78} />
    </mesh>
  )
}

function FruitWire({ x, y, length }: { x: number; y: number; length: number }) {
  return (
    <mesh
      position={[x, y, -length / 2 + 0.15]}
      rotation={[Math.PI / 2, 0, 0]}
    >
      <cylinderGeometry args={[0.004, 0.004, length, 4]} />
      <meshStandardMaterial color="#ced4da" metalness={0.55} roughness={0.35} />
    </mesh>
  )
}

export function GrapeCorridor() {
  const crop = useCropTuneStore((s) => s.grape)
  const tunnelLen = (ARCH_COUNT - 1) * ARCH_SPACING + 0.4

  const vines = useMemo(() => {
    const items: Array<{ x: number; z: number }> = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      items.push({ x: -POST_X + 0.06, z })
      items.push({ x: POST_X - 0.06, z })
    }
    return items
  }, [])

  const canopyLeaves = useMemo(() => {
    const items: Array<{
      pos: [number, number, number]
      rot: [number, number, number]
      w: number
      h: number
      shade: number
    }> = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z0 = -i * ARCH_SPACING
      for (let row = 0; row < 3; row += 1) {
        const z = z0 + (row - 1) * 0.22
        for (let t = 0.05; t <= 0.95; t += 0.055) {
          const { x, y } = archPoint(t)
          const tangent = Math.cos(Math.PI * t)
          items.push({
            pos: [
              x * 0.98,
              y + 0.06 + (Math.abs(t - 0.5) < 0.12 ? 0.04 : 0),
              z + (t - 0.5) * 0.05,
            ],
            rot: [
              Math.PI / 2.15 - Math.abs(tangent) * 0.25,
              t * 3.1 + row,
              -tangent * 0.75,
            ],
            w: 0.38 + (row % 2) * 0.06,
            h: 0.28 + ((i + row) % 3) * 0.04,
            shade: 0.15 + Math.abs(t - 0.5) * 0.9,
          })
        }
      }
    }
    return items
  }, [])

  /**
   * grape.glb 송이 — 예전 봉지 자리에 조밀 배치.
   * 모델 로컬: Y≈0~0.25 (밑→위). 와이어에 매달리도록 위치·회전.
   */
  const grapeBunches = useMemo(() => {
    const items: Array<{
      position: [number, number, number]
      rotation: [number, number, number]
      scale: number
    }> = []
    const zStep = 0.3
    const zStart = 0.12
    const zEnd = -tunnelLen + 0.45
    const leftTs = [0.2, 0.28, 0.35]
    const rightTs = [0.65, 0.72, 0.8]

    for (let z = zStart; z >= zEnd; z -= zStep) {
      for (const t of leftTs) {
        const { x, y } = archPoint(t)
        const jitter = ((Math.abs(z * 10 + t * 17) % 7) - 3) * 0.01
        const yaw = 0.4 + (Math.abs(z * 5) % 5) * 0.15
        items.push({
          // 송이 상단이 와이어 쪽에 오도록 Y를 약간 내림
          position: [x + 0.02, y - 0.2 + jitter * 0.4, z + jitter],
          rotation: [0.25, yaw, 0.12],
          scale: 1.05 + (Math.abs(z * 3) % 5) * 0.04,
        })
      }
      for (const t of rightTs) {
        const { x, y } = archPoint(t)
        const jitter = ((Math.abs(z * 11 + t * 13) % 7) - 3) * 0.01
        const yaw = -0.4 - (Math.abs(z * 4) % 5) * 0.15
        items.push({
          position: [x - 0.02, y - 0.2 + jitter * 0.4, z + jitter],
          rotation: [0.25, yaw, -0.12],
          scale: 1.05 + (Math.abs(z * 5) % 5) * 0.04,
        })
      }
    }
    return items
  }, [tunnelLen])

  return (
    <group position={[0, 0, 0.5]}>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.01, -tunnelLen / 2]}
        receiveShadow
      >
        <planeGeometry args={[AISLE_HALF * 2.15, tunnelLen + 0.6]} />
        <meshStandardMaterial color="#f1f3f5" roughness={0.5} metalness={0.05} />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[-(AISLE_HALF + 0.72), 0.016, -tunnelLen / 2]}
        receiveShadow
      >
        <planeGeometry args={[1.35, tunnelLen + 0.6]} />
        <meshStandardMaterial color="#141516" roughness={0.96} />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[AISLE_HALF + 0.72, 0.016, -tunnelLen / 2]}
        receiveShadow
      >
        <planeGeometry args={[1.35, tunnelLen + 0.6]} />
        <meshStandardMaterial color="#141516" roughness={0.96} />
      </mesh>

      <DripLine x={-POST_X + 0.12} length={tunnelLen} />
      <DripLine x={POST_X - 0.12} length={tunnelLen} />

      <FruitWire x={-0.78} y={1.58} length={tunnelLen} />
      <FruitWire x={-0.62} y={1.72} length={tunnelLen} />
      <FruitWire x={0.62} y={1.72} length={tunnelLen} />
      <FruitWire x={0.78} y={1.58} length={tunnelLen} />
      <FruitWire x={-0.35} y={2.2} length={tunnelLen} />
      <FruitWire x={0.35} y={2.2} length={tunnelLen} />
      <FruitWire x={0} y={2.42} length={tunnelLen} />

      {Array.from({ length: ARCH_COUNT }, (_, i) => (
        <ArchFrame key={`arch-${i}`} z={-i * ARCH_SPACING} />
      ))}

      {vines.map((v) => (
        <VineTrunk key={`trunk-${v.x}-${v.z}`} x={v.x} z={v.z} />
      ))}

      {canopyLeaves.map((leaf, index) => (
        <CanopyLeaf
          key={`leaf-${index}`}
          position={leaf.pos}
          rotation={leaf.rot}
          w={leaf.w}
          h={leaf.h}
          shade={leaf.shade}
        />
      ))}

      <Suspense fallback={null}>
        {grapeBunches.map((bunch, index) => (
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
