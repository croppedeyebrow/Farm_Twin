import { useEffect, useState } from 'react'
import './App.css'
import { GrowingRoomScene } from './scene/GrowingRoomScene'

type HealthState = 'loading' | 'ok' | 'error'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [ready, setReady] = useState<HealthState>('loading')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function checkApi() {
      try {
        const healthResponse = await fetch('/api/health')
        if (!healthResponse.ok) {
          throw new Error(`health ${healthResponse.status}`)
        }
        if (!cancelled) {
          setHealth('ok')
        }

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
