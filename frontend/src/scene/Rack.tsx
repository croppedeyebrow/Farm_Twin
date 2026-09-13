type RackProps = {
  position: [number, number, number]
  label: string
}

const SHELF_HEIGHTS = [0.45, 1.05, 1.65, 2.25]

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
