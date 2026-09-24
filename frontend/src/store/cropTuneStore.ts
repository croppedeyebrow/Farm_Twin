/**
 * 작물(딸기/포도) 크기·위치 튜닝 스토어.
 * localStorage 에 저장해 새로고침 후에도 유지한다.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type CropTransform = {
  /** 균일 스케일 */
  scale: number
  offsetX: number
  offsetY: number
  offsetZ: number
}

export const DEFAULT_STRAWBERRY: CropTransform = {
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  offsetZ: 0,
}

export const DEFAULT_GRAPE: CropTransform = {
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  offsetZ: 0,
}

type CropTuneStore = {
  strawberry: CropTransform
  grape: CropTransform
  panelOpen: boolean
  setStrawberry: (patch: Partial<CropTransform>) => void
  setGrape: (patch: Partial<CropTransform>) => void
  resetStrawberry: () => void
  resetGrape: () => void
  resetAll: () => void
  setPanelOpen: (open: boolean) => void
}

export const useCropTuneStore = create<CropTuneStore>()(
  persist(
    (set) => ({
      strawberry: { ...DEFAULT_STRAWBERRY },
      grape: { ...DEFAULT_GRAPE },
      panelOpen: true,
      setStrawberry: (patch) =>
        set((s) => ({ strawberry: { ...s.strawberry, ...patch } })),
      setGrape: (patch) => set((s) => ({ grape: { ...s.grape, ...patch } })),
      resetStrawberry: () => set({ strawberry: { ...DEFAULT_STRAWBERRY } }),
      resetGrape: () => set({ grape: { ...DEFAULT_GRAPE } }),
      resetAll: () =>
        set({
          strawberry: { ...DEFAULT_STRAWBERRY },
          grape: { ...DEFAULT_GRAPE },
        }),
      setPanelOpen: (open) => set({ panelOpen: open }),
    }),
    { name: 'farmtwin-crop-tune-v1' },
  ),
)
