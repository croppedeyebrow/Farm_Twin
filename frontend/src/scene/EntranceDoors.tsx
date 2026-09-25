/**
 * 온실 입구 이중문 — 좌우 슬라이드 개폐.
 *
 * doorOpen 0=닫힘, 1=열림.
 * 개구에 검은 가림판 없음 → 열리면 내부가 그대로 보인다.
 */

import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import type { Group } from 'three'

import { useTwinOpsStore } from '../store/twinOpsStore'
import { HALL_Z1 } from './GreenhouseShell'

const DOOR_W = 1.1
const DOOR_H = 2.15
const SLIDE_MAX = DOOR_W * 0.92

export function EntranceDoors() {
  const target = useTwinOpsStore((s) => s.doorOpen)
  const slideRef = useRef(0)
  const leftRef = useRef<Group>(null)
  const rightRef = useRef<Group>(null)

  useFrame((_, delta) => {
    slideRef.current +=
      (target * SLIDE_MAX - slideRef.current) * Math.min(1, delta * 3.2)
    const s = slideRef.current
    if (leftRef.current) leftRef.current.position.x = -s
    if (rightRef.current) rightRef.current.position.x = s
  })

  const open = target > 0.5

  return (
    <group position={[0, 0, HALL_Z1 + 0.1]}>
      {/* 문틀 */}
      <mesh position={[0, DOOR_H + 0.06, -0.02]}>
        <boxGeometry args={[DOOR_W * 2 + 0.2, 0.14, 0.1]} />
        <meshStandardMaterial color="#868e96" roughness={0.5} metalness={0.25} />
      </mesh>
      <mesh position={[-(DOOR_W + 0.06), DOOR_H / 2, -0.02]}>
        <boxGeometry args={[0.1, DOOR_H + 0.14, 0.1]} />
        <meshStandardMaterial color="#868e96" roughness={0.5} metalness={0.25} />
      </mesh>
      <mesh position={[DOOR_W + 0.06, DOOR_H / 2, -0.02]}>
        <boxGeometry args={[0.1, DOOR_H + 0.14, 0.1]} />
        <meshStandardMaterial color="#868e96" roughness={0.5} metalness={0.25} />
      </mesh>

      {/* 상단 레일 */}
      <mesh position={[0, DOOR_H + 0.02, 0.04]}>
        <boxGeometry args={[DOOR_W * 2 + 0.15, 0.04, 0.06]} />
        <meshStandardMaterial color="#495057" metalness={0.45} roughness={0.4} />
      </mesh>

      {/* 왼쪽 슬라이드 문 */}
      <group ref={leftRef} position={[0, DOOR_H / 2, 0.02]}>
        <mesh position={[-DOOR_W / 2, 0, 0]}>
          <boxGeometry args={[DOOR_W, DOOR_H, 0.05]} />
          <meshStandardMaterial color="#adb5bd" roughness={0.55} metalness={0.15} />
        </mesh>
        <mesh position={[-DOOR_W / 2, 0, 0.03]}>
          <boxGeometry args={[DOOR_W - 0.12, DOOR_H - 0.16, 0.02]} />
          <meshStandardMaterial
            color="#c5d9ea"
            transparent
            opacity={0.45}
            roughness={0.35}
          />
        </mesh>
        <mesh position={[-0.14, 0, 0.04]}>
          <boxGeometry args={[0.04, 0.22, 0.03]} />
          <meshStandardMaterial color="#495057" metalness={0.4} />
        </mesh>
      </group>

      {/* 오른쪽 슬라이드 문 */}
      <group ref={rightRef} position={[0, DOOR_H / 2, 0.02]}>
        <mesh position={[DOOR_W / 2, 0, 0]}>
          <boxGeometry args={[DOOR_W, DOOR_H, 0.05]} />
          <meshStandardMaterial color="#adb5bd" roughness={0.55} metalness={0.15} />
        </mesh>
        <mesh position={[DOOR_W / 2, 0, 0.03]}>
          <boxGeometry args={[DOOR_W - 0.12, DOOR_H - 0.16, 0.02]} />
          <meshStandardMaterial
            color="#c5d9ea"
            transparent
            opacity={0.45}
            roughness={0.35}
          />
        </mesh>
        <mesh position={[0.14, 0, 0.04]}>
          <boxGeometry args={[0.04, 0.22, 0.03]} />
          <meshStandardMaterial color="#495057" metalness={0.4} />
        </mesh>
      </group>

      {/* 개폐 상태등 */}
      <mesh position={[0, DOOR_H + 0.16, 0.05]}>
        <boxGeometry args={[0.22, 0.07, 0.045]} />
        <meshStandardMaterial
          color={open ? '#51cf66' : '#868e96'}
          emissive={open ? '#51cf66' : '#000000'}
          emissiveIntensity={open ? 0.6 : 0}
        />
      </mesh>
    </group>
  )
}
