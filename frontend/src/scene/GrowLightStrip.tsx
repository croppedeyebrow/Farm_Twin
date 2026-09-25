/**
 * 멀티스펙트럼 생장 LED 바 (레퍼런스: 흰/청/마젠타 다이오드).
 *
 * ledRatio 0 → OFF, >0 → ON. 발광·워시라이트를 useFrame 으로 보간.
 */

import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import type { Group, Mesh, MeshStandardMaterial } from 'three'

type GrowLightStripProps = {
  length: number
  ledRatio: number
  width?: number
}

const DIODE_COLORS = ['#f8f9fa', '#4dabf7', '#e64980', '#f8f9fa', '#4dabf7'] as const

export function GrowLightStrip({
  length,
  ledRatio,
  width = 0.26,
}: GrowLightStripProps) {
  const glowRef = useRef(0)
  const diodeGroupRef = useRef<Group>(null)
  const washRef = useRef<Mesh>(null)
  const statusRef = useRef<Mesh>(null)

  const diodes = useMemo(() => {
    const items: Array<{ z: number; color: string; lane: number }> = []
    const pitch = 0.11
    const half = (length * 0.82) / 2
    let i = 0
    for (let z = -half; z <= half + 1e-6; z += pitch) {
      for (let lane = 0; lane < 3; lane += 1) {
        items.push({
          z,
          lane,
          color: DIODE_COLORS[(i + lane) % DIODE_COLORS.length],
        })
      }
      i += 1
    }
    return items
  }, [length])

  useFrame((_, delta) => {
    glowRef.current += (ledRatio - glowRef.current) * Math.min(1, delta * 5)
    const g = glowRef.current
    const on = g > 0.02

    if (diodeGroupRef.current) {
      diodeGroupRef.current.traverse((obj) => {
        const mesh = obj as Mesh
        if (!mesh.isMesh) return
        const mat = mesh.material as MeshStandardMaterial
        if (!mat?.emissive) return
        mat.emissiveIntensity = on ? 0.08 + g * 2.1 : 0
      })
    }

    if (washRef.current) {
      const mat = washRef.current.material as MeshStandardMaterial
      mat.opacity = on ? 0.08 + g * 0.28 : 0
      washRef.current.visible = on
    }

    if (statusRef.current) {
      const mat = statusRef.current.material as MeshStandardMaterial
      const color = on ? '#51cf66' : '#fa5252'
      mat.color.set(color)
      mat.emissive.set(color)
      mat.emissiveIntensity = 0.55
    }
  })

  return (
    <group>
      <mesh>
        <boxGeometry args={[width, 0.07, length * 0.9]} />
        <meshStandardMaterial color="#ced4da" roughness={0.5} metalness={0.15} />
      </mesh>
      <mesh position={[0, -0.04, 0]}>
        <boxGeometry args={[width * 0.92, 0.02, length * 0.86]} />
        <meshStandardMaterial color="#212529" roughness={0.65} />
      </mesh>

      <group ref={diodeGroupRef}>
        {diodes.map((d, idx) => {
          const x = (d.lane - 1) * 0.055
          return (
            <mesh key={`d-${idx}`} position={[x, -0.055, d.z]}>
              <boxGeometry args={[0.04, 0.012, 0.07]} />
              <meshStandardMaterial
                color={d.color}
                emissive={d.color}
                emissiveIntensity={0}
                roughness={0.3}
              />
            </mesh>
          )
        })}
      </group>

      <mesh ref={statusRef} position={[0, 0.045, length * 0.4]}>
        <boxGeometry args={[0.06, 0.025, 0.06]} />
        <meshStandardMaterial
          color="#fa5252"
          emissive="#fa5252"
          emissiveIntensity={0.55}
        />
      </mesh>

      <mesh
        ref={washRef}
        position={[0, -0.55, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        visible={false}
      >
        <planeGeometry args={[width * 2.2, length * 0.75]} />
        <meshBasicMaterial
          color="#ff9ecd"
          transparent
          opacity={0}
          depthWrite={false}
        />
      </mesh>

      {[-length * 0.32, length * 0.32].map((z) => (
        <mesh key={`br-${z}`} position={[0, 0.09, z]}>
          <boxGeometry args={[0.05, 0.12, 0.05]} />
          <meshStandardMaterial color="#adb5bd" metalness={0.35} />
        </mesh>
      ))}
    </group>
  )
}
