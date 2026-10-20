import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'

export const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
] as const

export async function runAxe(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(results.violations).toEqual([])
}

export async function assertNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.innerWidth)
}

export async function setColorScheme(page: Page, scheme: 'light' | 'dark') {
  const current = await page.evaluate(() =>
    document.documentElement.getAttribute('data-mantine-color-scheme'),
  )
  if (current === scheme) return
  await page.getByRole('button', { name: 'Toggle colour scheme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-mantine-color-scheme', scheme)
}

export async function waitForCurveLoaded(page: Page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Yield curve' })).toBeVisible()
  await expect(page.getByLabel(/Valid date/)).toHaveValue('2026-10-16', { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Add to overlay' })).toBeEnabled({ timeout: 15_000 })
}

export function screenshotName(id: string, width: number, height: number, scheme: 'light' | 'dark') {
  return `${id}-${width}x${height}-${scheme}.png`
}
