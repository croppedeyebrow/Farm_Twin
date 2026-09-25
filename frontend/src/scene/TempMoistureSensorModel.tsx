/**
 * 온·습도 센서 GLB (SHT3X 계열 패키지).
 *
 * 원본은 실칩 스케일(~2.5mm) → 관제 씬에서 보이도록 스케일업.
 * 에셋: public/models/temp-moisture-sensor.glb
 * 레퍼런스: docs/refs/temp&moisture_sensor.glb
 */

import { Clone, useGLTF } from '@react-three/drei'
import { useMemo } from 'react'
import type { Object3D } from 'three'

export const TEMP_MOISTURE_SENSOR_URL = '/models/temp-moisture-sensor.glb'

/** 월드에서 약 12~15cm 하우징처럼 보이게 */
export const TEMP_MOISTURE_SENSOR_SCALE = 55

type TempMoistureSensorModelProps = {
  scale?: number
}

export function TempMoistureSensorModel({
  scale = TEMP_MOISTURE_SENSOR_SCALE,
}: TempMoistureSensorModelProps) {
  const { scene } = useGLTF(TEMP_MOISTURE_SENSOR_URL)
  const source = useMemo(() => scene.clone(true), [scene])

  return (
    <group
      scale={scale}
      // 칩 XY 평면이 관측자를 향하고, 핀은 아래로
      rotation={[Math.PI / 2, 0, 0]}
    >
      <Clone object={source as Object3D} />
    </group>
  )
}

useGLTF.preload(TEMP_MOISTURE_SENSOR_URL)

/** 온·습도(및 유사 환경) 센서에 GLB 사용 */
export function usesTempMoistureModel(sensorType: string): boolean {
  return (
    sensorType === 'temperature' ||
    sensorType === 'humidity' ||
    sensorType === 'substrate_moisture'
  )
}
