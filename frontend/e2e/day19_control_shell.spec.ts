/**
 * Day 19 Playwright — 관제 셸 핵심 흐름.
 *
 * 검증
 * ----
 * - FarmTwin 브랜드/대시보드 영역
 * - 3D viewport
 * - KPI · 시계열 · 상세 · 이벤트 패널
 * - 차트 메트릭 select 조작
 *
 * DB/WS 실패 시에도 셸은 렌더되어야 한다 (복구 UX).
 */
import { expect, test } from '@playwright/test'

test.describe('FarmTwin control shell', () => {
  test('loads 3D viewport and Day18–19 dashboard regions', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByText('FarmTwin')).toBeVisible()
    await expect(page.getByTestId('farm-3d-viewport')).toBeVisible()
    await expect(page.getByRole('region', { name: '환경 KPI' })).toBeVisible()
    await expect(page.getByTestId('timeseries-chart')).toBeVisible()
    await expect(page.getByRole('region', { name: '센서·설비 상세' })).toBeVisible()
    await expect(page.getByRole('region', { name: '이벤트 타임라인' })).toBeVisible()

    const metric = page.getByTestId('chart-metric-select')
    await metric.selectOption('humidity_pct')
    await expect(metric).toHaveValue('humidity_pct')
  })
})
