import { test, expect, type Page } from '@playwright/test'
import {
  assertNoHorizontalScroll,
  runAxe,
  screenshotName,
  setColorScheme,
  VIEWPORTS,
  waitForCurveLoaded,
} from './helpers'
import { freezeClock, installApiMocks } from './mockApi'

const AXE_VIEWPORT = { width: 1440, height: 900 }

async function captureSnapshots(
  page: Page,
  id: string,
  schemes: ('light' | 'dark')[],
) {
  for (const { width, height } of VIEWPORTS) {
    for (const scheme of schemes) {
      await page.setViewportSize({ width, height })
      await setColorScheme(page, scheme)
      if (width === 1280) {
        await assertNoHorizontalScroll(page)
      }
      await expect(page).toHaveScreenshot(screenshotName(id, width, height, scheme), { fullPage: true })
    }
  }
}

async function assertAxeAt(page: Page, schemes: ('light' | 'dark')[]) {
  await page.setViewportSize(AXE_VIEWPORT)
  for (const scheme of schemes) {
    await setColorScheme(page, scheme)
    await runAxe(page)
  }
}

test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(() => {
    window.matchMedia = (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })
  })
  await freezeClock(page)
  await installApiMocks(page, 'online')
})

test.describe('visual snapshots §7', () => {
  test('S1 curve, real, live', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S1', ['light', 'dark'])
  })

  test('S2 curve, simulated, as-of spike', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim&as_of=2026-10-19T18%3A49%3A25Z')
    await waitForCurveLoaded(page)
    await expect(page.getByRole('status')).toContainText('As of 19 Oct 2026, 18:49:25 UTC')
    await expect(page.getByRole('note')).toBeVisible()
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S2', ['light'])
  })

  test('S3 curve with two overlays', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByLabel(/Valid date/).fill('2026-10-15')
    await page.getByRole('button', { name: 'Add to overlay' }).click()
    await page.getByLabel(/Valid date/).fill('2026-10-14')
    await page.getByRole('button', { name: 'Add to overlay' }).click()
    await expect(page.getByLabel('Overlaid valid dates')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S3', ['light', 'dark'])
  })

  test('S4 history drawer 10Y simulated', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim')
    await waitForCurveLoaded(page)
    await assertAxeAt(page, ['light'])
    await page.getByRole('button', { name: 'History 10Y' }).click()
    await expect(page.getByRole('heading', { name: 'History of 10Y on 2026-10-16' })).toBeVisible()
    await captureSnapshots(page, 'S4', ['light'])
  })

  test('S5 time series chart', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    await expect(page.locator('.mantine-Skeleton-root')).toHaveCount(0)
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S5', ['light'])
  })

  test('S5t time series table', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    await page.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
    await expect(page.getByRole('columnheader', { name: 'Valid date' })).toBeVisible()
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S5t', ['light'])
  })

  test('S6 changes with three rows', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Changes' }).click()
    await page.getByLabel('Compare from (known as of)').fill('2026-10-17T08:00')
    await expect(page.getByRole('cell', { name: 'correction' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S6', ['light', 'dark'])
  })

  test('S7 changes empty state', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Changes' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Pick a starting point' })).toBeVisible()
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S7', ['light'])
  })

  test('S8 offline', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'offline')
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('Backend offline')
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S8', ['light'])
  })

  test('S9 loading', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'loading')
    await page.goto('/')
    await expect(page.getByText('Loading…')).toBeVisible()
    await page.setViewportSize(AXE_VIEWPORT)
    await runAxe(page)
    for (const { width, height } of VIEWPORTS) {
      await page.setViewportSize({ width, height })
      if (width === 1280) await assertNoHorizontalScroll(page)
      await expect(page).toHaveScreenshot(screenshotName('S9', width, height, 'light'), { fullPage: true })
    }
  })

  test('S10 no data 404', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'not-found')
    await page.goto('/')
    await expect(page.getByText('No data known for this date.')).toBeVisible()
    await assertAxeAt(page, ['light'])
    await captureSnapshots(page, 'S10', ['light'])
  })
})
