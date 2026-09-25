import type {
  ActuatorSummary,
  FarmStateSnapshot,
  SensorSummary,
} from '../api/farms'

type Props = {
  sensors: SensorSummary[]
  actuators: ActuatorSummary[]
  state: FarmStateSnapshot | null
  selectedSensorId: string | null
  selectedActuatorId: string | null
  onSelectSensor: (id: string | null) => void
  onSelectActuator: (id: string | null) => void
}

/** PPFD=측정계, CO₂=입구 센서, 배지=영양 체크 */
function sensorKindLabel(sensorType: string): string {
  switch (sensorType) {
    case 'ppfd':
      return '측정계'
    case 'co2':
      return '입구'
    case 'substrate_moisture':
      return '영양'
    case 'temperature':
    case 'humidity':
      return '온습도'
    default:
      return '계측'
  }
}

function sensorLiveReading(
  sensorType: string,
  state: FarmStateSnapshot | null,
): string | null {
  if (!state) return null
  switch (sensorType) {
    case 'temperature':
      return `${state.temperature_c.toFixed(1)} °C`
    case 'humidity':
      return `${state.humidity_pct.toFixed(1)} %`
    case 'co2':
      return `${state.co2_ppm.toFixed(0)} ppm`
    case 'substrate_moisture':
      return `${state.substrate_moisture_pct.toFixed(1)} %`
    case 'ppfd':
      return `${state.ppfd_umol.toFixed(0)} µmol`
    default:
      return null
  }
}

function actuatorStatusLabel(item: ActuatorSummary): string {
  const pct = Math.round(item.output_ratio * 100)
  if (pct <= 0) return `${item.mode} · OFF`
  return `${item.mode} · ON ${pct}%`
}

export function DetailPanel({
  sensors,
  actuators,
  state,
  selectedSensorId,
  selectedActuatorId,
  onSelectSensor,
  onSelectActuator,
}: Props) {
  const sensor = sensors.find((item) => item.id === selectedSensorId) ?? null
  const actuator =
    actuators.find((item) => item.id === selectedActuatorId) ?? null
  const live = sensor ? sensorLiveReading(sensor.sensor_type, state) : null

  return (
    <section className="detail-panel" aria-label="센서·설비 상세">
      <h2>상세</h2>

      <div className="detail-columns">
        <div>
          <h3>계측</h3>
          <ul className="entity-list">
            {sensors.map((item) => {
              const reading = sensorLiveReading(item.sensor_type, state)
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={
                      item.id === selectedSensorId ? 'is-selected' : undefined
                    }
                    onClick={() =>
                      onSelectSensor(
                        item.id === selectedSensorId ? null : item.id,
                      )
                    }
                  >
                    <span>
                      {item.code}
                      <span className="sensor-kind">
                        {sensorKindLabel(item.sensor_type)}
                      </span>
                    </span>
                    <em>{reading ?? item.sensor_type}</em>
                  </button>
                </li>
              )
            })}
          </ul>
          {sensor ? (
            <dl className="detail-dl">
              <div>
                <dt>이름</dt>
                <dd>{sensor.name}</dd>
              </div>
              <div>
                <dt>종류</dt>
                <dd>{sensorKindLabel(sensor.sensor_type)}</dd>
              </div>
              <div>
                <dt>현재값</dt>
                <dd>{live ?? '—'}</dd>
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
            <p className="panel-empty">계측 포인트를 선택하세요.</p>
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
                  <em data-on={item.output_ratio > 0 ? 'true' : 'false'}>
                    {actuatorStatusLabel(item)}
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
                <dt>상태</dt>
                <dd>
                  {actuator.output_ratio > 0
                    ? `ON · ${(actuator.output_ratio * 100).toFixed(0)}%`
                    : 'OFF'}
                </dd>
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
