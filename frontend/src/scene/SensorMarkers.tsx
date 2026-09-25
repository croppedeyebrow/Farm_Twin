/**
 * 계측·센서 3D 비주얼 (트윈 대시보드 방향).
 *
 * 스크린샷 주석 매핑
 * ------------------
 * - 입구 센서     → CO₂ 박스 (입구 골조)
 * - 온습도계      → 천장 현수 화이트 바 (온도+습도)
 * - 영양 체크     → 딸기 거터 배지 프로브
 * - PPFD 측정계   → LED 아래 PAR 미터
 * - 온·습도 칩 GLB → 온습도계 바에 보조 장착
 */

import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import type { Group, Mesh } from 'three'

import type { FarmStateSnapshot, SensorSummary } from '../api/farms'
import { GUTTER_HEIGHT, STRAWBERRY_ROW_X } from './rackLayout'
import {
  STATUS_COLOR,
  metricStatus,
  sensorTypeToMetric,
  type StatusLevel,
} from './statusColors'
import { TempMoistureSensorModel } from './TempMoistureSensorModel'

type SensorMarkersProps = {
  sensors: SensorSummary[]
  state: FarmStateSnapshot | null
  stale: boolean
  selectedSensorId: string | null
  onSelect: (sensorId: string, metricKey: string | null) => void
}

type MarkerItem = {
  sensor: SensorSummary
  level: StatusLevel
  metric: ReturnType<typeof sensorTypeToMetric>
}

function StatusHalo({
  level,
  selected,
  radius = 0.12,
}: {
  level: StatusLevel
  selected: boolean
  radius?: number
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
      mat.emissiveIntensity = (selected ? 1.0 : 0.65) * blink
      mat.opacity = 0.3 + 0.35 * blink
    } else {
      mat.emissiveIntensity = selected ? 0.8 : 0.35
      mat.opacity = selected ? 0.5 : 0.32
    }
  })

  return (
    <mesh ref={meshRef} rotation={[Math.PI / 2, 0, 0]}>
      <ringGeometry args={[radius * 0.7, radius, 24]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.35}
        transparent
        opacity={0.35}
        depthWrite={false}
      />
    </mesh>
  )
}

/** 입구 골조 — CO₂ / 입구 환경 센서 박스 */
function EntranceSensorBox({
  level,
  selected,
  onSelect,
}: {
  level: StatusLevel
  selected: boolean
  onSelect: () => void
}) {
  const color = STATUS_COLOR[level]
  return (
    <group
      // 입구(+Z) 중앙 통로 기둥 높이
      position={[0.05, 2.15, 5.35]}
      onClick={(e) => {
        e.stopPropagation()
        onSelect()
      }}
    >
      <mesh>
        <boxGeometry args={[0.14, 0.2, 0.1]} />
        <meshStandardMaterial
          color={selected ? '#343a40' : '#212529'}
          roughness={0.55}
          metalness={0.15}
        />
      </mesh>
      <mesh position={[0, 0.02, 0.055]}>
        <boxGeometry args={[0.08, 0.06, 0.02]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={selected ? 0.7 : 0.35}
        />
      </mesh>
      <StatusHalo level={level} selected={selected} radius={0.16} />
    </group>
  )
}

/**
 * 온습도계 — 작물 위 현수 화이트 바.
 * temperature / humidity 가 각각 바의 한쪽을 클릭한다.
 */
function ThermoHygrometerBar({
  temp,
  humidity,
  selectedSensorId,
  onSelect,
}: {
  temp: MarkerItem | null
  humidity: MarkerItem | null
  selectedSensorId: string | null
  onSelect: (sensorId: string, metricKey: string | null) => void
}) {
  const groupRef = useRef<Group>(null)
  const anySelected =
    (temp && temp.sensor.id === selectedSensorId) ||
    (humidity && humidity.sensor.id === selectedSensorId)

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const danger =
      temp?.level === 'danger' || humidity?.level === 'danger'
    if (danger) {
      const blink = 0.96 + 0.04 * Math.abs(Math.sin(clock.elapsedTime * 5))
      groupRef.current.scale.setScalar(blink)
    } else {
      groupRef.current.scale.setScalar(anySelected ? 1.03 : 1)
    }
  })

  // 포도·딸기 사이 통로 위, 행 방향(Z)으로 긴 바
  return (
    <group ref={groupRef} position={[-0.85, 2.05, 0.4]}>
      {/* 현수 와이어 */}
      <mesh position={[-0.9, 0.55, 0]}>
        <cylinderGeometry args={[0.006, 0.006, 1.1, 5]} />
        <meshStandardMaterial color="#868e96" />
      </mesh>
      <mesh position={[0.9, 0.55, 0]}>
        <cylinderGeometry args={[0.006, 0.006, 1.1, 5]} />
        <meshStandardMaterial color="#868e96" />
      </mesh>

      {/* 화이트 하우징 */}
      <mesh>
        <boxGeometry args={[2.05, 0.09, 0.14]} />
        <meshStandardMaterial color="#f8f9fa" roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.04, 0]}>
        <boxGeometry args={[1.9, 0.03, 0.1]} />
        <meshStandardMaterial color="#dee2e6" roughness={0.55} />
      </mesh>

      {temp ? (
        <group
          position={[-0.55, -0.02, 0.08]}
          onClick={(e) => {
            e.stopPropagation()
            onSelect(temp.sensor.id, temp.metric)
          }}
        >
          <TempMoistureSensorModel scale={38} />
          <StatusHalo
            level={temp.level}
            selected={temp.sensor.id === selectedSensorId}
            radius={0.1}
          />
          <mesh visible={false} position={[0, 0, 0.05]}>
            <boxGeometry args={[0.7, 0.2, 0.2]} />
            <meshBasicMaterial />
          </mesh>
        </group>
      ) : null}

      {humidity ? (
        <group
          position={[0.55, -0.02, 0.08]}
          onClick={(e) => {
            e.stopPropagation()
            onSelect(humidity.sensor.id, humidity.metric)
          }}
        >
          <TempMoistureSensorModel scale={38} />
          <StatusHalo
            level={humidity.level}
            selected={humidity.sensor.id === selectedSensorId}
            radius={0.1}
          />
          <mesh visible={false} position={[0, 0, 0.05]}>
            <boxGeometry args={[0.7, 0.2, 0.2]} />
            <meshBasicMaterial />
          </mesh>
        </group>
      ) : null}
    </group>
  )
}

