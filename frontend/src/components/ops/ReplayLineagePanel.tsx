/**
 * 재현(replay)·lineage 패널 (6단계 Day 23).
 *
 * - run lineage : seed·외기 모드·환경 모델·규칙 묶음 지문·체크포인트·산출물 수
 * - replay      : 데이터셋(farmtwin.replay.v1) 내보내기/가져오기 → 재생 실행 → 원본과 비교
 * - 이벤트 추적 : 제어 이벤트 → 명령 → 규칙 개정 → 근거 측정 → 외기 → run
 *
 * 재생 run 은 같은 룸을 쓰는 최신 run 이 되므로 관제 화면이 재생 결과를 따라간다.
 * 원본 run 이 RUNNING 이면 백엔드가 먼저 PAUSED 로 돌린다.
 */

import { useRef, useState } from 'react'

import {
  exportReplayDataset,
  fetchEventLineage,
  fetchReplayCompare,
  fetchRunLineage,
  importReplayDataset,
  runReplay,
  type EventLineage,
  type ReplayCompare,
  type ReplayDataset,
  type SimulationRunOut,
} from '../../api/data'
import { fetchFarmEvents } from '../../api/farms'
import { reloadSensorPanels } from '../../realtime/session'
import { formatSimTime, qualityReasonText, QUALITY_LABEL } from '../../realtime/sensorQuality'
import { usePolling } from '../../realtime/usePolling'
import { useRealtimeStore } from '../../store/realtimeStore'

const LINEAGE_POLL_MS = 15000

function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : '—'
}

