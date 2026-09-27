/**
 * GLB 작물 에셋 로더.
 *
 * 딸기 세트: 원본 형태 유지 + Roots 숨김 + 열매 메시를 복제해
 * 한 가지(트러스)당 매달린 양이 풍성해 보이게 한 뒤 재질별로 병합해 캐시한다.
 */

import { Clone, useGLTF } from '@react-three/drei'
import { useLayoutEffect, useMemo, useRef } from 'react'
import { Group, Mesh as MeshObject } from 'three'
import type { BufferGeometry, Material, Mesh, Object3D } from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

export const STRAWBERRY_SET_URL = '/models/strawberry-set.glb'
export const GRAPE_MODEL_URL = '/models/grape.glb'

/** 세트 모듈 길이 (모델 로컬 X → 월드 거터 Z) — 조밀하게 타일 */
export const STRAWBERRY_SEGMENT_LENGTH = 1.18

type CropModelProps = {
  url: string
  position?: [number, number, number]
  rotation?: [number, number, number]
  scale?: number | [number, number, number]
  objectName?: string
}

/** 열매 메시 주변에 추가 알을 붙여 클러스터를  densify */
function densifyFruitClusters(root: Object3D) {
  const fruits: Mesh[] = []
  root.traverse((obj) => {
    const mesh = obj as Mesh
    if (mesh.isMesh && mesh.name.includes('Fruit')) {
      fruits.push(mesh)
    }
  })

  // 알당 오프셋 (모델 로컬: Y=폭, Z=처짐) — 가지에 매달린 송이처럼
  const clusterOffsets: Array<[number, number, number]> = [
    [0.012, 0.018, -0.022],
    [-0.01, -0.016, -0.028],
    [0.008, 0.028, -0.04],
    [-0.014, 0.01, -0.048],
    [0.004, -0.024, -0.055],
  ]

  for (const fruit of fruits) {
    const parent = fruit.parent
    if (!parent || !fruit.geometry) continue

    const isRipe = fruit.name.includes('Ripe')
    const isTurning = fruit.name.includes('Turning')
    // 익은/전환 열매 쪽에 더 많이, 풋열매는 적게
    const extras = isRipe ? 5 : isTurning ? 4 : 2

    for (let i = 0; i < extras; i += 1) {
      const [dx, dy, dz] = clusterOffsets[i % clusterOffsets.length]
      const jitter = ((i * 17) % 7) * 0.0015
      const clone = fruit.clone(true)
      clone.name = `${fruit.name}_extra_${i}`
      clone.geometry = (fruit.geometry as BufferGeometry).clone()
      const pos = clone.geometry.getAttribute('position')
      for (let v = 0; v < pos.count; v += 1) {
        pos.setXYZ(
          v,
          pos.getX(v) + dx + jitter,
          pos.getY(v) + dy - jitter * 0.5,
          pos.getZ(v) + dz - i * 0.004,
        )
      }
      pos.needsUpdate = true
      clone.geometry.computeVertexNormals()
      // 살짝 작게 — 송이 끝 알
      clone.scale.setScalar(0.82 - i * 0.04)
      parent.add(clone)
    }
  }
}

/**
 * 보이는 메시를 재질별로 병합한다 — 다단 랙에서 세그먼트가 100개 가까이
 * 반복되므로 세그먼트당 draw call 을 ~200 → 재질 수로 줄인다.
 */
function mergeByMaterial(root: Object3D): Group {
  root.updateMatrixWorld(true)
  const buckets = new Map<string, { material: Material; geometries: BufferGeometry[] }>()

  root.traverse((obj) => {
    const mesh = obj as Mesh
    if (!mesh.isMesh || !mesh.visible || Array.isArray(mesh.material)) return
    const geometry = (mesh.geometry as BufferGeometry).clone()
    geometry.applyMatrix4(mesh.matrixWorld)
    const material = mesh.material
    const bucket = buckets.get(material.uuid) ?? { material, geometries: [] }
    bucket.geometries.push(geometry.index ? geometry.toNonIndexed() : geometry)
    buckets.set(material.uuid, bucket)
  })

  const merged = new Group()
  for (const { material, geometries } of buckets.values()) {
    const common = Object.keys(geometries[0].attributes).filter((name) =>
      geometries.every((g) => g.getAttribute(name) !== undefined),
    )
    for (const g of geometries) {
      for (const name of Object.keys(g.attributes)) {
        if (!common.includes(name)) g.deleteAttribute(name)
      }
      g.morphAttributes = {}
    }
    const combined = mergeGeometries(geometries, false)
    if (combined) {
      merged.add(new MeshObject(combined, material))
    } else {
      for (const g of geometries) merged.add(new MeshObject(g, material))
    }
  }
  return merged
}

const preparedRows = new WeakMap<Object3D, Object3D>()

function prepareStrawberryRow(source: Object3D): Object3D {
  const cached = preparedRows.get(source)
  if (cached) return cached
  const root = source.clone(true)
  root.removeFromParent()
  root.traverse((obj) => {
    const mesh = obj as Mesh
    if (!mesh.isMesh) return
    if (mesh.name.includes('Roots')) {
      mesh.visible = false
    }
  })
  densifyFruitClusters(root)
  const merged = mergeByMaterial(root)
  preparedRows.set(source, merged)
  return merged
}

export function CropModel({
  url,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  scale = 1,
  objectName,
}: CropModelProps) {
  const { scene } = useGLTF(url)
  const source = useMemo(() => {
    if (!objectName) return scene
    return scene.getObjectByName(objectName) ?? scene
  }, [scene, objectName])

  return (
    <group position={position} rotation={rotation} scale={scale}>
      <Clone object={source as Object3D} />
    </group>
  )
}

/**
 * 딸기 라인 세그먼트.
 * 모델 (x,y,z) → 월드 (y,z,x) — 열=Z, 폭=X, 높이=Y
 */
export function StrawberryRowSegment({
  position = [0, 0, 0],
  yaw = 0,
  scale = 1,
}: {
  position?: [number, number, number]
  yaw?: number
  scale?: number
}) {
  const { scene } = useGLTF(STRAWBERRY_SET_URL)
  const prepared = useMemo(() => {
    const row = scene.getObjectByName('SmartFarm_Strawberry_Row') ?? scene
    return prepareStrawberryRow(row)
  }, [scene])
  const orientRef = useRef<Group>(null)

  useLayoutEffect(() => {
    const g = orientRef.current
    if (!g) return
    g.matrix.set(
      0, 1, 0, 0,
      0, 0, 1, 0,
      1, 0, 0, 0,
      0, 0, 0, 1,
    )
    g.matrixAutoUpdate = false
  }, [])

  return (
    <group position={position} rotation={[0, yaw, 0]} scale={scale}>
      <group ref={orientRef}>
        <Clone object={prepared} />
      </group>
    </group>
  )
}

export function GrapePlantModel({
  scale = 1.35,
  ...props
}: Omit<CropModelProps, 'url' | 'objectName'>) {
  return <CropModel url={GRAPE_MODEL_URL} scale={scale} {...props} />
}

useGLTF.preload(STRAWBERRY_SET_URL)
useGLTF.preload(GRAPE_MODEL_URL)
