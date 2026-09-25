/**
 * Day 19+ Playwright — OPERATIONS 셸 · 멀티 페이지.
 */
import { expect, test } from '@playwright/test'

test.describe('FarmTwin multi-page shell', () => {
  test('환경 관제 dashboard', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByText('FarmTwin').first()).toBeVisible()
    await expect(page.getByRole('heading', { name: '환경 관제' })).toBeVisible()
    await expect(page.getByText('FARMTWIN / OPERATIONS')).toBeVisible()
    await expect(page.getByRole('region', { name: '실시간 센서 카드' })).toBeVisible()
    await expect(page.getByRole('region', { name: '센서 · 설비 상태' })).toBeVisible()
    await expect(page.getByRole('region', { name: '운전 기준' })).toBeVisible()
    await expect(page.getByRole('link', { name: '설비 제어' })).toBeVisible()
  })

  test('센서 기록 page', async ({ page }) => {
    await page.goto('/records')

    await expect(page.getByRole('heading', { name: '센서 기록' }).first()).toBeVisible()
    await expect(page.getByRole('region', { name: '측정 이력' })).toBeVisible()
  })

  test('설비 제어 page', async ({ page }) => {
    await page.goto('/control')

    await expect(page.getByRole('heading', { name: '설비 제어' })).toBeVisible()
    await expect(page.getByRole('region', { name: '자동 운전 기준' })).toBeVisible()
    await expect(page.getByRole('button', { name: '운전 기준 적용' })).toBeVisible()
    await expect(page.getByRole('region', { name: '이벤트 이력' })).toBeVisible()
  })

  test('twin page shows 3D viewport and control', async ({ page }) => {
    await page.goto('/twin')

    await expect(page.getByTestId('farm-3d-viewport')).toBeVisible()
    await expect(page.getByRole('heading', { name: '장치 제어' })).toBeVisible()
    await expect(page.getByRole('region', { name: '환경 제어' })).toBeVisible()
  })

  test('crops page lists lines', async ({ page }) => {
    await page.goto('/crops')

    await expect(page.getByRole('heading', { name: '작물 생육' })).toBeVisible()
    await expect(page.getByRole('region', { name: '재배 라인' })).toBeVisible()
    await expect(page.getByText('딸기 라인 1')).toBeVisible()
  })
})
