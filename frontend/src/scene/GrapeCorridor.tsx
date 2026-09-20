/**
 * 포도 터널 전경 (5단계 Day 19).
 *
 * 참고: 하우스타널 중앙 통로 + 아치 + 백(봉지) 포도.
 * CAD 정밀 복제가 아니라 **반복 모듈**로 상태 탐색 앵커를 만든다.
 *
 * 축
 * --
 * -Z 방향이 터널 안쪽(소실점). 카메라는 +Z 쪽에서 내려다본다.
 */

import { useMemo } from 'react'
import { DoubleSide } from 'three'

const ARCH_COUNT = 8
const ARCH_SPACING = 1.15

function Hoop({ z }: { z: number }) {
  // 얇은 박스로 아치를 근사 (토러스보다 가볍고 읽기 쉬움)
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

function GrapeBag({
  position,
}: {
  position: [number, number, number]
}) {
  // 반투명 흰 봉지 + 안쪽 포도 알 (단순 구체)
  return (
    <group position={position}>
      <mesh position={[0, -0.12, 0]}>
        <coneGeometry args={[0.09, 0.22, 8]} />
        <meshStandardMaterial
          color="#f8f9fa"
          transparent
          opacity={0.72}
          roughness={0.85}
        />
      </mesh>
      <mesh position={[0, -0.08, 0]}>
        <sphereGeometry args={[0.045, 8, 8]} />
        <meshStandardMaterial color="#5f3dc4" roughness={0.4} />
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
  const bags = useMemo(() => {
    const items: [number, number, number][] = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      items.push([-1.15, 1.55, z - 0.2])
      items.push([-1.05, 1.35, z + 0.15])
      items.push([1.15, 1.55, z - 0.2])
      items.push([1.05, 1.4, z + 0.1])
    }
    return items
  }, [])

  const leaves = useMemo(() => {
    const items: [number, number, number][] = []
    for (let i = 0; i < ARCH_COUNT; i += 1) {
      const z = -i * ARCH_SPACING
      for (let x = -1.3; x <= 1.3; x += 0.45) {
        items.push([x, 2.35 + (Math.abs(x) % 0.2), z])
      }
    }
    return items
  }, [])

  return (
    <group position={[0, 0, 1.2]}>
      {/* 중앙 백색 통로 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -4]} receiveShadow>
        <planeGeometry args={[1.1, 10]} />
        <meshStandardMaterial color="#f1f3f5" />
      </mesh>
      {/* 좌우 배지/토양 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-1.4, 0.02, -4]} receiveShadow>
        <planeGeometry args={[1.6, 10]} />
        <meshStandardMaterial color="#5c4033" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[1.4, 0.02, -4]} receiveShadow>
        <planeGeometry args={[1.6, 10]} />
        <meshStandardMaterial color="#5c4033" />
      </mesh>

      {/* 수직 지주 */}
      {Array.from({ length: ARCH_COUNT }, (_, i) => {
        const z = -i * ARCH_SPACING
        return (
          <group key={`post-${z}`}>
            <mesh position={[-1.2, 0.9, z]}>
              <cylinderGeometry args={[0.035, 0.035, 1.8, 6]} />
              <meshStandardMaterial color="#8b7355" />
            </mesh>
            <mesh position={[1.2, 0.9, z]}>
              <cylinderGeometry args={[0.035, 0.035, 1.8, 6]} />
              <meshStandardMaterial color="#8b7355" />
            </mesh>
          </group>
        )
      })}

      {Array.from({ length: ARCH_COUNT }, (_, i) => (
        <Hoop key={`hoop-${i}`} z={-i * ARCH_SPACING} />
      ))}

      {bags.map((pos, index) => (
        <GrapeBag key={`bag-${index}`} position={pos} />
      ))}
      {leaves.map((pos, index) => (
        <CanopyLeaf key={`leaf-${index}`} position={pos} />
      ))}
    </group>
  )
}
