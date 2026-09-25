import type { FarmStateSnapshot } from '../../api/farms'
import {
  humidityBadge,
  outdoorBadge,
  soilBadge,
  tempBadge,
} from './opsRules'

type Props = {
  state: FarmStateSnapshot | null
  outdoorTempC: number
  stale: boolean
}

export function OpsMetricCards({ state, outdoorTempC, stale }: Props) {
  const temp = state?.temperature_c ?? null
  const hum = state?.humidity_pct ?? null
  const soil = state?.substrate_moisture_pct ?? null

  const tBadge = temp == null ? null : tempBadge(temp)
  const hBadge = hum == null ? null : humidityBadge(hum)
  const sBadge = soil == null ? null : soilBadge(soil)
  const oBadge = outdoorBadge(outdoorTempC)

  return (
    <section className="ops-metrics" aria-label="실시간 센서 카드">
      <article className="ops-metric-card">
        <header>
          <span>실내 온도</span>
          {tBadge ? (
            <em className={`ops-badge tone-${tBadge.tone}`}>{tBadge.label}</em>
          ) : null}
        </header>
        <strong>
          {temp == null ? '—' : `${temp.toFixed(1)}`}
          <span>℃</span>
        </strong>
        <p>TEMP-01 / 가상 센서{stale ? ' · stale' : ''}</p>
      </article>

      <article className="ops-metric-card">
        <header>
          <span>실내 습도</span>
          {hBadge ? (
            <em className={`ops-badge tone-${hBadge.tone}`}>{hBadge.label}</em>
          ) : null}
        </header>
        <strong>
          {hum == null ? '—' : `${hum.toFixed(1)}`}
          <span>%</span>
        </strong>
        <p>HUM-01 / 가상 센서</p>
      </article>

      <article className="ops-metric-card">
        <header>
          <span>토양수분</span>
          {sBadge ? (
            <em className={`ops-badge tone-${sBadge.tone}`}>{sBadge.label}</em>
          ) : null}
        </header>
        <strong>
          {soil == null ? '—' : `${soil.toFixed(1)}`}
          <span>%</span>
        </strong>
        <p>SOIL-01 / 가상 센서</p>
      </article>

      <article className="ops-metric-card">
        <header>
          <span>외부 온도</span>
          <em className={`ops-badge tone-${oBadge.tone}`}>{oBadge.label}</em>
        </header>
        <strong>
          {outdoorTempC.toFixed(1)}
          <span>℃</span>
        </strong>
        <p>WEATHER / 외부 기상 시뮬레이션</p>
      </article>
    </section>
  )
}
