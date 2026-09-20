/**
 * 딸기 현수 거터 열 — GLB 작물 + 수관/열매 디테일.
 *
 * 레퍼런스: docs/refs/strawberry-interior.png
 * 에셋: public/models/strawberry.glb
 */

import { Suspense, useMemo } from 'react'
import { DoubleSide } from 'three'

import { StrawberryPlantModel } from './CropModel'
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

/** GLB 사이 빈 구간을 채우는 보조 잎·꽃 (저폴리) */
function FillerFoliage({
  position,
}: {
  position: [number, number, number]
}) {
  return (
    <group position={position}>
      <mesh position={[0.04, 0.05, 0.02]} rotation={[0.5, 0.3, 0.2]}>
        <planeGeometry args={[0.11, 0.08]} />
        <meshStandardMaterial color="#37b24d" side={DoubleSide} roughness={0.9} />
      </mesh>
      <mesh position={[-0.05, 0.04, -0.03]} rotation={[0.3, -0.4, -0.15]}>
        <planeGeometry args={[0.1, 0.07]} />
        <meshStandardMaterial color="#2b8a3e" side={DoubleSide} roughness={0.9} />
      </mesh>
      <mesh position={[0.01, 0.09, 0]}>
        <sphereGeometry args={[0.01, 5, 5]} />
        <meshStandardMaterial color="#ffffff" />
      </mesh>
    </group>
  )
}

function VHanger({ z, gutterY }: { z: number; gutterY: number }) {
  const topY = gutterY + 1.55
  return (
    <group position={[0, 0, z]}>
      <mesh position={[-0.12, (topY + gutterY) / 2, 0]} rotation={[0, 0, 0.18]}>
        <cylinderGeometry args={[0.008, 0.008, topY - gutterY, 4]} />
        <meshStandardMaterial color="#868e96" metalness={0.5} roughness={0.4} />
      </mesh>
      <mesh position={[0.12, (topY + gutterY) / 2, 0]} rotation={[0, 0, -0.18]}>
        <cylinderGeometry args={[0.008, 0.008, topY - gutterY, 4]} />
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

  const plantSlots = useMemo(() => {
    const items: Array<{
      z: number
      yaw: number
      scale: number
      side: number
    }> = []
    const start = -length / 2 + 0.35
    const end = length / 2 - 0.35
    let i = 0
    for (let z = start; z <= end; z += 0.48) {
      items.push({
        z,
        yaw: ((i * 47) % 360) * (Math.PI / 180),
        scale: 1.05 + (i % 3) * 0.08,
        side: i % 2 === 0 ? 0.02 : -0.02,
      })
      i += 1
    }
    return items
  }, [length])

  const fillers = useMemo(() => {
    const zs: number[] = []
    for (const slot of plantSlots) {
      zs.push(slot.z + 0.22)
    }
    return zs.filter((z) => Math.abs(z) < length / 2 - 0.2)
  }, [plantSlots, length])

  const hangers = useMemo(() => {
    const zs: number[] = []
    for (let z = -length / 2 + 0.6; z <= length / 2 - 0.6; z += 1.8) {
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
          <ringGeometry args={[0.35, 0.48, 28]} />
          <meshBasicMaterial color="#228be6" transparent opacity={0.5} />
        </mesh>
      ) : null}

      <mesh position={[0, gutterY, 0]}>
        <boxGeometry args={[0.32, 0.16, length]} />
        <meshStandardMaterial color="#f1f3f5" roughness={0.65} />
      </mesh>
      <mesh position={[0, gutterY + 0.06, 0]}>
        <boxGeometry args={[0.26, 0.05, length - 0.1]} />
        <meshStandardMaterial color="#5c4033" roughness={0.9} />
      </mesh>

      <mesh position={[0, gutterY + 0.55, 0]}>
        <boxGeometry args={[0.12, 0.04, length * 0.92]} />
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
        {plantSlots.map((slot, i) => (
          <StrawberryPlantModel
            key={`${label}-crop-${i}`}
            position={[slot.side, gutterY + 0.08, slot.z]}
            rotation={[0, slot.yaw, 0]}
            scale={slot.scale}
          />
        ))}
      </Suspense>

      {fillers.map((z, i) => (
        <FillerFoliage
          key={`${label}-fill-${i}`}
          position={[0, gutterY + 0.1, z]}
        />
      ))}

      <mesh position={[0.1, gutterY - 0.14, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.08, 0.012, 6, 16, Math.PI]} />
        <meshStandardMaterial color="#dee2e6" />
      </mesh>
      <mesh
        position={[-0.02, gutterY - 0.18, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <cylinderGeometry args={[0.012, 0.012, length * 0.9, 5]} />
        <meshStandardMaterial color="#e9ecef" />
      </mesh>

      {irrigating
        ? plantSlots
            .filter((_, i) => i % 3 === 0)
            .map((slot) => (
              <mesh
                key={`${label}-drop-${slot.z}`}
                position={[0.08, gutterY - 0.22, slot.z]}
              >
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
