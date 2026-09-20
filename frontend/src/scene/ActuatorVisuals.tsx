/**
 * 액추에이터 비주얼 (5단계 Day 19).
 *
 * - ventilation_fan: 회전 블레이드 (output_ratio → 각속도)
 * - led: StrawberryRack 이 담당 (여기서는 천장 보조광)
 * - irrigation_pump: 터널 바닥 물줄기 펄스
 * - hvac / dehumidifier: 상태 배지 박스
 */

import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import type { Group } from 'three'

import type { ActuatorSummary } from '../api/farms'

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
  if (!hit || hit.mode === 'off') {
    return { ratio: 0, id: hit?.id ?? null, mode: hit?.mode ?? 'off' }
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

export function ActuatorVisuals({
  actuators,
  selectedActuatorId,
  onSelect,
}: ActuatorVisualsProps) {
  const fan = ratioOf(actuators, 'ventilation_fan')
  const hvac = ratioOf(actuators, 'hvac')
  const dehum = ratioOf(actuators, 'dehumidifier')
  const irrig = ratioOf(actuators, 'irrigation_pump')

  return (
    <group>
      {/* 박공 환기팬 위치 (외피 환기창 근처) */}
      <Fan
        position={[-4.2, 3.6, -5.2]}
        speed={fan.ratio}
        selected={fan.id === selectedActuatorId}
        onSelect={() => fan.id && onSelect(fan.id)}
      />
      <Fan
        position={[0, 3.6, -5.2]}
        speed={fan.ratio}
        selected={fan.id === selectedActuatorId}
        onSelect={() => fan.id && onSelect(fan.id)}
      />
      <Fan
        position={[4.2, 3.6, -5.2]}
        speed={fan.ratio}
        selected={fan.id === selectedActuatorId}
        onSelect={() => fan.id && onSelect(fan.id)}
      />

      {/* HVAC 배지 */}
      <mesh
        position={[-5.8, 1.2, 4.5]}
        onClick={(event) => {
          event.stopPropagation()
          if (hvac.id) onSelect(hvac.id)
        }}
      >
        <boxGeometry args={[0.35, 0.55, 0.2]} />
        <meshStandardMaterial
          color={hvac.ratio > 0 ? '#74c0fc' : '#ced4da'}
          emissive={hvac.ratio > 0 ? '#4dabf7' : '#000000'}
          emissiveIntensity={hvac.ratio > 0 ? 0.4 : 0}
        />
      </mesh>

      {/* 제습기 배지 */}
      <mesh
        position={[5.8, 1.2, 4.5]}
        onClick={(event) => {
          event.stopPropagation()
          if (dehum.id) onSelect(dehum.id)
        }}
      >
        <boxGeometry args={[0.35, 0.55, 0.2]} />
        <meshStandardMaterial
          color={dehum.ratio > 0 ? '#63e6be' : '#ced4da'}
          emissive={dehum.ratio > 0 ? '#38d9a9' : '#000000'}
          emissiveIntensity={dehum.ratio > 0 ? 0.35 : 0}
        />
      </mesh>

      {/* 관수 펄스 — 딸기 통로 바닥 */}
      {irrig.ratio > 0 ? (
        <mesh
          position={[1.15, 0.08, -1.5]}
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

/** 딸기 랙용 LED/관수 비율 헬퍼 */
export function actuatorRatios(actuators: ActuatorSummary[]) {
  return {
    led: ratioOf(actuators, 'led').ratio,
    irrigation: ratioOf(actuators, 'irrigation_pump').ratio,
  }
}
