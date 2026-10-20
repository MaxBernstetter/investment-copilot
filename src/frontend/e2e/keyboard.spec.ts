import { test, expect } from '@playwright/test'
import { freezeClock, installApiMocks } from './mockApi'
import { waitForCurveLoaded } from './helpers'

test.beforeEach(async ({ page }) => {
  await freezeClock(page)
  await installApiMocks(page, 'online')
})

test('header tab order and as-of popover keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await waitForCurveLoaded(page)

  await page.keyboard.press('Tab')
  await expect(page.getByRole('tab', { name: 'Curve' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('radio', { name: 'Real' })).toBeFocused()
  await page.keyboard.press('Tab')
  const live = page.getByRole('button', { name: 'Live' })
  await expect(live).toBeFocused()

  await page.keyboard.press('Enter')
  await expect(page.getByLabel(/Known as of/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByLabel(/Known as of/)).not.toBeVisible()
  await expect(live).toBeFocused()

  await page.keyboard.press(' ')
  await expect(page.getByLabel(/Known as of/)).toBeVisible()
})
