/**
 * 장치별 수동 ON/OFF·출력 비율.
 * 3D 트윈 사이드바·설비 제어 페이지에서 공유한다.
 */

import { useEffect, useMemo, useState } from 'react'

import {
  setActuatorManual,
  type ActuatorSummary,
  type FarmStateSnapshot,
} from '../api/farms'

export const MANUAL_ACTUATOR_ORDER = [
  'led',
  'hvac',
  'heater',
  'dehumidifier',
  'humidifier',
  'irrigation_pump',
  'zone_valve_strawberry',
  'zone_valve_grape',
  'ventilation_fan',
  'vent_motor',
  'circulation_fan',
] as const

const LABELS: Record<string, { title: string; metric: string }> = {
  led: { title: '생장 LED', metric: '조도' },
  hvac: { title: '냉방 (HVAC)', metric: '냉방 출력' },
  heater: { title: '난방', metric: '난방 출력' },
  dehumidifier: { title: '제습기', metric: '제습 출력' },
  humidifier: { title: '가습기', metric: '가습 출력' },
  irrigation_pump: { title: '관수 펌프', metric: '펌프 출력' },
  zone_valve_strawberry: { title: '딸기 관수 밸브', metric: '개도' },
  zone_valve_grape: { title: '포도 관수 밸브', metric: '개도' },
  ventilation_fan: { title: '환기팬', metric: '팬 출력' },
  vent_motor: { title: '천창·측창', metric: '개도' },
  circulation_fan: { title: '순환팬', metric: '팬 출력' },
}

type Props = {
  actuators: ActuatorSummary[]
  state: FarmStateSnapshot | null
  selectedActuatorId: string | null
  onSelectActuator: (id: string | null) => void
  /** 선택 장치만 크게, 나머지는 접힌 목록 */
  compactList?: boolean
  disabled?: boolean
  className?: string
}

function effectHint(
  type: string,
  state: FarmStateSnapshot | null,
): string | null {
  if (!state) return null
  switch (type) {
    case 'led':
      return `PPFD ${state.ppfd_umol.toFixed(0)} µmol`
    case 'hvac':
    case 'heater':
      return `실내 ${state.temperature_c.toFixed(1)} ℃`
    case 'dehumidifier':
    case 'humidifier':
      return `실내 ${state.humidity_pct.toFixed(1)} %`
    case 'irrigation_pump':
    case 'zone_valve_strawberry':
    case 'zone_valve_grape':
      return `배지 ${state.substrate_moisture_pct.toFixed(1)} %`
    case 'ventilation_fan':
    case 'vent_motor':
      return `CO₂ ${state.co2_ppm.toFixed(0)} ppm`
    default:
      return null
  }
}

