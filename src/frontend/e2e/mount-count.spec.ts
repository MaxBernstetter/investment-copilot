import { test, expect } from '@playwright/test'
import { freezeClock, installApiMocks } from './mockApi'
import { waitForCurveLoaded } from './helpers'

test.beforeEach(async ({ page }) => {
  await freezeClock(page)
  await installApiMocks(page, 'online')
})

test('keeps the curve view mounted when switching tabs', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await waitForCurveLoaded(page)

  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()

  const curveTitle = page.getByRole('heading', { level: 1, name: 'Yield curve', includeHidden: true })
  await expect(curveTitle).toHaveCount(1)
  await expect(curveTitle).toBeHidden()
})