function downloadJson(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function CompareResult({ compare }: { compare: ReplayCompare }) {
  return (
    <div className="replay-compare">
      <p>
        <span className={`ops-badge tone-${compare.reproduced ? 'ok' : compare.completed ? 'alert' : 'warn'}`}>
          {compare.reproduced ? '재현 성공' : compare.completed ? '재현 불일치' : '진행 중'}
        </span>{' '}
        원본 {shortId(compare.source_run_id)} · 구간 {formatSimTime(compare.checkpoint_time)} ~{' '}
        {formatSimTime(compare.end_simulation_time)} (현재 {formatSimTime(compare.simulation_time_seconds)})
      </p>
      <ul className="lineage-kv">
        <li>
          <span>측정 일치</span>
          <strong>
            {compare.readings_matched} / {compare.readings_expected}
          </strong>
        </li>
        <li>
          <span>값 불일치 · 빠짐 · 초과</span>
          <strong>
            {compare.readings_mismatched} · {compare.readings_missing} · {compare.readings_extra}
          </strong>
        </li>
        <li>
          <span>명령</span>
          <strong>
            {compare.commands_actual} / {compare.commands_expected}{' '}
            {compare.commands_matched ? '일치' : '불일치'}
          </strong>
        </li>
        <li>
          <span>규칙 묶음</span>
          <strong>{compare.rule_set_match ? '같음' : '다름'}</strong>
        </li>
      </ul>
      {compare.reading_mismatches.length > 0 ? (
        <p className="control-hint">
          첫 불일치: {compare.reading_mismatches[0].sensor_code} seq{' '}
          {compare.reading_mismatches[0].source_sequence ?? '—'} @{' '}
          {formatSimTime(compare.reading_mismatches[0].simulation_time)}
        </p>
      ) : null}
    </div>
  )
}

function EventChain({ lineage }: { lineage: EventLineage }) {
  const { event, command, rule, trigger_reading: reading, weather, run } = lineage
  return (
    <ol className="lineage-chain">
      <li>
        <span>이벤트</span>
        <strong>{event.message ?? event.event_type}</strong>
        <em>{formatSimTime(event.simulation_time)}</em>
      </li>
      <li>
        <span>명령</span>
        <strong>
          {command.origin === 'manual' ? '수동' : '규칙'} · {command.actuator_code}{' '}
          {command.desired_mode} {(command.desired_output_ratio * 100).toFixed(0)}% ({command.status})
        </strong>
        <em>{command.reason ?? '—'}</em>
      </li>
      <li>
        <span>규칙</span>
        {rule ? (
          <>
            <strong>
              {rule.name} v{rule.version_at_command ?? '?'}
              {rule.version_at_command != null && rule.version_at_command !== rule.current_version
                ? ` (현재 v${rule.current_version})`
                : ''}
            </strong>
            <em>
              {rule.metric} {rule.comparator} {rule.start_threshold} / 해제 {rule.stop_threshold}
            </em>
          </>
        ) : (
          <strong>운영자 수동 제어</strong>
        )}
      </li>
      <li>
        <span>근거 측정</span>
        {reading ? (
          <>
            <strong>
              {reading.sensor_code} {reading.value?.toFixed(2) ?? '—'} (원시{' '}
              {reading.raw_value?.toFixed(2) ?? '—'}) · {QUALITY_LABEL[reading.quality]}
            </strong>
            <em>
              seq {reading.source_sequence ?? '—'} · {qualityReasonText(reading.quality_reason)} ·{' '}
              {reading.telemetry_schema_version}
            </em>
          </>
        ) : (
          <strong>{command.origin === 'manual' ? '해당 없음' : '측정 없음(dropout)'}</strong>
        )}
      </li>
      <li>
        <span>외기</span>
        {weather ? (
          <>
            <strong>
              {weather.outdoor_temperature_c.toFixed(1)} ℃ · {weather.outdoor_humidity_pct.toFixed(0)} %
            </strong>
            <em>
              {weather.source} #{weather.sequence} @ {formatSimTime(weather.simulation_time)}
            </em>
          </>
        ) : (
          <strong>—</strong>
        )}
      </li>
      <li>
        <span>run</span>
        <strong>
          {run.name} · seed {run.random_seed}
        </strong>
        <em>
          {run.weather_mode} · {run.environment_model_version} · {run.rule_set_version ?? '—'}
        </em>
      </li>
    </ol>
  )
}

export function ReplayLineagePanel() {
  const farmId = useRealtimeStore((s) => s.farmId)
  const runId = useRealtimeStore((s) => s.sensorHealth?.run_id ?? null)
  const fileRef = useRef<HTMLInputElement>(null)

  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [imported, setImported] = useState<SimulationRunOut | null>(null)
  const [compare, setCompare] = useState<ReplayCompare | null>(null)
  const [eventId, setEventId] = useState('')
  const [eventLineage, setEventLineage] = useState<EventLineage | null>(null)

  const { data: lineage, reload } = usePolling(
    runId,
    () => fetchRunLineage(runId ?? ''),
    LINEAGE_POLL_MS,
  )
  const { data: events } = usePolling(
    farmId && runId ? `${farmId}|${runId}` : null,
    () => fetchFarmEvents(farmId ?? '', 30),
    LINEAGE_POLL_MS,
  )

  async function act(label: string, action: () => Promise<void>) {
    setPending(label)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : '요청 실패')
    } finally {
      setPending(null)
    }
  }

  const exportDataset = () =>
    act('export', async () => {
      if (!runId) return
      const dataset = await exportReplayDataset(runId)
      downloadJson(dataset, `farmtwin-replay-${shortId(runId)}.json`)
    })

  const importDataset = (dataset: ReplayDataset) =>
    act('import', async () => {
      if (dataset.format !== 'farmtwin.replay.v1') {
        throw new Error('farmtwin.replay.v1 데이터셋이 아닙니다')
      }
      setImported(await importReplayDataset(dataset))
      setCompare(null)
    })

  const replayCurrent = () =>
    act('import', async () => {
      if (!runId) return
      setImported(await importReplayDataset(await exportReplayDataset(runId)))
      setCompare(null)
    })

  const runImported = () =>
    act('replay', async () => {
      if (!imported) return
      const result = await runReplay(imported.id)
      setCompare(result.compare)
      await reloadSensorPanels()
      reload()
    })

  const showCompare = () =>
    act('compare', async () => {
      if (!runId) return
      setCompare(await fetchReplayCompare(runId))
    })

  const traceEvent = (id: string) => {
    setEventId(id)
    setEventLineage(null)
    if (!id) return
    void act('trace', async () => setEventLineage(await fetchEventLineage(id)))
  }

  async function onFile(file: File | undefined) {
    if (!file) return
    try {
      importDataset(JSON.parse(await file.text()) as ReplayDataset)
    } catch {
      setError('JSON 파일을 읽을 수 없습니다')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const run = lineage?.run
  const isReplay = Boolean(run?.replay_of_run_id)

  return (
    <section className="ops-panel ops-table-panel" aria-label="재현과 lineage">
      <header className="ops-panel-head">
        <h2>재현 · Lineage</h2>
        <span className="ops-sort-tag">
          {run ? `${run.name} · ${run.status}` : 'run 없음'}
        </span>
      </header>

      {!runId || !lineage ? (
        <p className="ops-empty">시뮬레이션 run 이 없어 lineage 를 표시할 수 없습니다.</p>
      ) : (
        <>
          <ul className="lineage-kv">
            <li>
              <span>run</span>
              <strong>{shortId(lineage.run.id)}</strong>
            </li>
            <li>
              <span>seed · 외기</span>
              <strong>
                {lineage.run.random_seed} · {lineage.run.weather_mode}
              </strong>
            </li>
            <li>
              <span>환경 모델</span>
              <strong>{lineage.run.environment_model_version}</strong>
            </li>
            <li>
              <span>규칙 묶음</span>
              <strong>{lineage.run.rule_set_version ?? '—'}</strong>
            </li>
            <li>
              <span>체크포인트</span>
              <strong>
                {lineage.checkpoint_time == null ? '없음' : formatSimTime(lineage.checkpoint_time)}
              </strong>
            </li>
            <li>
              <span>스키마 · 센서 모델</span>
              <strong>
                {lineage.telemetry_schema_versions.join(', ') || '—'} ·{' '}
                {lineage.sensor_model_versions.join(', ') || '—'}
              </strong>
            </li>
            <li>
              <span>측정 · 외기</span>
              <strong>
                {lineage.counts.readings} · {lineage.counts.weather_snapshots}
              </strong>
            </li>
            <li>
              <span>명령 규칙 · 수동 · 차단</span>
              <strong>
                {lineage.counts.rule_commands} · {lineage.counts.manual_commands} ·{' '}
                {lineage.counts.blocked_commands}
              </strong>
            </li>
            <li>
              <span>원본 / 재생본</span>
              <strong>
                {lineage.replay_of ? `원본 ${shortId(lineage.replay_of.id)}` : '원본 run'}
                {lineage.replays.length > 0
                  ? ` · 재생 ${lineage.replays.map((r) => shortId(r.id)).join(', ')}`
                  : ''}
              </strong>
            </li>
          </ul>

          <div className="fault-form">
            <button
              type="button"
              className="control-apply"
              disabled={pending !== null || lineage.checkpoint_time == null}
              onClick={exportDataset}
            >
              {pending === 'export' ? '내보내는 중…' : '데이터셋 내보내기'}
            </button>
            <button
              type="button"
              className="control-apply"
              disabled={pending !== null}
              onClick={() => fileRef.current?.click()}
            >
              데이터셋 가져오기
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              hidden
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
            <button
              type="button"
              className="control-apply"
              disabled={pending !== null || lineage.checkpoint_time == null}
              onClick={replayCurrent}
            >
              {pending === 'import' ? '준비 중…' : '현재 run 재현 준비'}
            </button>
            {isReplay ? (
              <button
                type="button"
                className="control-off"
                disabled={pending !== null}
                onClick={showCompare}
              >
                원본과 비교
              </button>
            ) : null}
            <p className="control-hint">
              재생 run 은 같은 재배실을 사용합니다. 실행하면 진행 중인 원본 run 은 일시정지됩니다.
            </p>
          </div>

          {imported ? (
            <div className="fault-form">
              <p className="control-hint">
                재생 run {shortId(imported.id)} 준비됨 · 시작{' '}
                {formatSimTime(imported.simulation_time_seconds)}
              </p>
              <button
                type="button"
                className="control-apply"
                disabled={pending !== null}
                onClick={runImported}
              >
                {pending === 'replay' ? '재생 중…' : '재생 실행'}
              </button>
            </div>
          ) : null}

          {compare ? <CompareResult compare={compare} /> : null}

          <div className="fault-form">
            <label>
              이벤트 추적
              <select
                value={eventId}
                disabled={pending === 'trace'}
                onChange={(e) => traceEvent(e.target.value)}
              >
                <option value="">제어 이벤트 선택</option>
                {(events ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {formatSimTime(item.simulation_time)} · {item.message ?? item.event_type}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {eventLineage ? <EventChain lineage={eventLineage} /> : null}
        </>
      )}
      {error ? <p className="error">{error}</p> : null}
    </section>
  )
}
