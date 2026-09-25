/**
 * 환경 변화 추이 — 실내 온도/습도/토양수분 멀티라인
 */

import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useMemo, useRef } from 'react'

import type { KpiSample } from '../../realtime/history'
import type { ChartWindow } from '../../store/opsUiStore'

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

type Props = {
  history: KpiSample[]
  chartWindow: ChartWindow
  onWindowChange: (w: ChartWindow) => void
}

const WINDOW_OPTS: { id: ChartWindow; label: string }[] = [
  { id: '1h', label: '1시간' },
  { id: '6h', label: '6시간' },
  { id: '24h', label: '24시간' },
]

function windowSeconds(w: ChartWindow): number {
  if (w === '6h') return 6 * 3600
  if (w === '24h') return 24 * 3600
  return 3600
}

export function OpsTrendChart({
  history,
  chartWindow,
  onWindowChange,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.EChartsType | null>(null)

  const sliced = useMemo(() => {
    if (history.length === 0) return []
    const last = history[history.length - 1].simulation_time
    const minT = last - windowSeconds(chartWindow)
    return history.filter((s) => s.simulation_time >= minT)
  }, [history, chartWindow])

  useEffect(() => {
    if (!hostRef.current) return
    const chart = echarts.init(hostRef.current, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const lastT = sliced.length
      ? sliced[sliced.length - 1].simulation_time
      : 0
    const span = windowSeconds(chartWindow)

    const xs = sliced.map((s) => {
      const agoMin = Math.round((lastT - s.simulation_time) / 60)
      return `-${agoMin}분`
    })

    chart.setOption(
      {
        backgroundColor: 'transparent',
        grid: { left: 36, right: 16, top: 36, bottom: 28 },
        legend: {
          top: 0,
          left: 0,
          itemWidth: 8,
          itemHeight: 8,
          textStyle: { color: '#9aa3ae', fontSize: 11 },
          data: [
            { name: '실내 온도 ℃', itemStyle: { color: '#3dd68c' } },
            { name: '실내 습도 %', itemStyle: { color: '#5b8def' } },
            { name: '토양수분 %', itemStyle: { color: '#e8a24a' } },
          ],
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: '#1a2030',
          borderColor: '#2a3344',
          textStyle: { color: '#e8ecf1', fontSize: 12 },
        },
        xAxis: {
          type: 'category',
          data: xs.length ? xs : ['-60분', '-45분', '-30분', '-15분', '-0분'],
          boundaryGap: false,
          axisLine: { lineStyle: { color: '#2a3344' } },
          axisLabel: { color: '#7a8494', fontSize: 10 },
          axisTick: { show: false },
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          splitNumber: 4,
          axisLabel: { color: '#7a8494', fontSize: 10 },
          splitLine: { lineStyle: { color: '#243044', type: 'dashed' } },
          axisLine: { show: false },
        },
        series: [
          {
            name: '실내 온도 ℃',
            type: 'line',
            smooth: true,
            showSymbol: false,
            data: sliced.map((s) => Number(s.temperature_c.toFixed(1))),
            lineStyle: { width: 2, color: '#3dd68c' },
            itemStyle: { color: '#3dd68c' },
          },
          {
            name: '실내 습도 %',
            type: 'line',
            smooth: true,
            showSymbol: false,
            data: sliced.map((s) => Number(s.humidity_pct.toFixed(1))),
            lineStyle: { width: 2, color: '#5b8def' },
            itemStyle: { color: '#5b8def' },
          },
          {
            name: '토양수분 %',
            type: 'line',
            smooth: true,
            showSymbol: false,
            data: sliced.map((s) =>
              Number(s.substrate_moisture_pct.toFixed(1)),
            ),
            lineStyle: { width: 2, color: '#e8a24a' },
            itemStyle: { color: '#e8a24a' },
          },
        ],
      },
      { notMerge: true },
    )

    void span
  }, [sliced, chartWindow])

  return (
    <section className="ops-panel ops-trend" aria-label="환경 변화 추이">
      <header className="ops-panel-head">
        <h2>환경 변화 추이</h2>
        <div className="ops-window-tabs" role="tablist" aria-label="추이 구간">
          {WINDOW_OPTS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              role="tab"
              aria-selected={chartWindow === opt.id}
              className={
                chartWindow === opt.id
                  ? 'ops-window-tab is-active'
                  : 'ops-window-tab'
              }
              onClick={() => onWindowChange(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </header>
      <div ref={hostRef} className="ops-trend-chart" data-testid="ops-trend-chart" />
    </section>
  )
}
