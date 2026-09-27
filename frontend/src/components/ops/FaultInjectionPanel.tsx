/**
 * 센서 고장 주입 패널 (6단계 Day 22).
 *
 * spike / stuck / dropout 을 시뮬 측정에 주입하고 해제한다.
 * 고장은 측정에만 적용된다 — 참값은 그대로이고, 품질 판정이 이를 잡아
 * 규칙 엔진이 suspect 는 보류, bad/missing/stale 은 차단한다.
 */

import { useMemo, useState } from 'react'

import {
  clearFault,
  injectFault,
  type FaultType,
  type SensorFault,
} from '../../api/faults'
import { reloadSensorPanels } from '../../realtime/session'
import { useRealtimeStore } from '../../store/realtimeStore'

const SIMULATED_TYPES = [
  'temperature',
  'humidity',
  'co2',
  'substrate_moisture',
  'ppfd',
] as const

const FAULT_OPTS: { id: FaultType; label: string; hint: string }[] = [
  { id: 'spike', label: '스파이크', hint: '간헐적으로 값이 튐 → 의심(보류)' },
  { id: 'stuck', label: '고정(stuck)', hint: '값이 멈춤 → 4회 연속 시 불량(차단)' },
  { id: 'dropout', label: '끊김(dropout)', hint: '송신 중단 → 지연 → 복구 시 누락' },
]

const FAULT_LABEL: Record<FaultType, string> = {
  spike: '스파이크',
  stuck: '고정',
  dropout: '끊김',
}

function faultDetail(fault: SensorFault): string {
  if (fault.fault_type === 'spike' && fault.magnitude != null) {
    return `+${fault.magnitude}`
  }
  if (fault.fault_type === 'stuck' && fault.stuck_value != null) {
    return `= ${fault.stuck_value.toFixed(2)}`
  }
  return ''
}

function simSpan(fault: SensorFault): string {
  const start = `${fault.start_simulation_time.toFixed(0)}s`
  if (fault.end_simulation_time == null) return `${start} ~ 진행 중`
  return `${start} ~ ${fault.end_simulation_time.toFixed(0)}s`
}

export function FaultInjectionPanel() {
  const health = useRealtimeStore((s) => s.sensorHealth)
  const faultList = useRealtimeStore((s) => s.faults)
  const runId = health?.run_id ?? null

  const sensors = useMemo(
    () =>
      (health?.sensors ?? []).filter((item) =>
        (SIMULATED_TYPES as readonly string[]).includes(item.sensor_type),
      ),
    [health],
  )
  const faults = faultList?.faults ?? []
  const active = faults.filter((f) => f.active)
  const activeSensorIds = new Set(active.map((f) => f.sensor_id))

  const [sensorId, setSensorId] = useState('')
  const [faultType, setFaultType] = useState<FaultType>('spike')
  const [amount, setAmount] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedId =
    sensorId && sensors.some((s) => s.sensor_id === sensorId)
      ? sensorId
      : (sensors.find((s) => !activeSensorIds.has(s.sensor_id))?.sensor_id ?? '')
  const amountLabel =
    faultType === 'spike' ? '튐 크기' : faultType === 'stuck' ? '고정값' : null

  async function run(action: () => Promise<unknown>) {
    setPending(true)
    setError(null)
    try {
      await action()
      await reloadSensorPanels()
    } catch (err) {
      setError(err instanceof Error ? err.message : '요청 실패')
    } finally {
      setPending(false)
    }
  }

  function submit() {
    if (!runId || !selectedId) return
    const parsed = amount.trim() === '' ? undefined : Number(amount)
    if (parsed !== undefined && !Number.isFinite(parsed)) {
      setError('숫자를 입력하세요')
      return
    }
    void run(() =>
      injectFault(runId, {
        sensor_id: selectedId,
        fault_type: faultType,
        ...(faultType === 'spike' && parsed !== undefined ? { magnitude: parsed } : {}),
        ...(faultType === 'stuck' && parsed !== undefined ? { stuck_value: parsed } : {}),
      }),
    )
  }

  return (
    <section className="ops-panel ops-table-panel" aria-label="센서 고장 주입">
      <header className="ops-panel-head">
        <h2>센서 고장 주입</h2>
        <span className="ops-sort-tag">
          진행 중 {active.length}건 · 이력 {faults.length}건
        </span>
      </header>

      {!runId ? (
        <p className="ops-empty">시뮬레이션 run 이 없어 고장을 주입할 수 없습니다.</p>
      ) : (
        <div className="fault-form">
          <label>
            센서
            <select
              value={selectedId}
              disabled={pending}
              onChange={(e) => setSensorId(e.target.value)}
            >
              {sensors.map((item) => (
                <option
                  key={item.sensor_id}
                  value={item.sensor_id}
                  disabled={activeSensorIds.has(item.sensor_id)}
                >
                  {item.name}
                  {activeSensorIds.has(item.sensor_id) ? ' (고장 중)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label>
            유형
            <select
              value={faultType}
              disabled={pending}
              onChange={(e) => {
                setFaultType(e.target.value as FaultType)
                setAmount('')
              }}
            >
              {FAULT_OPTS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          {amountLabel ? (
            <label>
              {amountLabel}
              <input
                type="number"
                step="any"
                value={amount}
                placeholder={faultType === 'spike' ? '기본값' : '현재값'}
                disabled={pending}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
          ) : null}
          <button
            type="button"
            className="control-apply"
            disabled={pending || !selectedId}
            onClick={submit}
          >
            {pending ? '처리 중…' : '주입'}
          </button>
          <p className="control-hint">
            {FAULT_OPTS.find((opt) => opt.id === faultType)?.hint}
          </p>
        </div>
      )}
      {error ? <p className="error">{error}</p> : null}

      {faults.length > 0 ? (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>센서</th>
                <th>유형</th>
                <th>구간(시뮬)</th>
                <th>상태</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {faults.map((fault) => (
                <tr key={fault.id}>
                  <td>
                    <strong>{fault.sensor_code}</strong>
                  </td>
                  <td>
                    {FAULT_LABEL[fault.fault_type]} <em>{faultDetail(fault)}</em>
                  </td>
                  <td>{simSpan(fault)}</td>
                  <td>
                    <span
                      className={`ops-badge tone-${fault.active ? 'alert' : 'info'}`}
                    >
                      {fault.active ? '주입 중' : '해제'}
                    </span>
                  </td>
                  <td>
                    {fault.active && runId ? (
                      <button
                        type="button"
                        className="control-off"
                        disabled={pending}
                        onClick={() => void run(() => clearFault(runId, fault.id))}
                      >
                        해제
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
