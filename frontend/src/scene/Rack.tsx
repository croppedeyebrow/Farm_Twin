/**
 * 수직 재배 랙 골격 (1단계 Day 3).
 *
 * 기둥 4개 + 선반 4단. 센서/작물/LED 는 이후 단계에서 선반 위에 올린다.
 */
type RackProps = {
  /** 랙 원점의 월드 좌표 */
  position: [number, number, number]
  /** React key / 디버그용 라벨 (R1, R2, ...) */
  label: string
}

/** 선반 높이(y). 아래에서 위로 4단. */
const SHELF_HEIGHTS = [0.45, 1.05, 1.65, 2.25]

export function Rack({ position, label }: RackProps) {
  return (
    <group position={position}>
      {/* 네 모서리 기둥 */}
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

      {/* 선반 플레이트 */}
      {SHELF_HEIGHTS.map((height) => (
        <mesh key={`${label}-${height}`} position={[0, height, -0.35]}>
          <boxGeometry args={[1.5, 0.06, 0.9]} />
          <meshStandardMaterial color="#6f8578" />
        </mesh>
      ))}
    </group>
  )
}
