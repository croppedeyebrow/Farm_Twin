import { useMemo } from 'react'



import type { FarmStateSnapshot } from '../../api/farms'

import type { TimelineEntry } from '../../store/realtimeStore'

import { formatEventTime, SAFETY_RULES } from './opsRules'



type FeedItem = {

  id: string

  timeLabel: string

  title: string

  detail: string

  badge: string

  tone: 'warn' | 'control' | 'info'

}



type Props = {

  timeline: TimelineEntry[]

  state: FarmStateSnapshot | null

  scenarioLabel: string

  outdoorTempC: number

}



export function OpsEventFeed({

  timeline,

  state,

  scenarioLabel,

  outdoorTempC,

}: Props) {

  const items = useMemo(() => {

    const now = new Date()

    const derived: FeedItem[] = []



    if (state) {

      derived.push({

        id: 'sensor-refresh',

        timeLabel: formatEventTime(now),

        title: '센서 측정 갱신',

        detail: `온도 ${state.temperature_c.toFixed(1)}℃ · 습도 ${state.humidity_pct.toFixed(1)}% · 토양 ${state.substrate_moisture_pct.toFixed(1)}%`,

        badge: '정보',

        tone: 'info',

      })



      if (state.temperature_c > 30) {

        derived.push({

          id: 'rule-high-temp',

          timeLabel: formatEventTime(new Date(now.getTime() - 40_000)),

          title: '고온 임계값 초과',

          detail: `실내 온도 ${state.temperature_c.toFixed(0)}℃ 초과 · 냉방/환기 요청`,

          badge: '주의',

          tone: 'warn',

        })

      } else {

        derived.push({

          id: 'auto-check',

          timeLabel: formatEventTime(new Date(now.getTime() - 60_000)),

          title: '자동 제어 점검',

          detail: '기준 지표가 정상 범위입니다.',

          badge: '정보',

          tone: 'info',

        })

      }

    }



    derived.push({

      id: 'weather',

      timeLabel: formatEventTime(new Date(now.getTime() - 120_000)),

      title: '외부 기상 반영',

      detail:

        scenarioLabel.includes('폭염') || outdoorTempC >= 35

          ? `외부 온도 ${outdoorTempC.toFixed(1)}℃ · 폭염 시나리오`

          : `외부 온도 ${outdoorTempC.toFixed(1)}℃ 시뮬레이션 반영`,

      badge: '정보',

      tone: 'info',

    })



    for (const entry of timeline.slice(0, 4)) {

      if (derived.length >= 6) break

      derived.push({

        id: entry.id,

        timeLabel: `t=${entry.simulation_time.toFixed(0)}s`,

        title: entry.title,

        detail: entry.detail,

        badge:

          entry.kind === 'control'

            ? '제어'

            : entry.kind === 'state'

              ? '상태'

              : '정보',

        tone: entry.kind === 'control' ? 'control' : 'info',

      })

    }



    return derived

  }, [timeline, state, scenarioLabel, outdoorTempC])



  return (

    <section className="ops-panel ops-events" aria-label="최근 상태 및 설비 제어">

      <header className="ops-panel-head">

        <h2>최근 상태 및 설비 제어</h2>

        <span className="ops-sort-tag">최신순</span>

      </header>

      {items.length === 0 ? (

        <p className="ops-empty">제어 이벤트 또는 상태 변화가 여기 쌓입니다.</p>

      ) : (

        <ul className="ops-event-list">

          {items.map((item) => (

            <li key={item.id}>

              <time>{item.timeLabel}</time>

              <div>

                <strong>{item.title}</strong>

                <p>{item.detail}</p>

              </div>

              <em

                className={`ops-badge tone-${

                  item.tone === 'warn'

                    ? 'warn'

                    : item.tone === 'control'

                      ? 'control'

                      : 'info'

                }`}

              >

                {item.badge}

              </em>

            </li>

          ))}

        </ul>

      )}

    </section>

  )

}



export function OpsSafetyRules() {

  return (

    <section className="ops-panel ops-safety" aria-label="운전 기준">

      <header className="ops-panel-head">

        <h2>운전 기준</h2>

      </header>

      <ul className="ops-safety-list">

        {SAFETY_RULES.map((rule) => (

          <li key={rule.id}>

            <strong>{rule.title}</strong>

            <span>{rule.detail}</span>

          </li>

        ))}

      </ul>

      <p className="ops-safety-note">

        기초적인 규칙 예시를 화면에 반영했습니다. 이 데모의 설비 상태는

        시뮬레이션이며 실제 장치를 제어하지 않습니다.

      </p>

    </section>

  )

}


