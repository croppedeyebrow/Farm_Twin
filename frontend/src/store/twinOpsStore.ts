/**
 * 트윈 로컬 조작 상태 (문 개폐 등).
 *
 * 백엔드 액추에이터에 아직 없는 설비는 여기서 즉시 반영하고,
 * 이후 API 계약이 생기면 동기화한다.
 */

import { create } from 'zustand'

type TwinOpsStore = {
  /** 입구 이중문 열림 비율 0~1 */
  doorOpen: number
  setDoorOpen: (value: number) => void
  toggleDoor: () => void
}

export const useTwinOpsStore = create<TwinOpsStore>((set, get) => ({
  doorOpen: 0,
  setDoorOpen: (doorOpen) => set({ doorOpen: Math.min(1, Math.max(0, doorOpen)) }),
  toggleDoor: () => {
    const next = get().doorOpen > 0.5 ? 0 : 1
    set({ doorOpen: next })
  },
}))
