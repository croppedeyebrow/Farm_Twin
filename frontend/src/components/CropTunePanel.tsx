/**
 * 작물 크기·위치 튜닝 패널 (3D 뷰포트 위).
 * 딸기/포도 GLB 스케일·오프셋을 슬라이더로 조정한다.
 */

import { useCropTuneStore, type CropTransform } from '../store/cropTuneStore'

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
}) {
  return (
    <label className="crop-tune-row">
      <span>
        {label}
        <em>{value.toFixed(2)}</em>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

function CropSection({
  title,
  values,
  onChange,
  onReset,
}: {
  title: string
  values: CropTransform
  onChange: (patch: Partial<CropTransform>) => void
  onReset: () => void
}) {
  return (
    <div className="crop-tune-section">
      <div className="crop-tune-section-head">
        <strong>{title}</strong>
        <button type="button" className="crop-tune-btn" onClick={onReset}>
          리셋
        </button>
      </div>
      <SliderRow
        label="크기"
        value={values.scale}
        min={0.3}
        max={3}
        step={0.05}
        onChange={(scale) => onChange({ scale })}
      />
      <SliderRow
        label="위치 X"
        value={values.offsetX}
        min={-1.5}
        max={1.5}
        step={0.02}
        onChange={(offsetX) => onChange({ offsetX })}
      />
      <SliderRow
        label="위치 Y (높이)"
        value={values.offsetY}
        min={-1.5}
        max={1.5}
        step={0.02}
        onChange={(offsetY) => onChange({ offsetY })}
      />
      <SliderRow
        label="위치 Z"
        value={values.offsetZ}
        min={-2}
        max={2}
        step={0.02}
        onChange={(offsetZ) => onChange({ offsetZ })}
      />
    </div>
  )
}

export function CropTunePanel() {
  const panelOpen = useCropTuneStore((s) => s.panelOpen)
  const setPanelOpen = useCropTuneStore((s) => s.setPanelOpen)
  const strawberry = useCropTuneStore((s) => s.strawberry)
  const grape = useCropTuneStore((s) => s.grape)
  const setStrawberry = useCropTuneStore((s) => s.setStrawberry)
  const setGrape = useCropTuneStore((s) => s.setGrape)
  const resetStrawberry = useCropTuneStore((s) => s.resetStrawberry)
  const resetGrape = useCropTuneStore((s) => s.resetGrape)
  const resetAll = useCropTuneStore((s) => s.resetAll)

  if (!panelOpen) {
    return (
      <button
        type="button"
        className="crop-tune-fab"
        onClick={() => setPanelOpen(true)}
        aria-label="작물 튜닝 열기"
      >
        작물 튜닝
      </button>
    )
  }

  return (
    <aside className="crop-tune-panel" aria-label="작물 크기·위치 튜닝">
      <div className="crop-tune-head">
        <strong>작물 튜닝</strong>
        <div className="crop-tune-head-actions">
          <button
            type="button"
            className="crop-tune-btn"
            onClick={() => resetAll()}
          >
            전부 리셋
          </button>
          <button
            type="button"
            className="crop-tune-btn"
            onClick={() => {
              const payload = JSON.stringify({ strawberry, grape }, null, 2)
              void navigator.clipboard?.writeText(payload)
            }}
          >
            값 복사
          </button>
          <button
            type="button"
            className="crop-tune-btn"
            onClick={() => setPanelOpen(false)}
          >
            닫기
          </button>
        </div>
      </div>

      <CropSection
        title="딸기 (세트)"
        values={strawberry}
        onChange={setStrawberry}
        onReset={resetStrawberry}
      />
      <CropSection
        title="포도"
        values={grape}
        onChange={setGrape}
        onReset={resetGrape}
      />
    </aside>
  )
}
