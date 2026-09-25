/**
 * 운영 제어 패널 — LED 조도 + 입구 문 개폐.
 */

import { useEffect, useMemo, useState } from 'react'

import {
  setActuatorManual,
  type ActuatorSummary,
  type FarmStateSnapshot,
} from '../api/farms'
import { useTwinOpsStore } from '../store/twinOpsStore'

type Props = {
  actuators: ActuatorSummary[]
  state: FarmStateSnapshot | null
  selectedActuatorId: string | null
  onSelectActuator: (id: string | null) => void
}

export function ControlPanel({
  actuators,
  state,
  selectedActuatorId,
  onSelectActuator,
}: Props) {
  const led = useMemo(
    () => actuators.find((item) => item.actuator_type === 'led') ?? null,
    [actuators],
  )

  const doorOpen = useTwinOpsStore((s) => s.doorOpen)
  const setDoorOpen = useTwinOpsStore((s) => s.setDoorOpen)
  const toggleDoor = useTwinOpsStore((s) => s.toggleDoor)

  const [draftPct, setDraftPct] = useState(0)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (led) {
      setDraftPct(Math.round(led.output_ratio * 100))
    }
  }, [led?.id, led?.output_ratio])

  const appliedPct = led ? Math.round(led.output_ratio * 100) : 0
  const dirty = led != null && draftPct !== appliedPct
  const ledOn = appliedPct > 0

  async function applyRatio(ratio: number) {
    if (!led) return
    setPending(true)
    setError(null)
    try {
      await setActuatorManual(led.id, ratio)
      setDraftPct(Math.round(ratio * 100))
      onSelectActuator(led.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : '적용 실패')
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="control-panel" aria-label="환경 제어">
      <div className="panel-title-row">
        <h2>제어</h2>
        {led ? (
          <span className="control-mode-badge" data-mode={led.mode}>
            {led.mode}
          </span>
        ) : null}
      </div>

      {!led ? (
        <p className="panel-empty">LED 액추에이터가 없습니다.</p>
      ) : (
        <div className="control-led">
          <div className="control-led-head">
            <strong>{led.name}</strong>
            <em data-on={ledOn ? 'true' : 'false'}>
              {ledOn ? `ON · ${appliedPct}%` : 'OFF'}
            </em>
          </div>

          <label className="control-slider-row">
            <span>
              조도 (LED)
              <em>{draftPct}%</em>
            </span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={draftPct}
              disabled={pending}
              onChange={(event) => setDraftPct(Number(event.target.value))}
              onPointerUp={() => {
                if (selectedActuatorId !== led.id) onSelectActuator(led.id)
              }}
            />
          </label>

          <dl className="detail-dl">
            <div>
              <dt>적용 출력</dt>
              <dd>{appliedPct}%</dd>
            </div>
            <div>
              <dt>PPFD (측정)</dt>
              <dd>
                {state ? `${state.ppfd_umol.toFixed(0)} µmol` : '—'}
              </dd>
            </div>
          </dl>

          <p className="control-hint">
            ON/OFF·조도는 즉시 3D에 반영됩니다. PPFD는 시뮬 step 시 LED를
            추적합니다.
          </p>

          <div className="control-actions">
            <button
              type="button"
              className="control-apply"
              disabled={pending || !dirty}
              onClick={() => void applyRatio(draftPct / 100)}
            >
              {pending ? '적용 중…' : '적용'}
            </button>
            <button
              type="button"
              className="control-on"
              disabled={pending || appliedPct === 100}
              onClick={() => void applyRatio(1)}
            >
              ON
            </button>
            <button
              type="button"
              className="control-off"
              disabled={pending || appliedPct === 0}
              onClick={() => void applyRatio(0)}
            >
              OFF
            </button>
          </div>
        </div>
      )}

      <div className="control-door">
        <div className="control-led-head">
          <strong>입구 문</strong>
          <em data-on={doorOpen > 0.5 ? 'true' : 'false'}>
            {doorOpen > 0.5 ? '열림' : '닫힘'}
          </em>
        </div>
        <label className="control-slider-row">
          <span>
            개도
            <em>{Math.round(doorOpen * 100)}%</em>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(doorOpen * 100)}
            onChange={(event) => setDoorOpen(Number(event.target.value) / 100)}
          />
        </label>
        <div className="control-actions">
          <button
            type="button"
            className="control-on"
            disabled={doorOpen >= 0.99}
            onClick={() => setDoorOpen(1)}
          >
            열기
          </button>
          <button
            type="button"
            className="control-off"
            disabled={doorOpen <= 0.01}
            onClick={() => setDoorOpen(0)}
          >
            닫기
          </button>
          <button type="button" className="control-apply" onClick={toggleDoor}>
            토글
          </button>
        </div>
        <p className="control-hint">문 개폐는 트윈 로컬 상태입니다 (추후 API 연동).</p>
      </div>

      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
