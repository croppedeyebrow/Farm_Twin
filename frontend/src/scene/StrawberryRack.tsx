/**
 * 딸기 현수 라인.
 *
 * 레퍼런스: docs/refs/strawberry line.png
 * 에셋 원본 형태 유지 + 흰 거터/검정 레일 배치.
 */

import { Suspense, useMemo } from 'react'

import { useCropTuneStore } from '../store/cropTuneStore'
import {
  STRAWBERRY_SEGMENT_LENGTH,
  StrawberryRowSegment,
} from './CropModel'
import { GUTTER_HEIGHT, GUTTER_LENGTH } from './rackLayout'

type StrawberryRackProps = {
  position: [number, number, number]
  label: string
  ledRatio: number
  irrigating: boolean
  selected?: boolean
  onSelect?: () => void
  length?: number
}

function VHanger({ z, gutterY }: { z: number; gutterY: number }) {
  const topY = gutterY + 1.55
  return (
    <group position={[0, 0, z]}>
      <mesh position={[-0.16, (topY + gutterY) / 2, 0]} rotation={[0, 0, 0.14]}>
        <cylinderGeometry args={[0.009, 0.009, topY - gutterY, 5]} />
        <meshStandardMaterial color="#868e96" metalness={0.5} roughness={0.4} />
      </mesh>
      <mesh position={[0.16, (topY + gutterY) / 2, 0]} rotation={[0, 0, -0.14]}>
        <cylinderGeometry args={[0.009, 0.009, topY - gutterY, 5]} />
        <meshStandardMaterial color="#868e96" metalness={0.5} roughness={0.4} />
      </mesh>
    </group>
  )
}

export function StrawberryRack({
  position,
  label,
  ledRatio,
  irrigating,
  selected = false,
  onSelect,
  length = GUTTER_LENGTH,
}: StrawberryRackProps) {
  const gutterY = GUTTER_HEIGHT
  const crop = useCropTuneStore((s) => s.strawberry)

  const segments = useMemo(() => {
    const items: Array<{ z: number; flip: boolean }> = []
    const pitch = STRAWBERRY_SEGMENT_LENGTH
    const start = -length / 2 + pitch / 2
    const end = length / 2 - pitch / 2
    let i = 0
    for (let z = start; z <= end + 1e-6; z += pitch) {
      items.push({ z, flip: i % 2 === 1 })
      i += 1
    }
    return items
  }, [length])

  const hangers = useMemo(() => {
    const zs: number[] = []
    for (let z = -length / 2 + 0.5; z <= length / 2 - 0.5; z += 1.6) {
      zs.push(z)
    }
    return zs
  }, [length])

  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect?.()
      }}
    >
      {selected ? (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
          <ringGeometry args={[0.4, 0.55, 28]} />
          <meshBasicMaterial color="#228be6" transparent opacity={0.5} />
        </mesh>
      ) : null}

      {/* 흰 거터 */}
      <mesh position={[0, gutterY, 0]}>
        <boxGeometry args={[0.34, 0.22, length]} />
        <meshStandardMaterial color="#f5f5f5" roughness={0.45} />
      </mesh>
      {/* 상단 개구 (좁게 — 뿌리/배지 비노출) */}
      <mesh position={[0, gutterY + 0.105, 0]}>
        <boxGeometry args={[0.14, 0.02, length - 0.15]} />
        <meshStandardMaterial color="#2b2118" roughness={0.95} />
      </mesh>
      {/* 하단 검정 레일 */}
      <mesh position={[0, gutterY - 0.13, 0]}>
        <boxGeometry args={[0.09, 0.035, length - 0.15]} />
        <meshStandardMaterial color="#1a1a1a" roughness={0.7} />
      </mesh>

      <mesh position={[0, gutterY + 0.72, 0]}>
        <boxGeometry args={[0.14, 0.04, length * 0.92]} />
        <meshStandardMaterial
          color="#fff9db"
          emissive="#ffd43b"
          emissiveIntensity={0.12 + ledRatio * 1.5}
        />
      </mesh>

      {hangers.map((z) => (
        <VHanger key={`${label}-h-${z}`} z={z} gutterY={gutterY} />
      ))}

      <Suspense fallback={null}>
        {segments.map((seg, i) => (
          <StrawberryRowSegment
            key={`${label}-seg-${i}`}
            position={[
              crop.offsetX,
              gutterY + 0.1 + crop.offsetY,
              seg.z + crop.offsetZ,
            ]}
            yaw={seg.flip ? Math.PI : 0}
            scale={crop.scale}
          />
        ))}
      </Suspense>

      <mesh position={[0.14, gutterY - 0.18, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.08, 0.01, 6, 14, Math.PI]} />
        <meshStandardMaterial color="#ced4da" />
      </mesh>
      <mesh position={[0, gutterY - 0.22, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.01, 0.01, length * 0.9, 5]} />
        <meshStandardMaterial color="#adb5bd" />
      </mesh>

      {irrigating
        ? hangers
            .filter((_, i) => i % 2 === 0)
            .map((z) => (
              <mesh key={`${label}-drop-${z}`} position={[0.12, gutterY - 0.3, z]}>
                <sphereGeometry args={[0.02, 6, 6]} />
                <meshStandardMaterial
                  color="#74c0fc"
                  transparent
                  opacity={0.7}
                />
              </mesh>
            ))
        : null}
    </group>
  )
}