function DeviceRow({
  actuator,
  state,
  selected,
  onSelect,
  disabled,
  emphasized,
}: {
  actuator: ActuatorSummary
  state: FarmStateSnapshot | null
  selected: boolean
  onSelect: () => void
  disabled?: boolean
  emphasized?: boolean
}) {
  const label = LABELS[actuator.actuator_type] ?? {
    title: actuator.name,
    metric: '출력',
  }
  const appliedPct = Math.round(actuator.output_ratio * 100)
  const [draftPct, setDraftPct] = useState(appliedPct)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraftPct(Math.round(actuator.output_ratio * 100))
  }, [actuator.id, actuator.output_ratio])

  const dirty = draftPct !== appliedPct
  const on = appliedPct > 0
  const hint = effectHint(actuator.actuator_type, state)

  async function applyRatio(ratio: number) {
    setPending(true)
    setError(null)
    try {
      await setActuatorManual(actuator.id, ratio)
      setDraftPct(Math.round(ratio * 100))
      onSelect()
    } catch (err) {
      setError(err instanceof Error ? err.message : '적용 실패')
    } finally {
      setPending(false)
    }
  }

  return (
    <article
      className={
        emphasized ? 'actuator-manual-card is-focus' : 'actuator-manual-card'
      }
      data-selected={selected ? 'true' : 'false'}
      data-on={on ? 'true' : 'false'}
    >
      <button
        type="button"
        className="actuator-manual-select"
        onClick={onSelect}
      >
        <strong>{label.title}</strong>
        <em data-on={on ? 'true' : 'false'}>
          {on ? `ON · ${appliedPct}%` : 'OFF'}
          <span className="actuator-mode">{actuator.mode}</span>
        </em>
      </button>

      <label className="control-slider-row">
        <span>
          {label.metric}
          <em>{draftPct}%</em>
        </span>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={draftPct}
          disabled={pending || disabled}
          onChange={(event) => setDraftPct(Number(event.target.value))}
          onPointerDown={onSelect}
        />
      </label>

      {hint ? (
        <p className="control-hint">시뮬 반영 · {hint}</p>
      ) : (
        <p className="control-hint">수동 출력은 다음 시뮬 step에 반영됩니다.</p>
      )}

      <div className="control-actions">
        <button
          type="button"
          className="control-apply"
          disabled={pending || disabled || !dirty}
          onClick={() => void applyRatio(draftPct / 100)}
        >
          {pending ? '적용 중…' : '적용'}
        </button>
        <button
          type="button"
          className="control-on"
          disabled={pending || disabled || appliedPct === 100}
          onClick={() => void applyRatio(1)}
        >
          ON
        </button>
        <button
          type="button"
          className="control-off"
          disabled={pending || disabled || appliedPct === 0}
          onClick={() => void applyRatio(0)}
        >
          OFF
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
    </article>
  )
}

export function ActuatorManualPanel({
  actuators,
  state,
  selectedActuatorId,
  onSelectActuator,
  compactList = false,
  disabled = false,
  className,
}: Props) {
  const ordered = useMemo(() => {
    const byType = new Map(actuators.map((item) => [item.actuator_type, item]))
    const primary = MANUAL_ACTUATOR_ORDER.map((type) => byType.get(type)).filter(
      (item): item is ActuatorSummary => item != null,
    )
    const rest = actuators.filter(
      (item) =>
        !(MANUAL_ACTUATOR_ORDER as readonly string[]).includes(
          item.actuator_type,
        ),
    )
    return [...primary, ...rest]
  }, [actuators])

  const focus =
    ordered.find((item) => item.id === selectedActuatorId) ?? ordered[0] ?? null

  if (ordered.length === 0) {
    return (
      <section className={className ?? 'actuator-manual-panel'} aria-label="수동 설비 제어">
        <p className="panel-empty">제어 가능한 액추에이터가 없습니다.</p>
      </section>
    )
  }

  if (compactList && focus) {
    return (
      <section
        className={className ?? 'actuator-manual-panel'}
        aria-label="수동 설비 제어"
      >
        <DeviceRow
          key={focus.id}
          actuator={focus}
          state={state}
          selected
          emphasized
          disabled={disabled}
          onSelect={() => onSelectActuator(focus.id)}
        />
        <ul className="actuator-manual-rail" aria-label="장치 목록">
          {ordered.map((item) => {
            const on = item.output_ratio > 0 && item.mode !== 'off'
            const label =
              LABELS[item.actuator_type]?.title ?? item.name
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={
                    item.id === focus.id
                      ? 'actuator-rail-btn is-active'
                      : 'actuator-rail-btn'
                  }
                  data-on={on ? 'true' : 'false'}
                  onClick={() => onSelectActuator(item.id)}
                >
                  <span>{label}</span>
                  <em>{on ? `${Math.round(item.output_ratio * 100)}%` : 'OFF'}</em>
                </button>
              </li>
            )
          })}
        </ul>
      </section>
    )
  }

  return (
    <section
      className={className ?? 'actuator-manual-panel'}
      aria-label="수동 설비 제어"
    >
      <div className="actuator-manual-grid">
        {ordered.map((item) => (
          <DeviceRow
            key={item.id}
            actuator={item}
            state={state}
            selected={item.id === selectedActuatorId}
            disabled={disabled}
            onSelect={() => onSelectActuator(item.id)}
          />
        ))}
      </div>
    </section>
  )
}
