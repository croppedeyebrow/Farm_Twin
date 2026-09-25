/**
 * 액추에이터 비주얼 (5단계 Day 19 / 트윈 설비 구별).
 *
 * - ventilation_fan: 박공 환기팬
 * - led: StrawberryRack GrowLightStrip
 * - irrigation_pump: 바닥 물줄기
 * - hvac / dehumidifier: 천장 온·습도 조절 카세트 (LED 아님)
 */

import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import type { Group } from 'three'

import type { ActuatorSummary } from '../api/farms'
import { EAVES_HEIGHT, HALL_Z0, RIDGE_HEIGHT, SPAN_WIDTH } from './GreenhouseShell'

type ActuatorVisualsProps = {
  actuators: ActuatorSummary[]
  selectedActuatorId: string | null
  onSelect: (id: string) => void
}

function ratioOf(
  actuators: ActuatorSummary[],
  type: string,
): { ratio: number; id: string | null; mode: string } {
  const hit = actuators.find((item) => item.actuator_type === type)
  if (!hit) {
    return { ratio: 0, id: null, mode: 'off' }
  }
  // OFF 만 출력 0. manual/on/auto 는 output_ratio 사용
  if (hit.mode === 'off' || hit.output_ratio <= 0) {
    return { ratio: 0, id: hit.id, mode: hit.mode }
  }
  return { ratio: hit.output_ratio, id: hit.id, mode: hit.mode }
}

function Fan({
  position,
  speed,
  selected,
  onSelect,
}: {
  position: [number, number, number]
  speed: number
  selected: boolean
  onSelect: () => void
}) {
  const ref = useRef<Group>(null)
  useFrame((_, delta) => {
    if (ref.current && speed > 0) {
      ref.current.rotation.z += delta * (2 + speed * 10)
    }
  })
  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect()
      }}
    >
      <mesh>
        <cylinderGeometry args={[0.08, 0.08, 0.12, 10]} />
        <meshStandardMaterial color={selected ? '#228be6' : '#495057'} />
      </mesh>
      <group ref={ref}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <boxGeometry args={[0.55, 0.06, 0.04]} />
          <meshStandardMaterial color="#adb5bd" />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, Math.PI / 2]}>
          <boxGeometry args={[0.55, 0.06, 0.04]} />
          <meshStandardMaterial color="#adb5bd" />
        </mesh>
      </group>
    </group>
  )
}

function ClimateCassette({
  position,
  active,
  kind,
  selected,
  onSelect,
}: {
  position: [number, number, number]
  active: boolean
  kind: 'hvac' | 'dehumidifier'
  selected: boolean
  onSelect: () => void
}) {
  const accent = kind === 'hvac' ? '#74c0fc' : '#63e6be'
  const emissive = kind === 'hvac' ? '#4dabf7' : '#38d9a9'
  return (
    <group
      position={position}
      onClick={(event) => {
        event.stopPropagation()
        onSelect()
      }}
    >
      <mesh>
        <boxGeometry args={[0.58, 0.16, 0.34]} />
        <meshStandardMaterial
          color={selected ? '#dee2e6' : '#e9ecef'}
          roughness={0.5}
          emissive={active ? emissive : '#000000'}
          emissiveIntensity={active ? 0.25 : 0}
        />
      </mesh>
      <mesh position={[0, -0.09, 0]}>
        <boxGeometry args={[0.5, 0.03, 0.28]} />
        <meshStandardMaterial
          color={active ? accent : '#868e96'}
          emissive={active ? accent : '#000000'}
          emissiveIntensity={active ? 0.35 : 0}
        />
      </mesh>
      {selected ? (
        <mesh position={[0, 0.12, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.22, 0.3, 20]} />
          <meshBasicMaterial color="#228be6" transparent opacity={0.45} />
        </mesh>
      ) : null}
    </group>
  )
}

export function ActuatorVisuals({
  actuators,
  selectedActuatorId,
  onSelect,
}: ActuatorVisualsProps) {
  const fan = ratioOf(actuators, 'ventilation_fan')
  const hvac = ratioOf(actuators, 'hvac')
  const dehum = ratioOf(actuators, 'dehumidifier')
  const irrig = ratioOf(actuators, 'irrigation_pump')
  const climateY = EAVES_HEIGHT - 0.45 - 0.12

  return (
    <group>
      {[-SPAN_WIDTH, 0, SPAN_WIDTH].map((x) => (
        <Fan
          key={`fan-${x}`}
          position={[x, RIDGE_HEIGHT - 0.85, HALL_Z0 + 0.35]}
          speed={fan.ratio}
          selected={fan.id === selectedActuatorId}
          onSelect={() => fan.id && onSelect(fan.id)}
        />
      ))}

      <ClimateCassette
        position={[-3.8, climateY, 1.0]}
        active={hvac.ratio > 0}
        kind="hvac"
        selected={hvac.id === selectedActuatorId}
        onSelect={() => hvac.id && onSelect(hvac.id)}
      />
      <ClimateCassette
        position={[0, climateY, 1.0]}
        active={hvac.ratio > 0}
        kind="hvac"
        selected={hvac.id === selectedActuatorId}
        onSelect={() => hvac.id && onSelect(hvac.id)}
      />
      <ClimateCassette
        position={[3.8, climateY, 1.0]}
        active={dehum.ratio > 0}
        kind="dehumidifier"
        selected={dehum.id === selectedActuatorId}
        onSelect={() => dehum.id && onSelect(dehum.id)}
      />
      <ClimateCassette
        position={[-3.8, climateY, -2.7]}
        active={dehum.ratio > 0}
        kind="dehumidifier"
        selected={dehum.id === selectedActuatorId}
        onSelect={() => dehum.id && onSelect(dehum.id)}
      />

      {irrig.ratio > 0 ? (
        <mesh
          position={[1.3, 0.08, -1.2]}
          rotation={[-Math.PI / 2, 0, 0]}
          onClick={(event) => {
            event.stopPropagation()
            if (irrig.id) onSelect(irrig.id)
          }}
        >
          <circleGeometry args={[0.35 + irrig.ratio * 0.2, 20]} />
          <meshStandardMaterial
            color="#74c0fc"
            transparent
            opacity={0.35 + irrig.ratio * 0.3}
          />
        </mesh>
      ) : null}
    </group>
  )
}

export function actuatorRatios(actuators: ActuatorSummary[]) {
  return {
    led: ratioOf(actuators, 'led').ratio,
    irrigation: ratioOf(actuators, 'irrigation_pump').ratio,
  }
}
