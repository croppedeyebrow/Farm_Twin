import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Rack } from './Rack'
import { Room } from './Room'

const RACK_POSITIONS: [number, number, number][] = [
  [-2.2, 0, -0.4],
  [0, 0, -0.4],
  [2.2, 0, -0.4],
]

export function GrowingRoomScene() {
  return (
    <Canvas
      camera={{ position: [5.5, 4.2, 6.5], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true }}
    >
      <color attach="background" args={['#d7e4db']} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[6, 8, 4]} intensity={1.15} castShadow />
      <hemisphereLight args={['#f3f7f4', '#7f9a88', 0.35]} />

      <Room />
      {RACK_POSITIONS.map((position, index) => (
        <Rack key={position.join('-')} position={position} label={`R${index + 1}`} />
      ))}

      <OrbitControls
        makeDefault
        target={[0, 1.2, 0]}
        minPolarAngle={0.35}
        maxPolarAngle={1.35}
        minDistance={4}
        maxDistance={14}
        enablePan={false}
      />
    </Canvas>
  )
}
