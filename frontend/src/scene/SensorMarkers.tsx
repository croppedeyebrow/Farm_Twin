/**
 * 센서 마커 + 클릭 선택 (5단계 Day 19).
 *
 * 색 = metricStatus(참값). danger 는 점멸.
 * 클릭 → store.selectSensor + chartMetric 연동.
 */

import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import type { Mesh } from 'three'

import type { FarmStateSnapshot, SensorSummary } from '../api/farms'
import {
  STATUS_COLOR,
  metricStatus,
  sensorTypeToMetric,
  type StatusLevel,
} from './statusColors'

type SensorMarkersProps = {
  sensors: SensorSummary[]
  state: FarmStateSnapshot | null
  stale: boolean
  selectedSensorId: string | null
  onSelect: (sensorId: string, metricKey: string | null) => void
}

/** 센서 타입별 기본 월드 위치 (포도 베이 / 딸기 거터) */
function positionForSensor(
  sensor: SensorSummary,
  index: number,
): [number, number, number] {
  if (
    sensor.sensor_type === 'substrate_moisture' ||
    sensor.sensor_type === 'ppfd'
  ) {
    // 딸기 거터 높이 근처
    return [1.0 + (index % 3) * 1.1, 1.25, -0.5 - (index % 4) * 0.8]
  }
  // 환경 센서 — 포도 베이 입구 측면
  return [-3.6, 1.5 + (index % 3) * 0.4, 2.2 - index * 0.2]
}

function SensorMarker({
  position,
  level,
  selected,
  onSelect,
}: {
  position: [number, number, number]
  level: StatusLevel
  selected: boolean
  onSelect: () => void
}) {
  const meshRef = useRef<Mesh>(null)
  const color = STATUS_COLOR[level]

  useFrame(({ clock }) => {
    if (!meshRef.current) return
    if (level === 'danger') {
      const blink = 0.45 + 0.55 * Math.abs(Math.sin(clock.elapsedTime * 6))
      meshRef.current.scale.setScalar(selected ? 1.25 * blink : blink)
    } else {
      meshRef.current.scale.setScalar(selected ? 1.25 : 1)
    }
  })

  return (
    <mesh
      ref={meshRef}
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect()
      }}
    >
      <sphereGeometry args={[0.11, 16, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={selected ? 0.55 : 0.25}
      />
    </mesh>
  )
}

export function SensorMarkers({
  sensors,
  state,
  stale,
  selectedSensorId,
  onSelect,
}: SensorMarkersProps) {
  const items = useMemo(
    () =>
      sensors.map((sensor, index) => {
        const metric = sensorTypeToMetric(sensor.sensor_type)
        const value =
          metric && state ? state[metric] : Number.NaN
        const level =
          metric && Number.isFinite(value)
            ? metricStatus(metric, value, { stale })
            : ('stale' as StatusLevel)
        return {
          sensor,
          position: positionForSensor(sensor, index),
          level,
          metric,
        }
      }),
    [sensors, state, stale],
  )

  return (
    <group>
      {items.map(({ sensor, position, level, metric }) => (
        <SensorMarker
          key={sensor.id}
          position={position}
          level={level}
          selected={sensor.id === selectedSensorId}
          onSelect={() => onSelect(sensor.id, metric)}
        />
      ))}
    </group>
  )
}
