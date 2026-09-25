/**
 * 센서 마커 + 클릭 선택 (5단계 Day 19, Day20+ GLB).
 *
 * 온·습도·배지수분 → temp-moisture-sensor.glb + 상태 글로우
 * 그 외 → 기존 구체 마커
 *
 * 색 = metricStatus(참값). danger 는 점멸.
 * 클릭 → store.selectSensor + chartMetric 연동.
 */

import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import type { Group, Mesh } from 'three'

import type { FarmStateSnapshot, SensorSummary } from '../api/farms'
import {
  STATUS_COLOR,
  metricStatus,
  sensorTypeToMetric,
  type StatusLevel,
} from './statusColors'
import {
  TempMoistureSensorModel,
  usesTempMoistureModel,
} from './TempMoistureSensorModel'

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
  if (sensor.sensor_type === 'substrate_moisture') {
    // 딸기 거터 배지 근처 — 프로브처럼
    return [1.15 + (index % 2) * 0.9, 1.22, -0.4 - (index % 3) * 0.85]
  }
  if (sensor.sensor_type === 'ppfd') {
    return [1.0 + (index % 3) * 1.1, 1.55, -0.5 - (index % 4) * 0.8]
  }
  if (sensor.sensor_type === 'temperature') {
    // 입구 측면 벽 — 온습도 보드
    return [-3.75, 1.55, 1.65]
  }
  if (sensor.sensor_type === 'humidity') {
    // 온도 센서 옆 (같은 보드 영역)
    return [-3.75, 1.55, 1.35]
  }
  // CO₂ 등 — 포도 베이 입구 측면
  return [-3.8, 1.7 + (index % 3) * 0.3, 1.0 - index * 0.12]
}

function StatusGlow({
  level,
  selected,
}: {
  level: StatusLevel
  selected: boolean
}) {
  const meshRef = useRef<Mesh>(null)
  const color = STATUS_COLOR[level]

  useFrame(({ clock }) => {
    if (!meshRef.current) return
    const mat = meshRef.current.material as {
      emissiveIntensity: number
      opacity: number
    }
    if (level === 'danger') {
      const blink = 0.35 + 0.65 * Math.abs(Math.sin(clock.elapsedTime * 6))
      mat.emissiveIntensity = (selected ? 1.1 : 0.7) * blink
      mat.opacity = 0.35 + 0.35 * blink
    } else {
      mat.emissiveIntensity = selected ? 0.85 : 0.4
      mat.opacity = selected ? 0.55 : 0.35
    }
  })

  return (
    <mesh ref={meshRef} position={[0, -0.02, 0.04]} rotation={[Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.09, 0.14, 28]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.4}
        transparent
        opacity={0.4}
        depthWrite={false}
      />
    </mesh>
  )
}

function GlbSensorMarker({
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
  const groupRef = useRef<Group>(null)

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    if (level === 'danger') {
      const blink = 0.92 + 0.08 * Math.abs(Math.sin(clock.elapsedTime * 6))
      groupRef.current.scale.setScalar(selected ? 1.12 * blink : blink)
    } else {
      groupRef.current.scale.setScalar(selected ? 1.12 : 1)
    }
  })

  return (
    <group
      ref={groupRef}
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect()
      }}
    >
      <TempMoistureSensorModel />
      <StatusGlow level={level} selected={selected} />
      {/* 클릭 히트 영역 (칩이 작아 클릭이 어려울 때) */}
      <mesh visible={false}>
        <boxGeometry args={[0.22, 0.22, 0.12]} />
        <meshBasicMaterial />
      </mesh>
    </group>
  )
}

function SphereSensorMarker({
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
        const value = metric && state ? state[metric] : Number.NaN
        const level =
          metric && Number.isFinite(value)
            ? metricStatus(metric, value, { stale })
            : ('stale' as StatusLevel)
        return {
          sensor,
          position: positionForSensor(sensor, index),
          level,
          metric,
          useGlb: usesTempMoistureModel(sensor.sensor_type),
        }
      }),
    [sensors, state, stale],
  )

  return (
    <group>
      {items.map(({ sensor, position, level, metric, useGlb }) =>
        useGlb ? (
          <GlbSensorMarker
            key={sensor.id}
            position={position}
            level={level}
            selected={sensor.id === selectedSensorId}
            onSelect={() => onSelect(sensor.id, metric)}
          />
        ) : (
          <SphereSensorMarker
            key={sensor.id}
            position={position}
            level={level}
            selected={sensor.id === selectedSensorId}
            onSelect={() => onSelect(sensor.id, metric)}
          />
        ),
      )}
    </group>
  )
}
