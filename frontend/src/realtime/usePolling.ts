/**
 * REST 주기 조회 훅 (6단계 Day 23 — 이력·품질 리포트·lineage 패널).
 *
 * key 가 바뀌면 즉시 다시 불러오고, 이후 intervalMs 마다 갱신한다.
 * key 가 null 이면 조회하지 않는다 (farm/run 이 아직 없을 때).
 * 응답이 늦게 도착해도 key 가 바뀐 뒤라면 버린다.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export type PollingState<T> = {
  data: T | null
  error: string | null
  reload: () => void
}

export function usePolling<T>(
  key: string | null,
  load: () => Promise<T>,
  intervalMs: number,
): PollingState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const loadRef = useRef(load)

  useEffect(() => {
    loadRef.current = load
  })

  useEffect(() => {
    if (key === null) return
    let cancelled = false
    const run = () => {
      loadRef
        .current()
        .then((value) => {
          if (cancelled) return
          setData(value)
          setError(null)
        })
        .catch((err: unknown) => {
          if (cancelled) return
          setError(err instanceof Error ? err.message : '조회 실패')
        })
    }
    run()
    const timer = setInterval(run, intervalMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [key, intervalMs, tick])

  const reload = useCallback(() => setTick((value) => value + 1), [])
  return { data: key === null ? null : data, error, reload }
}
