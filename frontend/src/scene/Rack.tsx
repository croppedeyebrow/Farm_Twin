/**
 * 수직 재배 랙 골격 (1단계 Day 3 — 레거시).
 *
 * Day 19 부터 딸기 장면은 `StrawberryRack` 을 사용한다.
 * 이 파일은 단순 골격 참고용으로 남긴다.
 */
import { SHELF_HEIGHTS } from './rackLayout'

type RackProps = {
  position: [number, number, number]
  label: string
}

export function Rack({ position, label }: RackProps) {
  return (
    <group position={position}>
      <mesh position={[-0.7, 1.35, 0]}>
        <boxGeometry args={[0.08, 2.7, 0.08]} />
        <meshStandardMaterial color="#4d5c53" />
      </mesh>
      <mesh position={[0.7, 1.35, 0]}>
        <boxGeometry args={[0.08, 2.7, 0.08]} />
        <meshStandardMaterial color="#4d5c53" />
      </mesh>
      <mesh position={[-0.7, 1.35, -0.7]}>
        <boxGeometry args={[0.08, 2.7, 0.08]} />
        <meshStandardMaterial color="#4d5c53" />
      </mesh>
      <mesh position={[0.7, 1.35, -0.7]}>
        <boxGeometry args={[0.08, 2.7, 0.08]} />
        <meshStandardMaterial color="#4d5c53" />
      </mesh>

      {SHELF_HEIGHTS.map((height) => (
        <mesh key={`${label}-${height}`} position={[0, height, -0.35]}>
          <boxGeometry args={[1.5, 0.06, 0.9]} />
          <meshStandardMaterial color="#6f8578" />
        </mesh>
      ))}
    </group>
  )
}
