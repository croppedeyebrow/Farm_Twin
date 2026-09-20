/**
 * GLB 작물 에셋 로더 (딸기 / 포도).
 *
 * 파일: public/models/strawberry.glb , grape.glb
 * 원본 바운드 ≈ 0.17×0.25×0.15 — 거터·덩굴 스케일에 맞게 scale 로 조정.
 *
 * Clone 으로 동일 GPU 버퍼를 재사용해 열 단위 반복 배치한다.
 */

import { Clone, useGLTF } from '@react-three/drei'
import { useMemo } from 'react'

export const STRAWBERRY_MODEL_URL = '/models/strawberry.glb'
export const GRAPE_MODEL_URL = '/models/grape.glb'

type CropModelProps = {
  url: string
  position?: [number, number, number]
  rotation?: [number, number, number]
  scale?: number | [number, number, number]
  /** Y 기준 정렬: 모델 min.y=0 이므로 보통 불필요 */
  castShadow?: boolean
}

export function CropModel({
  url,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  scale = 1,
}: CropModelProps) {
  const { scene } = useGLTF(url)
  // Clone 내부에서도 복제하지만, key 안정성을 위해 scene 참조만 전달
  const source = useMemo(() => scene, [scene])

  return (
    <group position={position} rotation={rotation} scale={scale}>
      <Clone object={source} />
    </group>
  )
}

export function StrawberryPlantModel({
  scale = 1.15,
  ...props
}: Omit<CropModelProps, 'url'>) {
  return <CropModel url={STRAWBERRY_MODEL_URL} scale={scale} {...props} />
}

export function GrapePlantModel({
  scale = 1.35,
  ...props
}: Omit<CropModelProps, 'url'>) {
  return <CropModel url={GRAPE_MODEL_URL} scale={scale} {...props} />
}

useGLTF.preload(STRAWBERRY_MODEL_URL)
useGLTF.preload(GRAPE_MODEL_URL)
