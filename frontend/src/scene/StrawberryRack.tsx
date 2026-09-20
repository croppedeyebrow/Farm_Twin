/**
 * 딸기 수직 랙 (5단계 Day 19).
 *
 * 기존 Rack 골격을 확장: 선반 + 포트 + 잎/열매 포인트.
 * LED·관수 비주얼은 ActuatorVisuals 가 같은 위치에 올린다.
 */

import { SHELF_HEIGHTS } from './rackLayout'

type StrawberryRackProps = {
  position: [number, number, number]
  label: string
  /** LED 출력 0~1 — 선반 아래 emissive */
  ledRatio: number
  /** 관수 중이면 물방울 표시 */
  irrigating: boolean
  selected?: boolean
  onSelect?: () => void
}

function StrawberryPlant({
  position,
}: {
  position: [number, number, number]
}) {
  return (
    <group position={position}>
      <mesh position={[0, 0.04, 0]}>
        <cylinderGeometry args={[0.06, 0.05, 0.08, 8]} />
        <meshStandardMaterial color="#868e96" />
      </mesh>
      <mesh position={[0, 0.12, 0]}>
        <sphereGeometry args={[0.07, 8, 8]} />
        <meshStandardMaterial color="#37b24d" />
      </mesh>
      <mesh position={[0.05, 0.1, 0.04]}>
        <sphereGeometry args={[0.025, 6, 6]} />
        <meshStandardMaterial color="#f03e3e" />
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
}: StrawberryRackProps) {
  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect?.()
      }}
    >
      {/* 선택 하이라이트 바닥 */}
      {selected ? (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, -0.35]}>
          <ringGeometry args={[0.55, 0.7, 24]} />
          <meshBasicMaterial color="#228be6" transparent opacity={0.55} />
        </mesh>
      ) : null}

      {/* 기둥 */}
      {(
        [
          [-0.7, 1.35, 0],
          [0.7, 1.35, 0],
          [-0.7, 1.35, -0.7],
          [0.7, 1.35, -0.7],
        ] as [number, number, number][]
      ).map((pos) => (
        <mesh key={`${label}-${pos.join(',')}`} position={pos}>
          <boxGeometry args={[0.08, 2.7, 0.08]} />
          <meshStandardMaterial color="#495057" />
        </mesh>
      ))}

      {SHELF_HEIGHTS.map((height, shelfIndex) => (
        <group key={`${label}-shelf-${height}`}>
          <mesh position={[0, height, -0.35]}>
            <boxGeometry args={[1.5, 0.06, 0.9]} />
            <meshStandardMaterial color="#868e96" />
          </mesh>
          {/* LED 바 */}
          <mesh position={[0, height + 0.28, -0.35]}>
            <boxGeometry args={[1.35, 0.03, 0.08]} />
            <meshStandardMaterial
              color="#fff3bf"
              emissive="#ffd43b"
              emissiveIntensity={0.15 + ledRatio * 1.6}
            />
          </mesh>
          {/* 딸기 포트 3개 */}
          {[-0.45, 0, 0.45].map((x) => (
            <StrawberryPlant
              key={`${label}-p-${shelfIndex}-${x}`}
              position={[x, height + 0.08, -0.35]}
            />
          ))}
          {/* 관수 물방울 (가동 시만) */}
          {irrigating
            ? [-0.3, 0.3].map((x) => (
                <mesh
                  key={`${label}-drop-${shelfIndex}-${x}`}
                  position={[x, height + 0.2, -0.2]}
                >
                  <sphereGeometry args={[0.025, 6, 6]} />
                  <meshStandardMaterial
                    color="#74c0fc"
                    transparent
                    opacity={0.75}
                  />
                </mesh>
              ))
            : null}
        </group>
      ))}
    </group>
  )
}
