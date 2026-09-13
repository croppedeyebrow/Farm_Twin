export function Room() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[10, 8]} />
        <meshStandardMaterial color="#c5d5c9" />
      </mesh>

      <mesh position={[0, 1.8, -3.9]}>
        <boxGeometry args={[10, 3.6, 0.12]} />
        <meshStandardMaterial color="#9bb5a4" />
      </mesh>

      <mesh position={[-4.94, 1.8, 0]}>
        <boxGeometry args={[0.12, 3.6, 8]} />
        <meshStandardMaterial color="#a7bdae" />
      </mesh>

      <mesh position={[4.94, 1.8, 0]}>
        <boxGeometry args={[0.12, 3.6, 8]} />
        <meshStandardMaterial color="#a7bdae" />
      </mesh>

      <mesh position={[0, 3.62, 0]}>
        <boxGeometry args={[10, 0.08, 8]} />
        <meshStandardMaterial color="#b7c8bc" transparent opacity={0.55} />
      </mesh>
    </group>
  )
}
