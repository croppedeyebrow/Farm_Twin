/**
 * OPERATIONS 공통 페이지 헤더 — 시나리오 · 일시정지 · 배너 · 시계
 */

import { useEffect, useState, type ReactNode } from 'react'

import { OPS_SCENARIOS, formatClock } from './opsRules'
import { currentScenario, useOpsUiStore } from '../../store/opsUiStore'

type Props = {
  title: string
  subtitle?: string
  bannerOverride?: string | null
  children?: ReactNode
}

export function OpsPageChrome({
  title,
  subtitle = '재배실 센서 상태와 제어 흐름',
  bannerOverride,
  children,
}: Props) {
  const scenarioId = useOpsUiStore((s) => s.scenarioId)
  const paused = useOpsUiStore((s) => s.paused)
  const menuOpen = useOpsUiStore((s) => s.scenarioMenuOpen)
  const setScenarioId = useOpsUiStore((s) => s.setScenarioId)
  const togglePaused = useOpsUiStore((s) => s.togglePaused)
  const setScenarioMenuOpen = useOpsUiStore((s) => s.setScenarioMenuOpen)

  const scenario = currentScenario(scenarioId)
  const [clock, setClock] = useState(() => new Date())

  useEffect(() => {
    if (paused) return
    const id = window.setInterval(() => setClock(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [paused])

  useEffect(() => {
    if (!menuOpen) return
    const onDoc = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.ops-scenario')) return
      setScenarioMenuOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuOpen, setScenarioMenuOpen])

  const banner =
    bannerOverride ??
    (paused ? '일시정지됨 · 표시값 고정' : scenario.banner)

  return (
    <>
      <header className="ops-page-header">
        <div className="ops-page-titles">
          <p className="ops-breadcrumb">FARMTWIN / OPERATIONS</p>
          <h1>{title}</h1>
          <p className="ops-lede">{subtitle}</p>
        </div>

        <div className="ops-page-controls">
          <div className="ops-scenario">
            <button
              type="button"
              className="ops-scenario-trigger"
              aria-expanded={menuOpen}
              aria-haspopup="listbox"
              onClick={() => setScenarioMenuOpen(!menuOpen)}
            >
              {scenario.label}
              <span aria-hidden>▾</span>
            </button>
            {menuOpen ? (
              <ul className="ops-scenario-menu" role="listbox">
                {OPS_SCENARIOS.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={item.id === scenarioId}
                      className={
                        item.id === scenarioId ? 'is-selected' : undefined
                      }
                      onClick={() => setScenarioId(item.id)}
                    >
                      {item.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <button
            type="button"
            className="ops-pause-btn"
            onClick={togglePaused}
          >
            {paused ? '▶ 재개' : '일시정지'}
          </button>
          <time className="ops-clock" dateTime={clock.toISOString()}>
            마지막 갱신 {formatClock(clock)}
          </time>
        </div>
      </header>

      <p
        className="ops-sim-banner ops-sim-banner-bar"
        data-paused={paused ? 'true' : 'false'}
      >
        <span className="ops-sim-dot" aria-hidden />
        <span>{banner}</span>
        <time dateTime={clock.toISOString()}>{formatClock(clock)}</time>
      </p>

      {children}
    </>
  )
}
