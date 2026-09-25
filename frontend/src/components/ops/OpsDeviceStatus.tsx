import type { ActuatorSummary, FarmStateSnapshot } from '../../api/farms'
import { actuatorRunLabel, sensorRowStatus } from './opsRules'

type Props = {
  state: FarmStateSnapshot | null
  actuators: ActuatorSummary[]
  roomName?: string
}

type Row = {
  id: string
  label: string
  status: string
  tone: string
}

export function OpsDeviceStatus({
  state,
  actuators,
  roomName = '재배실 A',
}: Props) {
  const temp = sensorRowStatus('temp', state)
  const hum = sensorRowStatus('humidity', state)
  const soil = sensorRowStatus('soil', state)
  const fan = actuatorRunLabel(actuators, 'ventilation_fan')
  const cool = actuatorRunLabel(actuators, 'hvac')
  const irrig = actuatorRunLabel(actuators, 'irrigation_pump')

  const rows: Row[] = [
    { id: 'temp', label: 'TEMP-01 / 온도', status: temp.label, tone: temp.tone },
    {
      id: 'hum',
      label: 'HUM-01 / 상대습도',
      status: hum.label,
      tone: hum.tone,
    },
    {
      id: 'soil',
      label: 'SOIL-01 / 토양수분',
      status: soil.label,
      tone: soil.tone,
    },
    { id: 'fan', label: '환기팬', status: fan.label, tone: fan.tone },
    { id: 'cool', label: '냉방', status: cool.label, tone: cool.tone },
    { id: 'humid', label: '가습기', status: '대기', tone: 'idle' },
    {
      id: 'irrig',
      label: '관수 펌프',
      status: irrig.label,
      tone: irrig.tone,
    },
  ]

  return (
    <section className="ops-panel ops-devices" aria-label="센서 · 설비 상태">
      <header className="ops-panel-head">
        <h2>센서 · 설비 상태</h2>
        <span className="ops-room-tag">{roomName}</span>
      </header>
      <ul className="ops-device-list">
        {rows.map((row) => (
          <li key={row.id}>
            <span>{row.label}</span>
            <strong className={`tone-${row.tone}`}>{row.status}</strong>
          </li>
        ))}
      </ul>
    </section>
  )
}
