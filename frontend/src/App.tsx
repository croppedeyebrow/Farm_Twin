/**
 * 1단계 관제 셸 (Day 2 health 확인 + Day 3 빈 3D 재배실).
 *
 * 레이아웃
 * - 전체 화면 3D 뷰포트 (상태 탐색 UI의 시각 앵커)
 * - 좌상단 오버레이: 브랜드 + API health/ready 상태
 *
 * API 호출 경로
 * - 개발: Vite proxy `/api/*` → `http://127.0.0.1:8000/*`
 * - Compose: 브라우저 → Nginx `/api/` → FastAPI
 */
import { useEffect, useState } from 'react'
import './App.css'
import { GrowingRoomScene } from './scene/GrowingRoomScene'

/** UI에 표시하는 health 조회 상태. */
type HealthState = 'loading' | 'ok' | 'error'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [ready, setReady] = useState<HealthState>('loading')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)

  useEffect(() => {
    // StrictMode 더블 마운트 / 언마운트 시 늦은 응답이 state 를 덮어쓰지 않게 한다.
    let cancelled = false

    async function checkApi() {
      try {
        // Liveness: 프로세스 생존
        const healthResponse = await fetch('/api/health')
        if (!healthResponse.ok) {
          throw new Error(`health ${healthResponse.status}`)
        }
        if (!cancelled) {
          setHealth('ok')
        }

        // Readiness: DB 연결. 실패해도 화면은 유지하고 상태만 표시한다.
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
          setErrorDetail(error instanceof Error ? error.message : 'request failed')
        }
      }
    }

    void checkApi()

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="shell">
      {/* 풀블리드 3D — 1단계 완료 기준: 빈 재배실 표시 */}
      <div className="viewport" aria-label="빈 3D 재배실">
        <GrowingRoomScene />
      </div>

      <header className="overlay">
        <p className="brand-name">FarmTwin</p>
        <h1>실내 스마트팜 운영 트윈</h1>
        <p className="lede">빈 재배실과 랙 골격 — 드래그로 시점을 회전합니다.</p>

        <section className="status" aria-live="polite">
          <div className="status-row">
            <span>API /health</span>
            <strong data-state={health}>{labelFor(health)}</strong>
          </div>
          <div className="status-row">
            <span>API /health/ready</span>
            <strong data-state={ready}>{labelFor(ready)}</strong>
          </div>
          {errorDetail ? <p className="error">{errorDetail}</p> : null}
        </section>
      </header>
    </main>
  )
}

function labelFor(state: HealthState): string {
  if (state === 'loading') return '확인 중'
  if (state === 'ok') return '정상'
  return '실패'
}

export default App
