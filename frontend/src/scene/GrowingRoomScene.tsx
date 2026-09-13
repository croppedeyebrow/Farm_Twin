/**
 * 빈 3D 재배실 씬 (1단계 Day 3).
 *
 * 설계 문서 원칙: 3D는 CAD가 아니라 상태 탐색 인터페이스다.
 * 1단계에서는 정밀 모델 대신 방 + 랙 골격만 두고,
 * 이후 단계에서 센서/액추에이터 상태 색을 얹는다.
 */
import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Rack } from './Rack'
import { Room } from './Room'

/** 재배실 안쪽에 나란히 배치한 랙 3개의 월드 좌표 (x, y, z). */
const RACK_POSITIONS: [number, number, number][] = [
  [-2.2, 0, -0.4],
  [0, 0, -0.4],
  [2.2, 0, -0.4],
]

export function GrowingRoomScene() {
  return (
    <Canvas
      // 대각선에서 방 전체를 보도록 초기 카메라 설정
      camera={{ position: [5.5, 4.2, 6.5], fov: 42 }}
      // 고해상도 디스플레이에서만 DPR 을 올려 성능/화질 타협
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

      {/* 팬 금지·상하 각도 제한: 바닥 아래로 카메라가 파고들지 않게 */}
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
