/**
 * 통합 3D 관제 씬 (5단계 Day 19).
 *
 * =============================================================================
 * 구성
 * -----------------------------------------------------------------------------
 * - GrapeCorridor: 포도 터널 전경 (아치·봉지·캐노피)
 * - StrawberryRack ×2: 딸기 수직 재배 + LED/관수
 * - SensorMarkers: 참값 기반 색 + 클릭 선택
 * - ActuatorVisuals: 팬 회전 · HVAC/제습 배지 · 관수 펄스
 *
 * store 구독으로 KPI/차트/상세와 동일 소스를 쓴다.
 * 설계: 3D는 CAD가 아니라 상태 탐색 인터페이스.
 */
import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'

import { useRealtimeStore } from '../store/realtimeStore'
import { ActuatorVisuals, actuatorRatios } from './ActuatorVisuals'
import { GrapeCorridor } from './GrapeCorridor'
import { Room } from './Room'
import { SensorMarkers } from './SensorMarkers'
import { StrawberryRack } from './StrawberryRack'
import type { SensorMetricKey } from './statusColors'

const STRAWBERRY_POSITIONS: Array<{
  position: [number, number, number]
  label: string
}> = [
  { position: [2.6, 0, -0.2], label: 'S1' },
  { position: [4.0, 0, -0.2], label: 'S2' },
]

export function GrowingRoomScene() {
  const state = useRealtimeStore((s) => s.state)
  const sensors = useRealtimeStore((s) => s.sensors)
  const actuators = useRealtimeStore((s) => s.actuators)
  const stale = useRealtimeStore((s) => s.stale)
  const selectedSensorId = useRealtimeStore((s) => s.selectedSensorId)
  const selectedActuatorId = useRealtimeStore((s) => s.selectedActuatorId)
  const selectSensor = useRealtimeStore((s) => s.selectSensor)
  const selectActuator = useRealtimeStore((s) => s.selectActuator)
  const setChartMetric = useRealtimeStore((s) => s.setChartMetric)

  const { led, irrigation } = actuatorRatios(actuators)

  return (
    <Canvas
      // 터널 입구에서 안쪽(+소실점)과 딸기 랙이 같이 보이게
      camera={{ position: [3.8, 3.4, 7.2], fov: 40 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true }}
      onPointerMissed={() => {
        selectSensor(null)
        selectActuator(null)
      }}
    >
      <color attach="background" args={['#cfe0d4']} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 9, 5]} intensity={1.05} castShadow />
      <hemisphereLight args={['#f3f7f4', '#6b8f71', 0.4]} />
      {/* LED 가동 시 보조 점광 */}
      {led > 0 ? (
        <pointLight
          position={[3.2, 2.8, 0]}
          intensity={led * 2.2}
          color="#ffe066"
          distance={8}
        />
      ) : null}

      <Room />
      <GrapeCorridor />

      {STRAWBERRY_POSITIONS.map((rack) => (
        <StrawberryRack
          key={rack.label}
          position={rack.position}
          label={rack.label}
          ledRatio={led}
          irrigating={irrigation > 0}
          selected={false}
          onSelect={() => {
            const hit = actuators.find((a) => a.actuator_type === 'led')
            if (hit) selectActuator(hit.id)
          }}
        />
      ))}

      <SensorMarkers
        sensors={sensors}
        state={state}
        stale={stale}
        selectedSensorId={selectedSensorId}
        onSelect={(sensorId, metricKey) => {
          selectSensor(sensorId)
          if (metricKey) {
            setChartMetric(metricKey as SensorMetricKey)
          }
        }}
      />

      <ActuatorVisuals
        actuators={actuators}
        selectedActuatorId={selectedActuatorId}
        onSelect={selectActuator}
      />

      <OrbitControls
        makeDefault
        target={[0.6, 1.3, -1.2]}
        minPolarAngle={0.3}
        maxPolarAngle={1.4}
        minDistance={4}
        maxDistance={16}
        enablePan={false}
      />
    </Canvas>
  )
}