/** 딸기 거터 — 배지/영양 프로브 */
function NutritionProbe({
  level,
  selected,
  onSelect,
  rowIndex = 0,
}: {
  level: StatusLevel
  selected: boolean
  onSelect: () => void
  rowIndex?: number
}) {
  const x = STRAWBERRY_ROW_X[Math.min(rowIndex, STRAWBERRY_ROW_X.length - 1)]
  const color = STATUS_COLOR[level]
  const y = GUTTER_HEIGHT + 0.08

  return (
    <group
      position={[x + 0.12, y, -1.1]}
      onClick={(e) => {
        e.stopPropagation()
        onSelect()
      }}
    >
      {/* 프로브 스틱 */}
      <mesh position={[0, -0.08, 0]} rotation={[0.35, 0, 0.2]}>
        <cylinderGeometry args={[0.012, 0.008, 0.28, 6]} />
        <meshStandardMaterial color="#adb5bd" metalness={0.4} />
      </mesh>
      {/* 헤드 */}
      <mesh position={[0.02, 0.06, 0.04]}>
        <boxGeometry args={[0.1, 0.07, 0.06]} />
        <meshStandardMaterial color="#e9ecef" roughness={0.45} />
      </mesh>
      <mesh position={[0.02, 0.06, 0.075]}>
        <circleGeometry args={[0.018, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={selected ? 0.85 : 0.4}
        />
      </mesh>
      <StatusHalo level={level} selected={selected} radius={0.14} />
    </group>
  )
}

/** LED 아래 PPFD(광양자) 측정계 */
function PpfdMeter({
  level,
  selected,
  onSelect,
}: {
  level: StatusLevel
  selected: boolean
  onSelect: () => void
}) {
  const color = STATUS_COLOR[level]
  const x = STRAWBERRY_ROW_X[1]
  return (
    <group
      position={[x, GUTTER_HEIGHT + 0.55, 0.8]}
      onClick={(e) => {
        e.stopPropagation()
        onSelect()
      }}
    >
      <mesh>
        <boxGeometry args={[0.16, 0.05, 0.12]} />
        <meshStandardMaterial color="#495057" roughness={0.5} />
      </mesh>
      <mesh position={[0, -0.04, 0]} rotation={[0.4, 0, 0]}>
        <cylinderGeometry args={[0.035, 0.04, 0.06, 10]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={selected ? 0.6 : 0.25}
        />
      </mesh>
      <mesh position={[0, 0.12, 0]}>
        <cylinderGeometry args={[0.004, 0.004, 0.22, 4]} />
        <meshStandardMaterial color="#868e96" />
      </mesh>
      <StatusHalo level={level} selected={selected} radius={0.13} />
    </group>
  )
}

export function SensorMarkers({
  sensors,
  state,
  stale,
  selectedSensorId,
  onSelect,
}: SensorMarkersProps) {
  const byType = useMemo(() => {
    const map = new Map<string, MarkerItem>()
    for (const sensor of sensors) {
      const metric = sensorTypeToMetric(sensor.sensor_type)
      const value = metric && state ? state[metric] : Number.NaN
      const level =
        metric && Number.isFinite(value)
          ? metricStatus(metric, value, { stale })
          : ('stale' as StatusLevel)
      map.set(sensor.sensor_type, { sensor, level, metric })
    }
    return map
  }, [sensors, state, stale])

  const temp = byType.get('temperature') ?? null
  const humidity = byType.get('humidity') ?? null
  const co2 = byType.get('co2') ?? null
  const moisture = byType.get('substrate_moisture') ?? null
  const ppfd = byType.get('ppfd') ?? null

  return (
    <group>
      {co2 ? (
        <EntranceSensorBox
          level={co2.level}
          selected={co2.sensor.id === selectedSensorId}
          onSelect={() => onSelect(co2.sensor.id, co2.metric)}
        />
      ) : null}

      <ThermoHygrometerBar
        temp={temp}
        humidity={humidity}
        selectedSensorId={selectedSensorId}
        onSelect={onSelect}
      />

      {moisture ? (
        <NutritionProbe
          level={moisture.level}
          selected={moisture.sensor.id === selectedSensorId}
          onSelect={() => onSelect(moisture.sensor.id, moisture.metric)}
          rowIndex={0}
        />
      ) : null}

      {ppfd ? (
        <PpfdMeter
          level={ppfd.level}
          selected={ppfd.sensor.id === selectedSensorId}
          onSelect={() => onSelect(ppfd.sensor.id, ppfd.metric)}
        />
      ) : null}
    </group>
  )
}
