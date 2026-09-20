/**
 * 재배실 건축 골격: 바닥 · 뒷벽 · 좌우벽 · 반투명 천장 (1단계 Day 3).
 *
 * Day 19: 포도 터널·딸기 랙이 이 방 안에 배치된다.
 * 단위는 Three.js 월드 유닛(대략 m 스케일 감각).
 */
export function Room() {
  return (
    <group>
      {/* 바닥 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color="#c5d5c9" />
      </mesh>

      {/* 뒷벽 */}
      <mesh position={[0, 1.8, -3.9]}>
        <boxGeometry args={[10, 3.6, 0.12]} />
        <meshStandardMaterial color="#9bb5a4" />
      </mesh>

      {/* 왼쪽 벽 */}
      <mesh position={[-4.94, 1.8, 0]}>
        <boxGeometry args={[0.12, 3.6, 8]} />
        <meshStandardMaterial color="#a7bdae" />
      </mesh>

      {/* 오른쪽 벽 */}
      <mesh position={[4.94, 1.8, 0]}>
        <boxGeometry args={[0.12, 3.6, 8]} />
        <meshStandardMaterial color="#a7bdae" />
      </mesh>

      {/* 천장 — 내부가 보이도록 반투명 */}
      <mesh position={[0, 3.62, 0]}>
        <boxGeometry args={[10, 0.08, 8]} />
        <meshStandardMaterial color="#b7c8bc" transparent opacity={0.55} />
      </mesh>
    </group>
  )
}
