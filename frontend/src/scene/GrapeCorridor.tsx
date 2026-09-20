/**
 * 포도 터널 — GLB 포도 작물 + 덩굴나무(주간·결과모·수관) 디테일.
 *
 * 에셋: public/models/grape.glb
 * -Z 방향이 터널 안쪽.
 */

import { Suspense, useMemo } from 'react'
import { DoubleSide } from 'three'

import { GrapePlantModel } from './CropModel'

const ARCH_COUNT = 8
const ARCH_SPACING = 1.15

function Hoop({ z }: { z: number }) {
  return (
    <group position={[0, 0, z]}>
      <mesh position={[-1.55, 1.35, 0]}>
        <boxGeometry args={[0.05, 2.7, 0.05]} />
        <meshStandardMaterial color="#6b7280" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[1.55, 1.35, 0]}>
        <boxGeometry args={[0.05, 2.7, 0.05]} />
        <meshStandardMaterial color="#6b7280" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[0, 2.72, 0]} rotation={[0, 0, Math.PI / 2]}>
        <boxGeometry args={[0.05, 3.15, 0.05]} />
        <meshStandardMaterial color="#6b7280" metalness={0.4} roughness={0.45} />
      </mesh>
    </group>
  )
}

/** 갈색 주간 + 좌우 결과모(cordon) + 측지 */
function GrapeVineTree({
  x,
  z,
  side,
}: {
  x: number
  z: number
  /** -1 왼쪽 / +1 오른쪽 — 통로를 바라보는 방향 */
  side: -1 | 1
}) {
  const trunkH = 1.35
  const cordonY = 1.45
  const inward = -side * 0.15

  return (
    <group position={[x, 0, z]}>
      {/* 주간(trunk) */}
      <mesh position={[0, trunkH / 2, 0]}>
        <cylinderGeometry args={[0.045, 0.06, trunkH, 7]} />
        <meshStandardMaterial color="#6b4f3a" roughness={0.92} />
      </mesh>
      {/* 주간 상단 분기 마디 */}
      <mesh position={[0, cordonY, 0]}>
        <sphereGeometry args={[0.055, 6, 6]} />
        <meshStandardMaterial color="#5c4033" roughness={0.9} />
      </mesh>

      {/* 결과모 — Z 방향 수평 팔 */}
      <mesh
        position={[inward, cordonY, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <cylinderGeometry args={[0.028, 0.032, 0.95, 6]} />
        <meshStandardMaterial color="#7a5c45" roughness={0.88} />
      </mesh>

      {/* 측지 몇 갈래 */}
      {[
        { pos: [inward * 0.5, cordonY + 0.12, 0.28] as [number, number, number], rot: [0.5, 0, 0.35] as [number, number, number], len: 0.45 },
        { pos: [inward * 0.5, cordonY + 0.18, -0.25] as [number, number, number], rot: [-0.4, 0, -0.3] as [number, number, number], len: 0.4 },
        { pos: [inward * 0.8, cordonY + 0.35, 0.05] as [number, number, number], rot: [0.1, 0, side * 0.55] as [number, number, number], len: 0.5 },
      ].map((b, i) => (
        <mesh key={`br-${i}`} position={b.pos} rotation={b.rot}>
          <cylinderGeometry args={[0.012, 0.02, b.len, 5]} />
          <meshStandardMaterial color="#8b7355" roughness={0.9} />
        </mesh>
      ))}

      {/* 수관 잎 클러스터 */}
      {[
        [inward * 0.3, cordonY + 0.55, 0.1],
        [inward * 0.6, cordonY + 0.7, -0.15],
        [inward * 0.2, cordonY + 0.65, 0.35],
        [inward * 0.9, cordonY + 0.5, 0.0],
        [0.05 * side, cordonY + 0.85, -0.05],
      ].map((p, i) => (
        <mesh
          key={`canopy-${i}`}
          position={p as [number, number, number]}
          rotation={[
            0.3 + i * 0.1,
            i * 0.4,
            side * 0.2,
          ]}
        >
          <planeGeometry args={[0.38, 0.3]} />
          <meshStandardMaterial
            color={i % 2 === 0 ? '#2b8a3e' : '#37b24d'}
            side={DoubleSide}
            roughness={0.88}
          />
        </mesh>
      ))}
      <mesh position={[inward * 0.4, cordonY + 0.6, 0.05]}>
        <sphereGeometry args={[0.22, 8, 8]} />
        <meshStandardMaterial
          color="#2f9e44"
          transparent
          opacity={0.55}
          roughness={0.95}
        />
      </mesh>
    </group>
  )
}

function CanopyLeaf({
  position,
}: {
  position: [number, number, number]
}) {
  return (
    <mesh position={position} rotation={[Math.PI / 2.4, 0.2, 0.1]}>
      <planeGeometry args={[0.35, 0.28]} />
      <meshStandardMaterial color="#2b8a3e" side={DoubleSide} roughness={0.9} />
    </mesh>
  )
}

export function GrapeCorridor() {
  const vines = useMemo(() => {
    const items: Array<{ x: number; z: number; side: -1 | 1 }> = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      items.push({ x: -1.2, z, side: -1 })
      items.push({ x: 1.2, z, side: 1 })
    }
    return items
  }, [])

  const grapeCrops = useMemo(() => {
    const items: Array<{
      position: [number, number, number]
      rotation: [number, number, number]
      scale: number
    }> = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      // 결과모에서 매달린 포도 작물 (좌·우, 앞뒤)
      items.push({
        position: [-1.05, 1.15, z - 0.15],
        rotation: [0.15, 0.4, 0.1],
        scale: 1.25,
      })
      items.push({
        position: [-1.1, 1.35, z + 0.2],
        rotation: [-0.1, -0.3, -0.05],
        scale: 1.15,
      })
      items.push({
        position: [1.05, 1.15, z - 0.15],
        rotation: [0.15, -0.4, -0.1],
        scale: 1.25,
      })
      items.push({
        position: [1.1, 1.35, z + 0.2],
        rotation: [-0.1, 0.35, 0.08],
        scale: 1.15,
      })
    }
    return items
  }, [])

  const leaves = useMemo(() => {
    const items: [number, number, number][] = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      for (let x = -1.35; x <= 1.35; x += 0.4) {
        if (Math.abs(x) < 0.45) continue
        items.push([x, 2.25 + (Math.abs(x) % 0.15), z + (x > 0 ? 0.08 : -0.05)])
      }
    }
    return items
  }, [])

  return (
    <group position={[0, 0, 1.2]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -4]} receiveShadow>
        <planeGeometry args={[1.1, 10]} />
        <meshStandardMaterial color="#f1f3f5" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-1.4, 0.02, -4]} receiveShadow>
        <planeGeometry args={[1.6, 10]} />
        <meshStandardMaterial color="#5c4033" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[1.4, 0.02, -4]} receiveShadow>
        <planeGeometry args={[1.6, 10]} />
        <meshStandardMaterial color="#5c4033" />
      </mesh>

      {/* 수평 와이어 (덕트 열) */}
      {[-1.05, 1.05].map((x) => (
        <mesh
          key={`wire-${x}`}
          position={[x, 1.48, -4]}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <cylinderGeometry args={[0.008, 0.008, 9.5, 5]} />
          <meshStandardMaterial color="#adb5bd" metalness={0.6} roughness={0.35} />
        </mesh>
      ))}

      {vines.map((v) => (
        <GrapeVineTree key={`vine-${v.x}-${v.z}`} x={v.x} z={v.z} side={v.side} />
      ))}

      {Array.from({ length: ARCH_COUNT }, (_, i) => (
        <Hoop key={`hoop-${i}`} z={-i * ARCH_SPACING} />
      ))}

      <Suspense fallback={null}>
        {grapeCrops.map((crop, index) => (
          <GrapePlantModel
            key={`grape-${index}`}
            position={crop.position}
            rotation={crop.rotation}
            scale={crop.scale}
          />
        ))}
      </Suspense>

      {leaves.map((pos, index) => (
        <CanopyLeaf key={`leaf-${index}`} position={pos} />
      ))}
    </group>
  )
}
