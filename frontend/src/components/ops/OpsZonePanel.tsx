/**
 * 작물 구역 패널 — 딸기 / 포도 setpoint·근권·파생값 분리 표시
 *
 * 목적
 * ----
 * 룸 KPI(온·습·CO₂)와 별도로, 구역 고유 상태(VWC·EC·엽면습윤·밸브·병해·
 * 추정 Brix)와 공유 제어 요구(병해완화·LED/DLI)를 보여 준다.
 *
 * 이유
 * ----
 * 딸기·포도를 같은 제어값으로 보면 안 된다는 설계를 UI에서 강제한다.
 * estimated_brix 는 추정 — 당도계 검증 전제.
 */

import type { FarmZonesSnapshot, ZoneStateSnapshot } from '../../api/farms'
import { useOpsUiStore } from '../../store/opsUiStore'

type Props = {
  zones: FarmZonesSnapshot | null
}

function ZoneBody({ zone }: { zone: ZoneStateSnapshot }) {
  return (
    <dl className="ops-zone-dl">
      <div>
        <dt>배지 VWC</dt>
        <dd>{zone.substrate_vwc_pct.toFixed(1)} %</dd>
      </div>
      <div>
        <dt>배지 EC</dt>
        <dd>{zone.substrate_ec.toFixed(2)} mS/cm</dd>
      </div>
      <div>
        <dt>배지 온도</dt>
        <dd>{zone.substrate_temperature_c.toFixed(1)} ℃</dd>
      </div>
      <div>
        <dt>양액 pH</dt>
        <dd>{zone.nutrient_ph.toFixed(1)}</dd>
      </div>
      <div>
        <dt>VPD</dt>
        <dd>{zone.vpd_kpa.toFixed(2)} kPa</dd>
      </div>
      <div>
        <dt>DLI (당일)</dt>
        <dd>{zone.dli_today.toFixed(2)} mol</dd>
      </div>
      <div>
        <dt>엽면습윤</dt>
        <dd>{zone.leaf_wetness_minutes.toFixed(0)} min</dd>
      </div>
      <div>
        <dt>관수 유량</dt>
        <dd>{zone.irrigation_flow_lpm.toFixed(1)} L/min</dd>
      </div>
      <div>
        <dt>구역 밸브</dt>
        <dd data-on={zone.irrigation_valve_open ? 'true' : 'false'}>
          {zone.irrigation_valve_open ? 'OPEN' : 'CLOSED'}
        </dd>
      </div>
      <div>
        <dt>수분 스트레스</dt>
        <dd>{zone.water_stress_score.toFixed(0)}</dd>
      </div>
      <div>
        <dt>병해 위험</dt>
        <dd>{zone.disease_risk_score.toFixed(0)}</dd>
      </div>
      <div>
        <dt>추정 Brix</dt>
        <dd>
          {zone.estimated_brix.toFixed(1)}
          <em className="ops-est-tag">추정</em>
        </dd>
      </div>
    </dl>
  )
}

export function OpsZonePanel({ zones }: Props) {
  const selectedZone = useOpsUiStore((s) => s.selectedZone)
  const setSelectedZone = useOpsUiStore((s) => s.setSelectedZone)

  const zone =
    zones == null
      ? null
      : selectedZone === 'grape'
        ? zones.grape
        : zones.strawberry

  return (
    <section className="ops-panel ops-zone-panel" aria-label="작물 구역 상태">
      <header className="ops-panel-head">
        <h2>작물 구역</h2>
        <div className="ops-window-tabs" role="tablist" aria-label="구역 선택">
          <button
            type="button"
            role="tab"
            aria-selected={selectedZone === 'strawberry'}
            className={
              selectedZone === 'strawberry'
                ? 'ops-window-tab is-active'
                : 'ops-window-tab'
            }
            onClick={() => setSelectedZone('strawberry')}
          >
            딸기
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={selectedZone === 'grape'}
            className={
              selectedZone === 'grape'
                ? 'ops-window-tab is-active'
                : 'ops-window-tab'
            }
            onClick={() => setSelectedZone('grape')}
          >
            포도
          </button>
        </div>
      </header>

      {!zone ? (
        <p className="ops-empty">
          구역 스냅샷이 없습니다. 시뮬 step 후 새로고침하면 채워집니다.
        </p>
      ) : (
        <>
          <p className="ops-hint">
            {zone.label} · setpoint·관수·병해 규칙을 룸과 분리합니다. Brix는
            추정값이며 당도계 검증이 필요합니다.
          </p>
          {zones ? (
            <ul className="ops-zone-loop-status" aria-label="구역 폐쇄루프 상태">
              <li>
                병해 완화{' '}
                <strong data-on={zones.disease_mitigation_active ? 'true' : 'false'}>
                  {zones.disease_mitigation_active ? '가동' : '대기'}
                </strong>
              </li>
              <li>
                LED/DLI 요구{' '}
                <strong>
                  {Math.round((zones.led_demand_ratio ?? 0) * 100)}%
                </strong>
              </li>
            </ul>
          ) : null}
          <ZoneBody zone={zone} />
          {zones?.last_disease_reason || zones?.last_led_reason ? (
            <p className="ops-zone-reasons">
              {zones.last_irrigation_reason
                ? `관수: ${zones.last_irrigation_reason}`
                : null}
              {zones.last_disease_reason
                ? ` · 병해: ${zones.last_disease_reason}`
                : null}
              {zones.last_led_reason ? ` · 광: ${zones.last_led_reason}` : null}
            </p>
          ) : null}
        </>
      )}
    </section>
  )
}
