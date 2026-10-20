import { test, expect, type Locator } from '@playwright/test'
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
  expect(await live.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none')

  await page.keyboard.press('Enter')
  await expect(page.getByLabel(/Known as of/)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByLabel(/Known as of/)).not.toBeVisible()
  await expect(live).toBeFocused()

  await page.keyboard.press(' ')
  await expect(page.getByLabel(/Known as of/)).toBeVisible()
})

test('quality view tab order and flag popover', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await waitForCurveLoaded(page)

  await page.keyboard.press('Tab')
  const qualityTab = page.getByRole('tab', { name: 'Quality' })
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press('ArrowRight')
  }
  await expect(qualityTab).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Data quality' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '2026-10-16' })).toBeVisible()

  // The header controls sit between the tab list and the view, so Tab walks to From first.
  // Hidden panels stay mounted, so the visible fields are found by role. Chromium date inputs
  // take extra Tab stops for their day, month and year parts, so Tab until each control is focused.
  const tabUntilFocused = async (locator: Locator, maxPresses: number) => {
    for (let i = 0; i < maxPresses && !(await locator.evaluate((el) => el === document.activeElement)); i += 1) {
      await page.keyboard.press('Tab')
    }
    await expect(locator).toBeFocused()
  }
  await tabUntilFocused(page.getByRole('textbox', { name: 'From' }), 20)
  await tabUntilFocused(page.getByRole('textbox', { name: 'To' }), 10)
  await tabUntilFocused(page.getByRole('radio', { name: 'All' }), 10)
  const flag = page.getByRole('button', { name: 'Jump · warn, 10Y' })
  await tabUntilFocused(flag, 10)

  await page.keyboard.press('Enter')
  await expect(page.getByRole('link', { name: 'How we check this' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(flag).toBeFocused()
})
