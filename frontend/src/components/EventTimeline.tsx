/**
 * 이벤트 타임라인 (5단계 Day 18).
 *
 * - control: REST /farms/{id}/events
 * - simulation / state: WS 증분에서 로컬 파생
 * 최신 simulation_time 이 위.
 */

import type { TimelineEntry } from '../store/realtimeStore'

type Props = {
  entries: TimelineEntry[]
}

export function EventTimeline({ entries }: Props) {
  return (
    <section className="timeline-panel" aria-label="이벤트 타임라인">
      <h2>이벤트</h2>
      {entries.length === 0 ? (
        <p className="panel-empty">
          제어 이벤트 또는 시뮬 상태 변화가 여기 쌓입니다.
        </p>
      ) : (
        <ol className="timeline-list">
          {entries.map((entry) => (
            <li key={entry.id} data-kind={entry.kind}>
              <div className="timeline-head">
                <strong>{entry.title}</strong>
                <span>t={entry.simulation_time.toFixed(0)}s</span>
              </div>
              <p>{entry.detail}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
