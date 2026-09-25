/**
 * 공통 앱 셸 — 다크 사이드바 + 실시간 세션.
 *
 * WORKSPACE: 환경 관제 / 센서 기록 / 설비 제어
 * VIEW: 3D 트윈 / 생육
 */

import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { DEMO_FARM_ID } from '../config'
import {
  labelFor,
  socketDataState,
  socketLabel,
  type HealthState,
} from '../lib/statusLabels'
import {
  startFarmRealtimeSession,
  stopFarmRealtimeSession,
} from '../realtime/session'
import { useRealtimeStore } from '../store/realtimeStore'

const WORKSPACE = [
  { to: '/', end: true, label: '환경 관제' },
  { to: '/records', end: false, label: '센서 기록' },
  { to: '/control', end: false, label: '설비 제어' },
] as const

const VIEW = [
  { to: '/twin', label: '3D 트윈' },
  { to: '/crops', label: '생육' },
] as const

export function AppShell() {
  const location = useLocation()
  const isOps =
    location.pathname === '/' ||
    location.pathname === '/records' ||
    location.pathname === '/control'

  const [health, setHealth] = useState<HealthState>('loading')
  const [ready, setReady] = useState<HealthState>('loading')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)

  const socketStatus = useRealtimeStore((s) => s.socketStatus)
  const lastSequence = useRealtimeStore((s) => s.lastSequence)
  const stale = useRealtimeStore((s) => s.stale)
  const recovering = useRealtimeStore((s) => s.recovering)
  const realtimeError = useRealtimeStore((s) => s.lastError)

  useEffect(() => {
    let cancelled = false

    async function checkApi() {
      try {
        const healthResponse = await fetch('/api/health')
        if (!healthResponse.ok) {
          throw new Error(`health ${healthResponse.status}`)
        }
        if (!cancelled) setHealth('ok')

        const readyResponse = await fetch('/api/health/ready')
        if (!cancelled) {
          setReady(readyResponse.ok ? 'ok' : 'error')
          if (!readyResponse.ok) {
            const body = (await readyResponse.json().catch(() => null)) as
              | { detail?: string }
              | null
            setErrorDetail(body?.detail ?? `ready ${readyResponse.status}`)
          }
        }
      } catch (error) {
        if (!cancelled) {
          setHealth('error')
          setReady('error')
          setErrorDetail(
            error instanceof Error ? error.message : 'request failed',
          )
        }
      }
    }

    void checkApi()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    void startFarmRealtimeSession(DEMO_FARM_ID)
    return () => {
      stopFarmRealtimeSession()
    }
  }, [])

  return (
    <div className={isOps ? 'app-root app-root-ops' : 'app-root app-root-view'}>
      <aside className="ops-sidebar" aria-label="워크스페이스">
        <div className="ops-brand">
          Farm<span>Twin</span>
        </div>

        <p className="ops-nav-label">WORKSPACE</p>
        <nav className="ops-side-nav" aria-label="운영">
          {WORKSPACE.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? 'ops-side-link is-active' : 'ops-side-link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <p className="ops-nav-label">VIEW</p>
        <nav className="ops-side-nav" aria-label="뷰">
          {VIEW.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? 'ops-side-link is-active' : 'ops-side-link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ops-side-foot">
          <p>실내 스마트팜 디지털트윈</p>
          <p>DEMO 가상 센서 데이터</p>
          <ul className="ops-side-status" aria-live="polite">
            <li>
              API <strong data-state={health}>{labelFor(health)}</strong>
            </li>
            <li>
              WS{' '}
              <strong data-state={socketDataState(socketStatus)}>
                {socketLabel(socketStatus)}
              </strong>
            </li>
            <li>
              Seq <strong>{lastSequence}</strong>
            </li>
            <li>
              데이터{' '}
              <strong data-state={stale || recovering ? 'error' : 'ok'}>
                {recovering ? '복구 중' : stale ? 'stale' : '최신'}
              </strong>
            </li>
            <li>
              Ready <strong data-state={ready}>{labelFor(ready)}</strong>
            </li>
          </ul>
        </div>
      </aside>

      <div className="ops-shell-main">
        {(errorDetail || realtimeError) && (
          <div className="app-banner-errors">
            {errorDetail ? <p className="error">{errorDetail}</p> : null}
            {realtimeError ? <p className="error">{realtimeError}</p> : null}
          </div>
        )}
        <div className="app-main">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
