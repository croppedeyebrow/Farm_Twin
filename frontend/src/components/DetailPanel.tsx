/**
 * 센서·액추에이터 상세 패널 (5단계 Day 18).
 *
 * 목록에서 선택하면 store 에 id 를 남긴다 (Day 19 3D 연동용).
 * 값은 snapshot(+향후 WS) 기준 — 참값 KPI 와 혼동하지 않는다.
 */

import type { ActuatorSummary, SensorSummary } from '../api/farms'

type Props = {
  sensors: SensorSummary[]
  actuators: ActuatorSummary[]
  selectedSensorId: string | null
  selectedActuatorId: string | null
  onSelectSensor: (id: string | null) => void
  onSelectActuator: (id: string | null) => void
}

export function DetailPanel({
  sensors,
  actuators,
  selectedSensorId,
  selectedActuatorId,
  onSelectSensor,
  onSelectActuator,
}: Props) {
  const sensor = sensors.find((item) => item.id === selectedSensorId) ?? null
  const actuator =
    actuators.find((item) => item.id === selectedActuatorId) ?? null

  return (
    <section className="detail-panel" aria-label="센서·설비 상세">
      <h2>상세</h2>

      <div className="detail-columns">
        <div>
          <h3>센서</h3>
          <ul className="entity-list">
            {sensors.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={item.id === selectedSensorId ? 'is-selected' : undefined}
                  onClick={() =>
                    onSelectSensor(item.id === selectedSensorId ? null : item.id)
                  }
                >
                  <span>{item.code}</span>
                  <em>{item.sensor_type}</em>
                </button>
              </li>
            ))}
          </ul>
          {sensor ? (
            <dl className="detail-dl">
              <div>
                <dt>이름</dt>
                <dd>{sensor.name}</dd>
              </div>
              <div>
                <dt>단위</dt>
                <dd>{sensor.unit}</dd>
              </div>
              <div>
                <dt>모델</dt>
                <dd>{sensor.model_version}</dd>
              </div>
            </dl>
          ) : (
            <p className="panel-empty">센서를 선택하세요.</p>
          )}
        </div>

        <div>
          <h3>액추에이터</h3>
          <ul className="entity-list">
            {actuators.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={
                    item.id === selectedActuatorId ? 'is-selected' : undefined
                  }
                  onClick={() =>
                    onSelectActuator(
                      item.id === selectedActuatorId ? null : item.id,
                    )
                  }
                >
                  <span>{item.code}</span>
                  <em>
                    {item.mode} · {(item.output_ratio * 100).toFixed(0)}%
                  </em>
                </button>
              </li>
            ))}
          </ul>
          {actuator ? (
            <dl className="detail-dl">
              <div>
                <dt>이름</dt>
                <dd>{actuator.name}</dd>
              </div>
              <div>
                <dt>타입</dt>
                <dd>{actuator.actuator_type}</dd>
              </div>
              <div>
                <dt>mode</dt>
                <dd>{actuator.mode}</dd>
              </div>
              <div>
                <dt>output</dt>
                <dd>{(actuator.output_ratio * 100).toFixed(0)}%</dd>
              </div>
            </dl>
          ) : (
            <p className="panel-empty">설비를 선택하세요.</p>
          )}
        </div>
      </div>
    </section>
  )
}
