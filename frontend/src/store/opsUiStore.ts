/**
 * OPERATIONS UI 상태 — 시나리오 · 일시정지 · 추이 · 운전 기준 · 모드
 */

import { create } from 'zustand'

import {
  DEFAULT_CONTROL_RULES,
  OPS_SCENARIOS,
  type OpsScenarioId,
} from '../components/ops/opsRules'

export type ChartWindow = '1h' | '6h' | '24h'
export type DriveMode = 'auto' | 'manual'
export type SensorFilter = 'all' | 'temp' | 'humidity' | 'soil' | 'outdoor'

export type ControlRules = {
  coolStartC: number
  humidStartPct: number
  irrigateStartPct: number
}

type OpsUiState = {
  scenarioId: OpsScenarioId
  paused: boolean
  chartWindow: ChartWindow
  scenarioMenuOpen: boolean
  driveMode: DriveMode
  modeMenuOpen: boolean
  draftRules: ControlRules
  appliedRules: ControlRules
  sensorFilter: SensorFilter
  recordsWindow: ChartWindow
  setScenarioId: (id: OpsScenarioId) => void
  setPaused: (paused: boolean) => void
  togglePaused: () => void
  setChartWindow: (w: ChartWindow) => void
  setScenarioMenuOpen: (open: boolean) => void
  setDriveMode: (mode: DriveMode) => void
  setModeMenuOpen: (open: boolean) => void
  setDraftRule: (key: keyof ControlRules, value: number) => void
  applyRules: () => void
  setSensorFilter: (f: SensorFilter) => void
  setRecordsWindow: (w: ChartWindow) => void
}

export const useOpsUiStore = create<OpsUiState>((set) => ({
  scenarioId: 'normal',
  paused: false,
  chartWindow: '1h',
  scenarioMenuOpen: false,
  driveMode: 'manual',
  modeMenuOpen: false,
  draftRules: { ...DEFAULT_CONTROL_RULES },
  appliedRules: { ...DEFAULT_CONTROL_RULES },
  sensorFilter: 'all',
  recordsWindow: '1h',
  setScenarioId: (scenarioId) => set({ scenarioId, scenarioMenuOpen: false }),
  setPaused: (paused) => set({ paused }),
  togglePaused: () => set((s) => ({ paused: !s.paused })),
  setChartWindow: (chartWindow) => set({ chartWindow }),
  setScenarioMenuOpen: (scenarioMenuOpen) => set({ scenarioMenuOpen }),
  setDriveMode: (driveMode) => set({ driveMode, modeMenuOpen: false }),
  setModeMenuOpen: (modeMenuOpen) => set({ modeMenuOpen }),
  setDraftRule: (key, value) =>
    set((s) => ({ draftRules: { ...s.draftRules, [key]: value } })),
  applyRules: () => set((s) => ({ appliedRules: { ...s.draftRules } })),
  setSensorFilter: (sensorFilter) => set({ sensorFilter }),
  setRecordsWindow: (recordsWindow) => set({ recordsWindow }),
}))

export function currentScenario(scenarioId: OpsScenarioId) {
  return OPS_SCENARIOS.find((s) => s.id === scenarioId) ?? OPS_SCENARIOS[0]
}
