/**
 * 통합 3D 관제 씬.
 *
 * =============================================================================
 * 구성 (레퍼런스 반영)
 * -----------------------------------------------------------------------------
 * - GreenhouseShell: 멀티스팬 아치 외피·골조·기초·천장 그리드
 * - GrapeCorridor ×2: 좌측·중앙 포도
 * - StrawberryRack ×4: 중앙~우측 딸기 (벽 안쪽)
 * - SensorMarkers / ActuatorVisuals
 *
 * 레퍼런스: docs/refs/greenhouse-exterior.jpg, strawberry-interior.png, strawberry line.png
 * 작물 GLB: public/models/strawberry-set.glb, grape.glb
 */

import { OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'

import { useRealtimeStore } from '../store/realtimeStore'
import { ActuatorVisuals, actuatorRatios } from './ActuatorVisuals'
import { GrapeCorridor } from './GrapeCorridor'
import { GreenhouseShell } from './GreenhouseShell'
import { GRAPE_CORRIDOR_PLACEMENTS, STRAWBERRY_ROW_X } from './rackLayout'
import { SensorMarkers } from './SensorMarkers'
import { StrawberryRack } from './StrawberryRack'
import type { SensorMetricKey } from './statusColors'

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
      // 딸기 통로 시점 (내부 레퍼런스와 비슷한 소실점)
      camera={{ position: [0.15, 1.55, 6.8], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true }}
      onPointerMissed={() => {
        selectSensor(null)
        selectActuator(null)
      }}
    >
      <color attach="background" args={['#4d9fd6']} />
      <fog attach="fog" args={['#8ecae6', 28, 55]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[10, 14, 6]} intensity={1.25} castShadow />
      <hemisphereLight args={['#e8f4ff', '#c4b59a', 0.5]} />
      {led > 0 ? (
        <pointLight
          position={[1.2, 2.6, 0]}
          intensity={led * 2.0}
          color="#ffe066"
          distance={10}
        />
      ) : null}

      <GreenhouseShell />

      {/* 포도 — 좌측 스팬 + 중앙 공백 (주석: 포도 추가) */}
      {GRAPE_CORRIDOR_PLACEMENTS.map((g) => (
        <group key={g.label} position={g.position}>
          <GrapeCorridor />
        </group>
      ))}

      {/* 딸기 — 중앙~우측, 벽 밖으로 안 나가게 (주석: 딸기 추가) */}
      {STRAWBERRY_ROW_X.map((x, i) => (
        <StrawberryRack
          key={`row-${i}`}
          position={[x, 0, 0]}
          label={`S${i + 1}`}
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
        target={[0.4, 1.1, -1.5]}
        minPolarAngle={0.25}
        maxPolarAngle={1.45}
        minDistance={3.5}
        maxDistance={22}
        enablePan
      />
    </Canvas>
  )
}
