/**
 * 작물 생육 상태 페이지.
 *
 * MVP: 환경 KPI + 라인 메타로 생육 적합도·단계를 추정한다.
 * (정밀 생리 모델은 이후 단계)
 */

import { useMemo, useState } from 'react'

import { STRAWBERRY_ROW_X, GRAPE_CORRIDOR_PLACEMENTS } from '../scene/rackLayout'
import { useCropTuneStore } from '../store/cropTuneStore'
import { useRealtimeStore } from '../store/realtimeStore'
import type { FarmStateSnapshot } from '../api/farms'

type CropLine = {
  id: string
  kind: 'strawberry' | 'grape'
  label: string
  name: string
}

const LINES: CropLine[] = [
  ...STRAWBERRY_ROW_X.map((_, i) => ({
    id: `S${i + 1}`,
    kind: 'strawberry' as const,
    label: `S${i + 1}`,
    name: `딸기 라인 ${i + 1}`,
  })),
  ...GRAPE_CORRIDOR_PLACEMENTS.map((g) => ({
    id: g.label,
    kind: 'grape' as const,
    label: g.label,
    name: `포도 터널 ${g.label}`,
  })),
]

type GrowthAssessment = {
  stage: string
  score: number
  level: 'good' | 'warn' | 'bad' | 'unknown'
  notes: string[]
}

function assessGrowth(
  kind: CropLine['kind'],
  state: FarmStateSnapshot | null,
): GrowthAssessment {
  if (!state) {
    return {
      stage: '데이터 없음',
      score: 0,
      level: 'unknown',
      notes: ['환경 스냅샷이 없습니다. 시뮬/연결을 확인하세요.'],
    }
  }

  const notes: string[] = []
  let score = 100

  const t = state.temperature_c
  const h = state.humidity_pct
  const m = state.substrate_moisture_pct
  const p = state.ppfd_umol

  if (kind === 'strawberry') {
    if (t < 15 || t > 28) {
      score -= 25
      notes.push(`온도 ${t.toFixed(1)}°C — 딸기 적정(약 18~25°C) 밖`)
    } else if (t < 18 || t > 25) {
      score -= 10
      notes.push(`온도 ${t.toFixed(1)}°C — 약간 벗어남`)
    }

    if (h < 45 || h > 80) {
      score -= 20
      notes.push(`습도 ${h.toFixed(0)}% — 적정(45~80%) 밖`)
    }

    if (m < 30 || m > 70) {
      score -= 20
      notes.push(`배지 ${m.toFixed(0)}% — 수분 점검 필요`)
    } else {
      notes.push(`배지 ${m.toFixed(0)}% — 수분 양호`)
    }

    if (p < 50) {
      score -= 15
      notes.push('PPFD 낮음 — LED 조도를 올리세요')
    } else if (p > 600) {
      score -= 10
      notes.push('PPFD 높음 — 광 스트레스 주의')
    } else {
      notes.push(`PPFD ${p.toFixed(0)} — 광량 범위 내`)
    }

    const stage =
      p < 30 ? '휴면·저광' : m < 35 ? '수분 스트레스' : t > 26 ? '고온 관리' : '영양생장'

    return {
      stage,
      score: Math.max(0, Math.min(100, score)),
      level: score >= 75 ? 'good' : score >= 50 ? 'warn' : 'bad',
      notes,
    }
  }

  // grape
  if (t < 18 || t > 32) {
    score -= 25
    notes.push(`온도 ${t.toFixed(1)}°C — 포도 적정(약 20~28°C) 밖`)
  }
  if (h > 85) {
    score -= 15
    notes.push(`습도 ${h.toFixed(0)}% — 병해 위험`)
  }
  if (p < 80) {
    score -= 15
    notes.push('PPFD 낮음 — 착색·당도 지연 가능')
  } else {
    notes.push(`PPFD ${p.toFixed(0)} — 광량 참고`)
  }

  return {
    stage: p < 50 ? '저광 생장' : t > 30 ? '고온 관리' : '수관 생장',
    score: Math.max(0, Math.min(100, score)),
    level: score >= 75 ? 'good' : score >= 50 ? 'warn' : 'bad',
    notes: notes.length ? notes : ['환경이 대체로 양호합니다.'],
  }
}

