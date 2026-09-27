/**
 * 딸기 다단 재배대 (3단).
 *
 * 레퍼런스: 딸기 재배 구역 — 흰 스틸 프레임 다단 선반, 단마다 흰 거터 + 점적관,
 * 윗단 밑에 붙은 생장 LED 가 아랫단 캐노피를 비춘다. 열매는 거터 양옆으로 늘어진다.
 */

import { Suspense, useMemo } from 'react'

import { useCropTuneStore } from '../store/cropTuneStore'
import {
  STRAWBERRY_SEGMENT_LENGTH,
  StrawberryRowSegment,
} from './CropModel'
import { GrowLightStrip } from './GrowLightStrip'
import {
  GUTTER_LENGTH,
  STRAWBERRY_TIER_HEIGHTS,
  TIER_LED_DROP,
} from './rackLayout'

type StrawberryRackProps = {
  position: [number, number, number]
  label: string
  ledRatio: number
  irrigating: boolean
  selected?: boolean
  onSelect?: () => void
  length?: number
}

const FRAME = '#eef1f4'
const FRAME_HALF_X = 0.2
const POST_PITCH = 1.6
const GUTTER_W = 0.3
const GUTTER_H = 0.18

const TIER_PITCH = STRAWBERRY_TIER_HEIGHTS[1] - STRAWBERRY_TIER_HEIGHTS[0]
const TOP_Y =
  STRAWBERRY_TIER_HEIGHTS[STRAWBERRY_TIER_HEIGHTS.length - 1] + TIER_PITCH - 0.06

function ledHeight(tierIndex: number): number {
  const above =
    STRAWBERRY_TIER_HEIGHTS[tierIndex + 1] ??
    STRAWBERRY_TIER_HEIGHTS[tierIndex] + TIER_PITCH
  return above - TIER_LED_DROP
}

function FramePost({ z }: { z: number }) {
  return (
    <group position={[0, 0, z]}>
      {([-FRAME_HALF_X, FRAME_HALF_X] as const).map((x) => (
        <mesh key={`post-${x}`} position={[x, TOP_Y / 2, 0]}>
          <boxGeometry args={[0.035, TOP_Y, 0.035]} />
          <meshStandardMaterial color={FRAME} roughness={0.5} metalness={0.2} />
        </mesh>
      ))}
      <mesh position={[0, 0.02, 0]}>
        <boxGeometry args={[FRAME_HALF_X * 2 + 0.12, 0.04, 0.06]} />
        <meshStandardMaterial color="#c9ced4" roughness={0.6} />
      </mesh>
      {STRAWBERRY_TIER_HEIGHTS.map((y) => (
        <mesh key={`arm-${y}`} position={[0, y - GUTTER_H / 2 - 0.02, 0]}>
          <boxGeometry args={[FRAME_HALF_X * 2 + 0.04, 0.03, 0.035]} />
          <meshStandardMaterial color={FRAME} roughness={0.5} metalness={0.2} />
        </mesh>
      ))}
      <mesh position={[0, TOP_Y, 0]}>
        <boxGeometry args={[FRAME_HALF_X * 2 + 0.04, 0.035, 0.035]} />
        <meshStandardMaterial color={FRAME} roughness={0.5} metalness={0.2} />
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
  const crop = useCropTuneStore((s) => s.strawberry)

  const segments = useMemo(() => {
    const pitch = STRAWBERRY_SEGMENT_LENGTH
    const count = Math.max(1, Math.floor(length / pitch))
    const start = -((count - 1) * pitch) / 2
    return Array.from({ length: count }, (_, i) => ({
      z: start + i * pitch,
      flip: i % 2 === 1,
    }))
  }, [length])

  const posts = useMemo(() => {
    const count = Math.max(2, Math.round(length / POST_PITCH) + 1)
    const step = (length - 0.1) / (count - 1)
    return Array.from({ length: count }, (_, i) => -length / 2 + 0.05 + i * step)
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

      {posts.map((z) => (
        <FramePost key={`${label}-post-${z.toFixed(2)}`} z={z} />
      ))}
      {([-FRAME_HALF_X, FRAME_HALF_X] as const).map((x) => (
        <mesh key={`${label}-top-${x}`} position={[x, TOP_Y, 0]}>
          <boxGeometry args={[0.03, 0.03, length]} />
          <meshStandardMaterial color={FRAME} roughness={0.5} metalness={0.2} />
        </mesh>
      ))}

      {STRAWBERRY_TIER_HEIGHTS.map((y, tier) => (
        <group key={`${label}-tier-${tier}`}>
          <mesh position={[0, y, 0]}>
            <boxGeometry args={[GUTTER_W, GUTTER_H, length]} />
            <meshStandardMaterial color="#f8f9fa" roughness={0.45} />
          </mesh>
          <mesh position={[0, y + GUTTER_H / 2 + 0.002, 0]}>
            <boxGeometry args={[0.13, 0.012, length - 0.12]} />
            <meshStandardMaterial color="#2b2118" roughness={0.95} />
          </mesh>
          <mesh
            position={[0.07, y + GUTTER_H / 2 + 0.012, 0]}
            rotation={[Math.PI / 2, 0, 0]}
          >
            <cylinderGeometry args={[0.008, 0.008, length - 0.1, 5]} />
            <meshStandardMaterial color="#1a1b1e" roughness={0.7} />
          </mesh>

          <group position={[0, ledHeight(tier), 0]}>
            <GrowLightStrip
              length={length}
              ledRatio={ledRatio}
              width={0.2}
              washDrop={0.28}
            />
          </group>

          <Suspense fallback={null}>
            {segments.map((seg, i) => (
              <StrawberryRowSegment
                key={`${label}-t${tier}-seg-${i}`}
                position={[
                  crop.offsetX,
                  y + 0.08 + crop.offsetY,
                  seg.z + crop.offsetZ,
                ]}
                yaw={(seg.flip ? Math.PI : 0) + (tier % 2 === 1 ? Math.PI : 0)}
                scale={crop.scale}
              />
            ))}
          </Suspense>

          {irrigating
            ? posts.slice(0, -1).map((z) => (
                <mesh
                  key={`${label}-drop-${tier}-${z.toFixed(2)}`}
                  position={[0.07, y + GUTTER_H / 2 - 0.02, z + POST_PITCH / 2]}
                >
                  <sphereGeometry args={[0.018, 6, 6]} />
                  <meshStandardMaterial color="#74c0fc" transparent opacity={0.75} />
                </mesh>
              ))
            : null}
        </group>
      ))}
    </group>
  )
}
