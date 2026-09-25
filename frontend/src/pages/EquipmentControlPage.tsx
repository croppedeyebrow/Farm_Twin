/**
 * 설비 제어 — 운전 기준 · 모드 · 이벤트 이력
 */

import { useEffect, useMemo, useState } from 'react'

import { OpsPageChrome } from '../components/ops/OpsPageChrome'
import { formatStamp } from '../components/ops/opsRules'
import {
  currentScenario,
  useOpsUiStore,
  type DriveMode,
} from '../store/opsUiStore'
import { useRealtimeStore } from '../store/realtimeStore'

type ControlEventRow = {
  id: string
  at: Date
  kind: string
  target: string
  basis: string
  result: string
}

export function EquipmentControlPage() {
  const state = useRealtimeStore((s) => s.state)
  const timeline = useRealtimeStore((s) => s.timeline)
  const scenarioId = useOpsUiStore((s) => s.scenarioId)
  const driveMode = useOpsUiStore((s) => s.driveMode)
  const modeMenuOpen = useOpsUiStore((s) => s.modeMenuOpen)
  const draftRules = useOpsUiStore((s) => s.draftRules)
  const appliedRules = useOpsUiStore((s) => s.appliedRules)
  const setDriveMode = useOpsUiStore((s) => s.setDriveMode)
  const setModeMenuOpen = useOpsUiStore((s) => s.setModeMenuOpen)
  const setDraftRule = useOpsUiStore((s) => s.setDraftRule)
  const applyRules = useOpsUiStore((s) => s.applyRules)
  const scenario = currentScenario(scenarioId)
  const [appliedFlash, setAppliedFlash] = useState(false)

  useEffect(() => {
    if (!modeMenuOpen) return
    const onDoc = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.ops-mode')) return
      setModeMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [modeMenuOpen, setModeMenuOpen])

  const rows = useMemo(() => {
    const now = new Date()
    const built: ControlEventRow[] = []

    if (state) {
      built.push({
        id: 'temp',
        at: now,
        kind: '정보',
        target: `온도 측정 갱신 (TEMP-01)`,
        basis: `${state.temperature_c.toFixed(1)} ℃`,
        result: state.temperature_c > appliedRules.coolStartC ? '주의' : '정상',
      })
      built.push({
        id: 'hum',
        at: new Date(now.getTime() - 30_000),
        kind: '정보',
        target: `습도 측정 갱신 (HUM-01)`,
        basis: `${state.humidity_pct.toFixed(1)} %`,
        result:
          state.humidity_pct < appliedRules.humidStartPct ? '주의' : '정상',
      })
      built.push({
        id: 'soil',
        at: new Date(now.getTime() - 60_000),
        kind: '정보',
        target: `토양수분 측정 갱신 (SOIL-01)`,
        basis: `${state.substrate_moisture_pct.toFixed(1)} %`,
        result:
          state.substrate_moisture_pct < appliedRules.irrigateStartPct
            ? '주의'
            : '정상',
      })
      built.push({
        id: 'rule',
        at: new Date(now.getTime() - 90_000),
        kind: '정보',
        target: '규칙 검사 완료 (자동 제어)',
        basis:
          driveMode === 'auto'
            ? '자동 운전 기준 적용'
            : '수동 운전 · 규칙 감시만',
        result: '대기',
      })
    }

    for (const entry of timeline.slice(0, 4)) {
      built.push({
        id: entry.id,
        at: new Date(),
        kind: entry.kind === 'control' ? '제어' : '정보',
        target: entry.title,
        basis: entry.detail,
        result: entry.kind === 'control' ? '적용' : '정상',
      })
    }

    return built
  }, [state, timeline, appliedRules, driveMode])

  const anomalyCount = rows.filter(
    (r) => r.result === '주의' || r.result === '경고',
  ).length
  const controlCount = rows.filter(
    (r) => r.kind === '제어' || r.result === '적용',
  ).length

  function onApply() {
    applyRules()
    setAppliedFlash(true)
    window.setTimeout(() => setAppliedFlash(false), 1600)
  }

  const modeLabel: Record<DriveMode, string> = {
    auto: '자동 운전',
    manual: '수동 운전',
  }

  return (
    <main className="page page-ops" aria-label="설비 제어">
      <OpsPageChrome title="설비 제어" />

      <section className="ops-metrics ops-metrics-3" aria-label="제어 요약">
        <article className="ops-metric-card">
          <header>
            <span>이벤트 합계</span>
          </header>
          <strong>
            {rows.length}
            <span>건</span>
          </strong>
          <p>현재 시나리오 · {scenario.label}</p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>이상 감지</span>
          </header>
          <strong>
            {anomalyCount}
            <span>건</span>
          </strong>
          <p>임계값 데이터 신뢰도</p>
        </article>
        <article className="ops-metric-card">
          <header>
            <span>제어 동작</span>
          </header>
          <strong>
            {Math.max(controlCount, 1)}
            <span>건</span>
          </strong>
          <p>가상 설비 모델링 및 대기</p>
        </article>
      </section>

      <div className="ops-control-row">
        <section className="ops-panel" aria-label="자동 운전 기준">
          <header className="ops-panel-head">
            <h2>자동 운전 기준</h2>
          </header>
          <p className="ops-hint">
            측정값이 기준을 넘으면 해당 설비가 자동 모드에서 기동됩니다.
          </p>
          <div className="ops-rule-fields">
            <label>
              냉방 시작 온도
              <span>
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={1}
                  value={draftRules.coolStartC}
                  onChange={(e) =>
                    setDraftRule('coolStartC', Number(e.target.value))
                  }
                />
                ℃
              </span>
            </label>
            <label>
              가습 시작 습도
              <span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={draftRules.humidStartPct}
                  onChange={(e) =>
                    setDraftRule('humidStartPct', Number(e.target.value))
                  }
                />
                %
              </span>
            </label>
            <label>
              관수 시작 토양수분
              <span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={draftRules.irrigateStartPct}
                  onChange={(e) =>
                    setDraftRule('irrigateStartPct', Number(e.target.value))
                  }
                />
                %
              </span>
            </label>
          </div>
          <button type="button" className="ops-apply-btn" onClick={onApply}>
            운전 기준 적용
          </button>
          <p className="ops-rule-foot" data-flash={appliedFlash ? 'true' : 'false'}>
            현재 기준: 온도 &gt; {appliedRules.coolStartC}℃ · 습도 &lt;{' '}
            {appliedRules.humidStartPct}% · 토양수분 &lt;{' '}
            {appliedRules.irrigateStartPct}%
          </p>
        </section>

        <section className="ops-panel" aria-label="운전 모드 · 설비">
          <header className="ops-panel-head">
            <h2>운전 모드 · 설비</h2>
          </header>
          <div className="ops-mode">
            <span className="ops-field-label">운전 모드</span>
            <button
              type="button"
              className="ops-scenario-trigger"
              aria-expanded={modeMenuOpen}
              onClick={() => setModeMenuOpen(!modeMenuOpen)}
            >
              {modeLabel[driveMode]}
              <span aria-hidden>▾</span>
            </button>
            {modeMenuOpen ? (
              <ul className="ops-scenario-menu ops-mode-menu" role="listbox">
                <li>
                  <button
                    type="button"
                    className={driveMode === 'auto' ? 'is-selected' : undefined}
                    onClick={() => setDriveMode('auto')}
                  >
                    자동 운전
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    className={
                      driveMode === 'manual' ? 'is-selected' : undefined
                    }
                    onClick={() => setDriveMode('manual')}
                  >
                    수동 운전
                  </button>
                </li>
              </ul>
            ) : null}
          </div>
          <p className="ops-hint">
            자동 모드로 설정하면 운전 기준에 따라 설비 상태가 갱신됩니다.
          </p>
        </section>
      </div>

      <section className="ops-panel ops-table-panel" aria-label="이벤트 이력">
        <header className="ops-panel-head">
          <h2>이벤트 이력</h2>
          <span className="ops-sort-tag">최신순</span>
        </header>
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>발생 시각</th>
                <th>유형</th>
                <th>대상 / 내용</th>
                <th>판단 근거</th>
                <th>결과</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{formatStamp(row.at)}</td>
                  <td>
                    <span className="ops-badge tone-ok">{row.kind}</span>
                  </td>
                  <td>{row.target}</td>
                  <td>{row.basis}</td>
                  <td>{row.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
