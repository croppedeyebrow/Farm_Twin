/**
 * 참값 시계열 차트 (5단계 Day 18~19).
 *
 * ECharts line. x = simulation_time.
 * Day 19: chartMetric 은 store — 3D 센서 클릭과 동기화.
 * 탭 hidden 이면 setOption 생략 (설계 7절).
 */

import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'

import type { KpiSample } from '../realtime/history'
import type { SensorMetricKey } from '../scene/statusColors'
import { useRealtimeStore } from '../store/realtimeStore'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const SERIES: Array<{ key: SensorMetricKey; name: string; color: string }> = [
  { key: 'temperature_c', name: '온도 °C', color: '#0f3d2e' },
  { key: 'humidity_pct', name: '습도 %', color: '#2a6f97' },
  { key: 'co2_ppm', name: 'CO₂ ppm', color: '#6b4f3a' },
  { key: 'substrate_moisture_pct', name: '배지 %', color: '#3d5a40' },
  { key: 'ppfd_umol', name: 'PPFD', color: '#b08900' },
]

type Props = {
  history: KpiSample[]
}

export function TimeSeriesChart({ history }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.EChartsType | null>(null)
  const metric = useRealtimeStore((s) => s.chartMetric)
  const setChartMetric = useRealtimeStore((s) => s.setChartMetric)

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

    const apply = () => {
      if (document.hidden) return
      const seriesMeta = SERIES.find((item) => item.key === metric) ?? SERIES[0]
      chart.setOption({
        animation: false,
        grid: { left: 44, right: 16, top: 28, bottom: 28 },
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          name: 'sim t',
          data: history.map((sample) => sample.simulation_time.toFixed(0)),
          axisLabel: { color: '#4a554e', fontSize: 10 },
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLabel: { color: '#4a554e', fontSize: 10 },
          splitLine: { lineStyle: { color: '#d7e0d9' } },
        },
        series: [
          {
            type: 'line',
            name: seriesMeta.name,
            showSymbol: history.length < 40,
            data: history.map((sample) => sample[metric]),
            lineStyle: { width: 2, color: seriesMeta.color },
            itemStyle: { color: seriesMeta.color },
          },
        ],
      })
    }

    apply()
    const onVisibility = () => {
      if (!document.hidden) apply()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [history, metric])

  return (
    <section className="chart-panel" aria-label="시계열 차트" data-testid="timeseries-chart">
      <div className="panel-title-row">
        <h2>시계열</h2>
        <select
          className="metric-select"
          value={metric}
          onChange={(event) =>
            setChartMetric(event.target.value as SensorMetricKey)
          }
          aria-label="차트 메트릭"
          data-testid="chart-metric-select"
        >
          {SERIES.map((item) => (
            <option key={item.key} value={item.key}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      <div ref={hostRef} className="chart-host" />
      {history.length === 0 ? (
        <p className="panel-empty">snapshot/WS 참값이 쌓이면 그래프가 채워집니다.</p>
      ) : null}
    </section>
  )
}
