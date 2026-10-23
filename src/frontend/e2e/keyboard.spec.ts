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
  // The select shows focus with its border colour (Mantine Input), not an outline.
  const select = page.getByRole('combobox', { name: 'Curve' })
  const idleBorder = await select.evaluate((el) => getComputedStyle(el).borderTopColor)
  await page.keyboard.press('Tab')
  await expect(select).toBeFocused()
  await expect.poll(() => select.evaluate((el) => getComputedStyle(el).borderTopColor)).not.toBe(idleBorder)

  await page.keyboard.press('Enter')
  await expect(page.getByRole('listbox')).toBeVisible()
  // ArrowDown can be lost while the list opens, or the highlight can return to the selected
  // option; press again until the all-issuer option carries the keyboard highlight, then pick it.
  const allIssuer = page.getByRole('option', { name: 'ECB euro area all-issuer spot' })
  await expect(async () => {
    if (!(await allIssuer.getAttribute('data-combobox-selected'))) await page.keyboard.press('ArrowDown')
    await expect(allIssuer).toHaveAttribute('data-combobox-selected', { timeout: 1000 })
  }).toPass()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('listbox')).not.toBeVisible()
  await expect(page).toHaveURL(/curve=ecb-all-spot/)
  await expect(select).toHaveValue('ECB euro area all-issuer spot')

  await page.keyboard.press('Enter')
  await expect(page.getByRole('listbox')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).not.toBeVisible()
  await expect(select).toBeFocused()
  await page.keyboard.press('Tab')
  const live = page.getByRole('button', { name: 'Live' })
  await expect(live).toBeFocused()
  expect(await live.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none')

  await page.keyboard.press('Enter')
  await expect(page.getByLabel(/Known as of/)).toBeVisible()
  // The popover traps focus once it opens; Escape pressed before that is lost.
  await expect(page.getByLabel(/Known as of/)).toBeFocused()
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

test('curve flag badge opens its explanation from the keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/?curve=ecb-aaa-spot-sim&as_of=2026-10-19T18%3A49%3A25Z')
  await waitForCurveLoaded(page)
  // Passed cells hold nothing focusable: Tab goes from one History button to the next.
  await page.getByRole('button', { name: 'History 3M' }).focus()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'History 6M' })).toBeFocused()
  // In the 10Y row the flag badges come before History.
  await page.getByRole('button', { name: 'History 7Y' }).focus()
  await page.keyboard.press('Tab')
  const flag = page.getByRole('button', { name: 'Range · warn, 10Y' })
  await expect(flag).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Jump · warn, 10Y' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'History 10Y' })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await page.keyboard.press('Shift+Tab')
  await expect(flag).toBeFocused()
  await page.keyboard.press('Enter')
  const link = page.getByRole('link', { name: 'How we check this' })
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(link).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(link).toBeHidden()
  await expect(flag).toBeFocused()
})

test('key figure explanations open on focus and close with Escape', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  await waitForCurveLoaded(page)

  const add = page.getByRole('button', { name: 'Add to overlay' })
  await add.focus()
  await expect(add).toBeFocused()
  // Each tooltip is found by its own text: the previous one leaves the DOM after its close transition.
  const explanations: [string, string][] = [
    ['10Y yield', 'Spot rate for a 10-year maturity on this valid date, in percent.'],
    ['2Y–10Y spread', '10Y yield minus 2Y yield, in basis points. Also called the slope. Below zero the curve is inverted.'],
    [
      '3M–10Y spread',
      '10Y yield minus 3M yield, in basis points. Compares the long end with the money-market end of the curve.',
    ],
    [
      '2Y–5Y–10Y curvature',
      '2 × 5Y \u2212 2Y \u2212 10Y, in basis points. Positive means a humped belly: 5Y is above the average of 2Y and 10Y. Negative means a sagging belly.',
    ],
  ]
  for (const [label, help] of explanations) {
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: `About ${label}` })).toBeFocused()
    await expect(page.getByRole('tooltip').filter({ hasText: help })).toBeVisible()
  }

  await page.keyboard.press('Escape')
  await expect(page.getByRole('tooltip')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'About 2Y–5Y–10Y curvature' })).toBeFocused()
})
