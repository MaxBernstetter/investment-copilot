import { test, expect, type Page } from '@playwright/test'
import {
  assertNoHorizontalScroll,
  runAxe,
  screenshotName,
  settleAnimations,
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
  fullPage = true,
) {
  for (const { width, height } of VIEWPORTS) {
    for (const scheme of schemes) {
      await page.setViewportSize({ width, height })
      await setColorScheme(page, scheme)
      if (width === 1280) {
        await assertNoHorizontalScroll(page)
      }
      await page.mouse.move(0, 0)
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
      await expect(page).toHaveScreenshot(screenshotName(id, width, height, scheme), { fullPage })
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

/** Opens the Quality tab on the default curve; the fixture days are not awaited here. */
async function openQualityTab(page: Page) {
  await page.goto('/')
  await waitForCurveLoaded(page)
  await page.getByRole('tab', { name: 'Quality' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Data quality' })).toBeVisible()
}

async function openQuality(page: Page) {
  await openQualityTab(page)
  await expect(page.getByRole('cell', { name: '2026-10-16' })).toBeVisible()
}

/** Overrides the quality endpoint for one test; registered after beforeEach, so it wins. */
async function routeQuality(page: Page, status: number, body: unknown) {
  await page.route('**/v1/curves/*/quality**', (route) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }),
  )
}

const QUALITY_META = { as_of: '2026-10-19T12:00:00Z', source_attribution: 'Source: ECB statistics' }

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
    await assertAxeAt(page, ['light', 'dark'])
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
    const drawerHeading = page.getByRole('heading', { name: 'History of 10Y on 2026-10-16' })
    for (const scheme of ['light', 'dark'] as const) {
      await page.setViewportSize(AXE_VIEWPORT)
      await setColorScheme(page, scheme)
      await settleAnimations(page)
      await page.getByRole('button', { name: 'History 10Y' }).click()
      await expect(drawerHeading).toBeVisible()
      await settleAnimations(page)
      await runAxe(page)
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toBeHidden()
    }
    await setColorScheme(page, 'light')
    await page.getByRole('button', { name: 'History 10Y' }).click()
    await expect(drawerHeading).toBeVisible()
    await captureSnapshots(page, 'S4', ['light'], false)
  })

  test('S5 time series chart', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    // Inactive views stay in the DOM with their own skeletons, so count only this panel's.
    await expect(page.getByRole('tabpanel', { name: 'Time series' }).locator('.mantine-Skeleton-root')).toHaveCount(0)
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S5', ['light'])
  })

  test('S5t time series table', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    await page.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
    await expect(page.getByRole('columnheader', { name: 'Valid date' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
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
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S7', ['light'])
  })

  test('S8 offline', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'offline')
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('Backend offline')
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S8', ['light'])
  })

  test('S9 loading', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'loading')
    await page.goto('/')
    await expect(page.getByText('Loading…')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S9', ['light'])
  })

  test('S10 no data 404', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'not-found')
    await page.goto('/')
    await expect(page.getByText('No data known for this date.')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S10', ['light'])
  })

  test('S11 data quality view', async ({ page }) => {
    await openQuality(page)
    await assertAxeAt(page, ['light', 'dark'])
    await captureSnapshots(page, 'S11', ['light', 'dark'])
  })

  test('S12 quality flag popover', async ({ page }) => {
    await openQuality(page)
    const flag = page.getByRole('button', { name: 'Jump · warn, 10Y' })
    const link = page.getByRole('link', { name: 'How we check this' })
    for (const { width, height } of VIEWPORTS) {
      for (const scheme of ['light', 'dark'] as const) {
        await page.setViewportSize({ width, height })
        await setColorScheme(page, scheme)
        await flag.focus()
        await page.keyboard.press('Enter')
        await expect(link).toBeFocused()
        await settleAnimations(page)
        await page.mouse.move(0, 0)
        if (width === AXE_VIEWPORT.width) {
          await runAxe(page)
        }
        await expect(link).toBeVisible()
        await expect(page).toHaveScreenshot(screenshotName('S12', width, height, scheme))
        await page.keyboard.press('Escape')
        await expect(link).toBeHidden()
      }
    }
  })

  test('S13 quality no business days', async ({ page }) => {
    await routeQuality(page, 200, {
      data: { curve_id: 'ecb-aaa-spot', valid_from: '2026-09-19', valid_to: '2026-10-19', days: [] },
      meta: QUALITY_META,
    })
    await openQualityTab(page)
    await expect(page.getByText('No business days in this range')).toBeVisible()
    await captureSnapshots(page, 'S13', ['light'])
  })

  test('S14 quality loading', async ({ page }) => {
    await page.route('**/v1/curves/*/quality**', () => {})
    await openQualityTab(page)
    const panel = page.getByRole('tabpanel', { name: 'Quality' })
    await expect(panel.getByText('Loading…')).toBeAttached()
    await expect(panel.locator('.mantine-Skeleton-root')).toHaveCount(5)
    await captureSnapshots(page, 'S14', ['light'])
  })

  test('S15 quality backend offline', async ({ page }) => {
    await routeQuality(page, 503, { detail: 'The quality service is not reachable; try again later.' })
    await openQualityTab(page)
    await expect(page.getByRole('alert')).toContainText('Backend offline')
    await captureSnapshots(page, 'S15', ['light'])
  })
})