export function CropGrowthPage() {
  const state = useRealtimeStore((s) => s.state)
  const strawberry = useCropTuneStore((s) => s.strawberry)
  const grape = useCropTuneStore((s) => s.grape)
  const [selectedId, setSelectedId] = useState(LINES[0]?.id ?? 'S1')

  const selected = LINES.find((l) => l.id === selectedId) ?? LINES[0]
  const assessment = useMemo(
    () => assessGrowth(selected.kind, state),
    [selected.kind, state],
  )

  const tune = selected.kind === 'strawberry' ? strawberry : grape

  return (
    <main className="page page-crops" aria-label="작물 생육">
      <header className="page-header">
        <div>
          <h1>작물 생육</h1>
          <p className="lede">
            라인별 생육 적합도와 단계를 환경값 기준으로 추정합니다.
          </p>
        </div>
      </header>

      <div className="crops-layout">
        <section className="crops-lines" aria-label="재배 라인">
          <h2>라인</h2>
          <ul className="entity-list">
            {LINES.map((line) => {
              const a = assessGrowth(line.kind, state)
              return (
                <li key={line.id}>
                  <button
                    type="button"
                    className={
                      line.id === selected.id ? 'is-selected' : undefined
                    }
                    onClick={() => setSelectedId(line.id)}
                  >
                    <span>
                      {line.label}
                      <em className="sensor-kind">
                        {line.kind === 'strawberry' ? '딸기' : '포도'}
                      </em>
                    </span>
                    <em data-level={a.level}>{a.score}</em>
                  </button>
                </li>
              )
            })}
          </ul>
        </section>

        <section className="crops-detail" aria-label="생육 상세">
          <div className="panel-title-row">
            <h2>{selected.name}</h2>
            <span className="growth-badge" data-level={assessment.level}>
              {assessment.level === 'good'
                ? '양호'
                : assessment.level === 'warn'
                  ? '주의'
                  : assessment.level === 'bad'
                    ? '불량'
                    : '미확인'}
            </span>
          </div>

          <dl className="detail-dl growth-summary">
            <div>
              <dt>추정 단계</dt>
              <dd>{assessment.stage}</dd>
            </div>
            <div>
              <dt>적합도</dt>
              <dd>{assessment.score} / 100</dd>
            </div>
            <div>
              <dt>3D 스케일</dt>
              <dd>{tune.scale.toFixed(2)}</dd>
            </div>
            <div>
              <dt>오프셋</dt>
              <dd>
                ({tune.offsetX.toFixed(2)}, {tune.offsetY.toFixed(2)},{' '}
                {tune.offsetZ.toFixed(2)})
              </dd>
            </div>
          </dl>

          <div className="growth-meter" aria-hidden>
            <div
              className="growth-meter-fill"
              data-level={assessment.level}
              style={{ width: `${assessment.score}%` }}
            />
          </div>

          <h3>환경 메모</h3>
          <ul className="growth-notes">
            {assessment.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>

          {state ? (
            <dl className="detail-dl">
              <div>
                <dt>온도</dt>
                <dd>{state.temperature_c.toFixed(1)} °C</dd>
              </div>
              <div>
                <dt>습도</dt>
                <dd>{state.humidity_pct.toFixed(0)} %</dd>
              </div>
              <div>
                <dt>배지</dt>
                <dd>{state.substrate_moisture_pct.toFixed(0)} %</dd>
              </div>
              <div>
                <dt>PPFD</dt>
                <dd>{state.ppfd_umol.toFixed(0)}</dd>
              </div>
            </dl>
          ) : null}

          <p className="control-hint">
            MVP 추정입니다. 정식 생육 모델·라인별 센서는 이후 단계에서
            연결합니다. 3D 배치는 「3D 트윈」의 작물 튜닝에서 조정하세요.
          </p>
        </section>
      </div>
    </main>
  )
}
