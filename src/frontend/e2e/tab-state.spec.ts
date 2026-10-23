import { test, expect } from '@playwright/test'
import { freezeClock, installApiMocks } from './mockApi'
import { waitForCurveLoaded } from './helpers'

// #207: hidden views keep their DOM, state and data (Mantine activity mode, see App.tsx).
test.beforeEach(async ({ page }) => {
  await freezeClock(page)
  await installApiMocks(page, 'online')
})

test('a chosen Time series layout survives a tab round trip, and the hidden view stays mounted once', async ({
  page,
}) => {
  await page.goto('/')
  await waitForCurveLoaded(page)
  await page.getByRole('tab', { name: 'Time series' }).click()
  await page.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
  await expect(page.getByRole('columnheader', { name: 'Valid date' })).toBeVisible()
  // The hidden Curve view stays in the DOM; a DOM locator sees it, role queries skip it.
  await expect(page.locator('h1', { hasText: 'Yield curve' })).toHaveCount(1)

  await page.getByRole('tab', { name: 'Curve' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Yield curve' })).toBeVisible()

  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(page.getByRole('radio', { name: 'Table' })).toBeChecked()
  await expect(page.getByRole('columnheader', { name: 'Valid date' })).toBeVisible()
})

test('returning to the curve view shows its data at once while it revalidates', async ({ page }) => {
  await page.goto('/')
  await waitForCurveLoaded(page)
  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()

  await page.getByRole('tab', { name: 'Curve' }).click()
  await expect(page.getByLabel(/Valid date/)).toHaveValue('2026-10-16')
  await expect(page.getByRole('tabpanel', { name: 'Yield curve' }).locator('.mantine-Skeleton-root')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Add to overlay' })).toBeEnabled()
})
