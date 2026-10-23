import { test, expect } from '@playwright/test'
import { freezeClock, installApiMocks } from './mockApi'

// Regression guard for #209: the colour-scheme tooltip must close after the pointer leaves,
// also on the loading screen under CPU throttling.
test.beforeEach(async ({ page }) => {
  await freezeClock(page)
  await installApiMocks(page, 'loading')
})

test('colour-scheme tooltip closes after the pointer leaves (loading screen, throttled)', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  await page.goto('/')
  const toggle = page.getByRole('button', { name: 'Toggle colour scheme' })
  await expect(toggle).toBeVisible()

  for (let i = 0; i < 20; i++) {
    await toggle.click()
    await page.mouse.move(0, 0)
    await page.waitForTimeout(1000)
    await expect(page.getByRole('tooltip')).toBeHidden()
  }
})
